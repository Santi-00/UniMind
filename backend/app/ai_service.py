"""LocalAIService: unico punto di accesso a Ollama. Nessuna simulazione, nessun cloud."""
import json
import time
from typing import AsyncIterator
import httpx
from .config import load_settings


class AIUnavailable(Exception):
    """Ollama non raggiungibile o in errore."""


class ModelMissing(Exception):
    """Il modello selezionato non è installato."""


def _ollama_error(status: int, body: str) -> str:
    """Estrae la causa reale dalla risposta di errore di Ollama."""
    try:
        msg = json.loads(body).get("error", body)
    except ValueError:
        msg = body
    msg = (msg or "").strip()[:300] or "nessun dettaglio"
    out = f"Ollama ha risposto con errore {status}: {msg}"
    if any(w in msg.lower() for w in ("memory", "memoria", "allocate", "failed to load", "out of")):
        out += " — Il modello è troppo pesante per la memoria disponibile: scegline uno più piccolo (es. qwen2.5:3b) e chiudi altri programmi."
    return out


class LocalAIService:
    _timings: list[float] = []

    def _cfg(self) -> dict:
        return load_settings()

    def _client(self, timeout: float | None = None) -> httpx.AsyncClient:
        cfg = self._cfg()
        return httpx.AsyncClient(base_url=cfg["ollama_url"], timeout=timeout or cfg["request_timeout"])

    async def status(self) -> dict:
        cfg = self._cfg()
        start = time.perf_counter()
        try:
            async with self._client(5) as c:
                r = await c.get("/api/tags")
                r.raise_for_status()
                models = [m["name"] for m in r.json().get("models", [])]
        except (httpx.HTTPError, OSError) as e:
            return {
                "online": False, "url": cfg["ollama_url"], "models": [],
                "llm_model": cfg["llm_model"], "embedding_model": cfg["embedding_model"],
                "error": str(e) or e.__class__.__name__,
                "help": "Ollama non è raggiungibile. Avvialo con 'ollama serve' "
                        "(o apri l'app Ollama) e riprova.",
                "avg_response_s": self.avg_time(),
            }
        return {
            "online": True, "url": cfg["ollama_url"], "models": models,
            "llm_model": cfg["llm_model"], "embedding_model": cfg["embedding_model"],
            "llm_installed": self._installed(cfg["llm_model"], models),
            "embedding_installed": self._installed(cfg["embedding_model"], models),
            "latency_ms": round((time.perf_counter() - start) * 1000),
            "avg_response_s": self.avg_time(),
        }

    @staticmethod
    def _installed(name: str, models: list[str]) -> bool:
        return bool(name) and any(m == name or m.split(":")[0] == name for m in models)

    async def _require_model(self, kind: str) -> str:
        cfg = self._cfg()
        name = cfg["llm_model"] if kind == "llm" else cfg["embedding_model"]
        st = await self.status()
        if not st["online"]:
            raise AIUnavailable(st["help"])
        if not name:
            raise ModelMissing(f"Nessun modello {kind} selezionato. Sceglilo dalle Impostazioni.")
        if not self._installed(name, st["models"]):
            raise ModelMissing(f"Il modello '{name}' non è installato. Installalo con: ollama pull {name}")
        return name

    def avg_time(self) -> float | None:
        t = self._timings[-20:]
        return round(sum(t) / len(t), 2) if t else None

    def _trim(self, messages: list[dict]) -> list[dict]:
        """Taglia il contesto troppo lungo mantenendo system e ultimi messaggi."""
        limit = self._cfg()["max_context_chars"]
        system = [m for m in messages if m["role"] == "system"]
        rest = [m for m in messages if m["role"] != "system"]
        while rest and sum(len(m["content"]) for m in system + rest) > limit and len(rest) > 1:
            rest.pop(0)
        return system + rest

    async def chat(self, messages: list[dict], json_mode: bool = False) -> str:
        """json_mode=True forza Ollama a produrre JSON valido (molto più affidabile con i modelli piccoli)."""
        model = await self._require_model("llm")
        payload = {"model": model, "messages": self._trim(messages), "stream": False}
        if json_mode:
            payload["format"] = "json"
        start = time.perf_counter()
        try:
            async with self._client() as c:
                r = await c.post("/api/chat", json=payload)
                if r.status_code >= 400:
                    raise AIUnavailable(_ollama_error(r.status_code, r.text))
                out = r.json()["message"]["content"]
        except httpx.TimeoutException:
            raise AIUnavailable("Il modello ha impiegato troppo tempo. Prova un modello più piccolo.")
        except httpx.HTTPError as e:
            raise AIUnavailable(f"Errore di comunicazione con Ollama: {e}")
        self._timings.append(time.perf_counter() - start)
        return out

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        model = await self._require_model("llm")
        start = time.perf_counter()
        try:
            async with self._client() as c:
                async with c.stream("POST", "/api/chat",
                                    json={"model": model, "messages": self._trim(messages), "stream": True}) as r:
                    if r.status_code >= 400:
                        body = (await r.aread()).decode("utf-8", errors="replace")
                        raise AIUnavailable(_ollama_error(r.status_code, body))
                    async for line in r.aiter_lines():
                        if line:
                            part = json.loads(line)
                            if part.get("error"):
                                raise AIUnavailable(_ollama_error(500, line))
                            if part.get("message", {}).get("content"):
                                yield part["message"]["content"]
        except httpx.HTTPError as e:
            raise AIUnavailable(f"Errore di comunicazione con Ollama: {e}")
        self._timings.append(time.perf_counter() - start)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = await self._require_model("embedding")
        try:
            async with self._client() as c:
                r = await c.post("/api/embed", json={"model": model, "input": texts})
                if r.status_code >= 400:
                    raise AIUnavailable(_ollama_error(r.status_code, r.text))
                return r.json()["embeddings"]
        except httpx.HTTPError as e:
            raise AIUnavailable(f"Errore embedding: {e}")


ai = LocalAIService()
