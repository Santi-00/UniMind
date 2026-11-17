"""Studio in sequenza: dal documento ai capitoli, dai capitoli alle lezioni, una dopo l'altra."""
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from .ai_service import ai, AIUnavailable, ModelMissing
from .database import db
from .lessons import build_for_chapter
from .progress import set_state

router = APIRouter(prefix="/api/study")
jobs: dict[int, dict] = {}


async def save_chapter_lesson(chapter_id: int) -> dict:
    data = await build_for_chapter(chapter_id)
    with db() as c:
        old = c.execute("SELECT id FROM lessons WHERE chapter_id=? ORDER BY id DESC LIMIT 1", (chapter_id,)).fetchone()
        if old:  # rigenerazione: gli appunti personali restano
            c.execute("UPDATE lessons SET title=?, content=?, studied=0 WHERE id=?", (data["title"], data["content"], old["id"]))
            lid = old["id"]
        else:
            lid = c.execute("INSERT INTO lessons(subject_id, document_id, chapter_id, title, content) VALUES(?,?,?,?,?)",
                            (data["subject_id"], data["document_id"], chapter_id, data["title"], data["content"])).lastrowid
        set_state(c, data["subject_id"], data["title"], "caricato")
    return {"lesson_id": lid, "title": data["title"]}


@router.get("/{doc_id}")
def overview(doc_id: int):
    with db() as c:
        doc = c.execute("SELECT id, filename, subject_id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(404, "Documento non trovato.")
        chapters = [dict(r) for r in c.execute(
            "SELECT ch.id, ch.title, ch.position, ch.page_start, ch.page_end, "
            "(SELECT id FROM lessons WHERE chapter_id=ch.id ORDER BY id DESC LIMIT 1) AS lesson_id, "
            "(SELECT studied FROM lessons WHERE chapter_id=ch.id ORDER BY id DESC LIMIT 1) AS studied "
            "FROM chapters ch WHERE ch.document_id=? ORDER BY ch.position", (doc_id,))]
    return {"document": dict(doc), "chapters": chapters, "job": jobs.get(doc_id)}


@router.post("/chapter/{chapter_id}/generate")
async def generate_one(chapter_id: int):
    return await save_chapter_lesson(chapter_id)


async def _run_all(doc_id: int):
    job = jobs[doc_id]
    try:
        with db() as c:
            todo = [(r["id"], r["title"]) for r in c.execute(
                "SELECT ch.id, ch.title FROM chapters ch WHERE ch.document_id=? AND NOT EXISTS "
                "(SELECT 1 FROM lessons l WHERE l.chapter_id=ch.id) ORDER BY ch.position", (doc_id,))]
        job["total"] = len(todo)
        for cid, title in todo:
            job["current"] = title
            await save_chapter_lesson(cid)
            job["done"] += 1
    except HTTPException as e:
        job["error"] = str(e.detail)
    except Exception as e:
        logging.exception("Generazione lezioni in sequenza")
        job["error"] = f"{e.__class__.__name__}: {e}"
    finally:
        job["running"] = False
        job["current"] = None


@router.post("/{doc_id}/generate-all")
async def generate_all(doc_id: int, background: BackgroundTasks):
    if jobs.get(doc_id, {}).get("running"):
        raise HTTPException(409, "La generazione è già in corso per questo documento.")
    try:
        await ai._require_model("llm")
    except AIUnavailable as e:
        raise HTTPException(503, str(e))
    except ModelMissing as e:
        raise HTTPException(409, str(e))
    jobs[doc_id] = {"running": True, "total": 0, "done": 0, "current": None, "error": None}
    background.add_task(_run_all, doc_id)
    return jobs[doc_id]
