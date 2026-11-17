"""Tutor AI: risponde solo con Ollama, usando i documenti recuperati dal RAG e citando le fonti."""
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from .ai_service import ai, AIUnavailable, ModelMissing
from .database import db
from .rag import search

router = APIRouter(prefix="/api/tutor")

BASE = ("Sei UniMind, un tutor universitario. Rispondi sempre in italiano. "
        "Per tutto ciò che riguarda il materiale dello studente usa SOLO gli estratti forniti e citali con [n]. "
        "Se gli estratti non contengono la risposta, dillo chiaramente senza inventare. "
        "Ogni spiegazione che aggiungi tu, non presente negli estratti, va introdotta con 'Approfondimento AI:'. "
        "Scrivi ogni formula matematica in LaTeX: nel testo tra $...$, su una riga propria tra $$...$$. "
        "Non inventare mai fonti.")
MODES = {
    "spiegazione": "MODALITÀ SPIEGAZIONE: insegna l'argomento in modo graduale, con esempi e formule dove servono.",
    "interrogazione": ("MODALITÀ INTERROGAZIONE: poni UNA sola domanda alla volta sull'argomento. Attendi la risposta, "
                       "valutala, correggi gli errori con la spiegazione giusta, poi fai la domanda successiva."),
    "esercizi": ("MODALITÀ ESERCIZI: proponi un esercizio alla volta, a difficoltà progressiva. Dopo la risposta "
                 "dello studente correggi passo dopo passo e proponi il successivo."),
}
CONFUSED = ("Lo studente NON ha capito la tua ultima spiegazione. Ricomincia dalle basi: spiega in modo molto più "
            "semplice con un'analogia quotidiana, poi aumenta la difficoltà gradualmente in 3 passi e chiudi con una "
            "domanda di controllo.")


class ConvIn(BaseModel):
    subject_id: int | None = None
    mode: str = "spiegazione"


class MsgIn(BaseModel):
    content: str
    confused: bool = False


@router.post("/conversations")
def new_conversation(b: ConvIn):
    if b.mode not in MODES:
        raise HTTPException(422, "Modalità non valida.")
    with db() as c:
        cur = c.execute("INSERT INTO conversations(subject_id, mode) VALUES(?,?)", (b.subject_id, b.mode))
        return {"id": cur.lastrowid}


@router.get("/conversations")
def list_conversations():
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT v.*, s.name AS subject_name FROM conversations v LEFT JOIN subjects s ON s.id=v.subject_id "
            "ORDER BY v.id DESC")]


@router.get("/conversations/{cid}/messages")
def messages(cid: int):
    with db() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (cid,))]
    for r in rows:
        r["sources"] = json.loads(r["sources"]) if r["sources"] else []
    return rows


@router.delete("/conversations/{cid}")
def delete_conversation(cid: int):
    with db() as c:
        c.execute("DELETE FROM conversations WHERE id=?", (cid,))
    return {"deleted": cid}


def build_system(mode: str, sources: list[dict], confused: bool) -> str:
    parts = [BASE, MODES.get(mode, MODES["spiegazione"])]
    if confused:
        parts.append(CONFUSED)
    if sources:
        ctx = "\n\n".join(f"[{i}] ({s['filename']}, pag. {s['page']}"
                          f"{', cap. ' + s['chapter'] if s.get('chapter') else ''})\n{s['text']}"
                          for i, s in enumerate(sources, start=1))
        parts.append("ESTRATTI DAI DOCUMENTI DELLO STUDENTE:\n" + ctx)
    else:
        parts.append("Non è stato trovato alcun estratto pertinente nei documenti dello studente (o non sono "
                     "ancora indicizzati). Dichiaralo chiaramente prima di rispondere e tutto ciò che aggiungi "
                     "deve essere introdotto con 'Approfondimento AI:'.")
    return "\n\n".join(parts)


def ev(kind: str, data) -> str:
    return json.dumps({"type": kind, "data": data}, ensure_ascii=False) + "\n"


@router.post("/conversations/{cid}/message")
async def send_message(cid: int, body: MsgIn):
    with db() as c:
        conv = c.execute("SELECT * FROM conversations WHERE id=?", (cid,)).fetchone()
        if not conv:
            raise HTTPException(404, "Conversazione non trovata.")
        hist = [dict(r) for r in c.execute(
            "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 10", (cid,))][::-1]
        c.execute("INSERT INTO messages(conversation_id, role, content) VALUES(?,?,?)", (cid, "user", body.content))
        if not conv["title"]:
            c.execute("UPDATE conversations SET title=? WHERE id=?", (body.content[:50], cid))

    async def gen():
        prev = [m["content"] for m in hist if m["role"] == "user" and m["content"] != "Non ho capito."]
        query = body.content
        if body.confused and prev:
            query = prev[-1]
        elif len(body.content.split()) <= 3 and prev:
            query = prev[-1] + " " + body.content
        try:
            sources = await search(query, conv["subject_id"], k=5)
        except (AIUnavailable, ModelMissing) as e:
            yield ev("error", str(e)); return
        except ImportError:
            yield ev("error", "ChromaDB non è installato: esegui 'pip install chromadb'."); return
        yield ev("sources", sources)

        msgs = [{"role": "system", "content": build_system(conv["mode"], sources, body.confused)}] + hist + \
               [{"role": "user", "content": body.content}]
        reply = ""
        try:
            async for tok in ai.stream_chat(msgs):
                reply += tok
                yield ev("token", tok)
        except (AIUnavailable, ModelMissing) as e:
            yield ev("error", str(e))
        if reply:
            with db() as c:
                c.execute("INSERT INTO messages(conversation_id, role, content, sources) VALUES(?,?,?,?)",
                          (cid, "assistant", reply, json.dumps(sources, ensure_ascii=False)))

    return StreamingResponse(gen(), media_type="application/x-ndjson")
