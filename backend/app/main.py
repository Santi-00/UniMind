import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from .ai_service import ai, AIUnavailable, ModelMissing
from .config import LOG_DIR, ensure_dirs, load_settings, save_settings, BASE_DIR, DB_FILE, STORAGE_DIR, VECTOR_DIR, BACKUP_DIR
from .database import db, init_db

ensure_dirs()
logging.basicConfig(filename=LOG_DIR / "unimind.log", level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="UniMind", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    init_db()
    try:  # un backup automatico al giorno
        from .backup import auto_backup
        auto_backup()
    except Exception:
        logging.exception("Backup automatico non riuscito")


def ai_errors(fn):
    from functools import wraps
    @wraps(fn)
    async def wrap(*a, **k):
        try:
            return await fn(*a, **k)
        except AIUnavailable as e:
            raise HTTPException(503, str(e))
        except ModelMissing as e:
            raise HTTPException(409, str(e))
    return wrap


@app.get("/api/health")
def health():
    return {"ok": True}


# ---------- IA ----------
@app.get("/api/ai/status")
async def ai_status():
    return await ai.status()


class SettingsIn(BaseModel):
    ollama_url: str | None = None
    llm_model: str | None = None
    embedding_model: str | None = None


@app.put("/api/ai/settings")
def ai_settings(body: SettingsIn):
    return save_settings({k: v for k, v in body.model_dump().items() if v is not None})


@app.get("/api/ai/hardware")
def hardware():
    import os
    info = {"cpu_cores": os.cpu_count()}
    try:
        import psutil
        info["ram_total_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
        info["ram_available_gb"] = round(psutil.virtual_memory().available / 1e9, 1)
    except ImportError:
        info["ram_note"] = "Installa psutil per il rilevamento della RAM."
    info["gpu_note"] = "Il rilevamento GPU è delegato a Ollama (vedi 'ollama ps')."
    ram = info.get("ram_total_gb")
    if ram:
        info["suggerimento"] = ("modelli piccoli (1-4B)" if ram < 12 else
                                "modelli medi (7-9B)" if ram < 24 else "modelli grandi (14B+)")
    return info


class TestIn(BaseModel):
    prompt: str = "Rispondi solo con la parola: ok"


@app.post("/api/ai/test")
@ai_errors
async def ai_test(body: TestIn):
    return {"response": await ai.chat([{"role": "user", "content": body.prompt}])}


class ChatIn(BaseModel):
    messages: list[dict]


@app.post("/api/ai/chat/stream")
async def ai_stream(body: ChatIn):
    async def gen():
        try:
            async for piece in ai.stream_chat(body.messages):
                yield piece
        except (AIUnavailable, ModelMissing) as e:
            yield f"\n[ERRORE] {e}"
    return StreamingResponse(gen(), media_type="text/plain; charset=utf-8")


# ---------- Materie ----------
class SubjectIn(BaseModel):
    name: str
    professor: str | None = None
    description: str | None = None
    color: str = "#7c3aed"
    exam_date: str | None = None


@app.get("/api/subjects")
def list_subjects():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM subjects ORDER BY name")]


@app.post("/api/subjects")
def create_subject(s: SubjectIn):
    with db() as c:
        cur = c.execute("INSERT INTO subjects(name,professor,description,color,exam_date) VALUES(?,?,?,?,?)",
                        (s.name, s.professor, s.description, s.color, s.exam_date))
        return {"id": cur.lastrowid, **s.model_dump()}


@app.put("/api/subjects/{sid}")
def update_subject(sid: int, s: SubjectIn):
    with db() as c:
        c.execute("UPDATE subjects SET name=?,professor=?,description=?,color=?,exam_date=? WHERE id=?",
                  (s.name, s.professor, s.description, s.color, s.exam_date, sid))
    return {"id": sid, **s.model_dump()}


@app.delete("/api/subjects/{sid}")
def delete_subject(sid: int):
    with db() as c:
        c.execute("DELETE FROM subjects WHERE id=?", (sid,))
    return {"deleted": sid}


# ---------- Privacy ----------
@app.get("/api/privacy")
def privacy():
    return {
        "database": str(DB_FILE), "documenti": str(STORAGE_DIR), "vettori": str(VECTOR_DIR),
        "backup": str(BACKUP_DIR), "log": str(LOG_DIR / "unimind.log"),
        "telemetria": False, "servizi_esterni": False,
        "nota": "Tutti i dati restano sul tuo computer. L'unica connessione è verso Ollama locale.",
    }


# ---------- Router ----------
from . import documents, schedule  # noqa: E402
app.include_router(documents.router)
app.include_router(schedule.router)


@app.get("/api/dashboard")
def dashboard():
    with db() as c:
        n = lambda t: c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        exams = [dict(r) for r in c.execute(
            "SELECT name, exam_date, color FROM subjects WHERE exam_date IS NOT NULL AND exam_date >= date('now') "
            "ORDER BY exam_date LIMIT 5")]
        prof = c.execute("SELECT name FROM profile WHERE id=1").fetchone()
        last = [dict(r) for r in c.execute(
            "SELECT a.score_pct, a.grade_30, a.created_at, t.topic, s.name AS subject_name FROM test_attempts a "
            "JOIN tests t ON t.id=a.test_id LEFT JOIN subjects s ON s.id=t.subject_id ORDER BY a.id DESC LIMIT 5")]
        prep = [{k: r[k] for k in ("id", "name", "color", "preparazione", "media_test")} for r in progress.overview()]
        return {"nome": (prof["name"] if prof else "") or "", "materie": n("subjects"), "documenti": n("documents"),
                "lezioni": n("lessons"), "test": n("test_attempts"), "esami": exams,
                "preparazione": prep, "ultimi_test": last}

from . import rag, tutor  # noqa: E402
app.include_router(rag.router)
app.include_router(tutor.router)

from . import lessons, quizzes, progress, plans  # noqa: E402
for _m in (lessons, quizzes, progress, plans):
    app.include_router(_m.router)


from . import backup, profile, study  # noqa: E402
for _m in (backup, profile, study):
    app.include_router(_m.router)
