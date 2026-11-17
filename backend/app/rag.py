"""RAG locale: chunk -> embedding (Ollama) -> ChromaDB su disco -> ricerca semantica."""
import asyncio
import json
import re
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from .ai_service import ai, AIUnavailable, ModelMissing
from .config import VECTOR_DIR, load_settings
from .context import parse_json_array
from .database import db

router = APIRouter(prefix="/api/rag")
BATCH = 16
state = {"running": False, "last_error": None}


def _slug(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", model).strip("_")[:50] or "default"


def _collection(model: str):
    import chromadb  # import tardivo: l'app parte anche senza ChromaDB
    from chromadb.config import Settings
    client = chromadb.PersistentClient(path=str(VECTOR_DIR), settings=Settings(anonymized_telemetry=False))
    # una collezione per modello: dimensioni degli embedding diverse non si mescolano
    return client.get_or_create_collection(f"unimind_{_slug(model)}", metadata={"hnsw:space": "cosine"})


def remove_document_vectors(doc_id: int) -> None:
    """Rimuove i vettori di un documento. Non deve mai bloccare altre operazioni."""
    try:
        model = load_settings()["embedding_model"]
        if model:
            _collection(model).delete(where={"document_id": doc_id})
    except Exception:
        pass
    try:
        with db() as c:
            c.execute("UPDATE chunks SET indexed_model=NULL WHERE document_id=?", (doc_id,))
    except Exception:
        pass


async def index_pending(document_id: int | None = None, subject_id: int | None = None) -> int:
    model = load_settings()["embedding_model"]
    sql = ("SELECT k.id, k.text, k.page, k.document_id, COALESCE(k.subject_id,0) AS subject_id, "
           "d.filename, COALESCE(ch.title,'') AS chapter FROM chunks k "
           "JOIN documents d ON d.id=k.document_id LEFT JOIN chapters ch ON ch.id=k.chapter_id "
           "WHERE (k.indexed_model IS NULL OR k.indexed_model != ?)")
    args: list = [model]
    if document_id:
        sql += " AND k.document_id=?"; args.append(document_id)
    if subject_id:
        sql += " AND k.subject_id=?"; args.append(subject_id)
    with db() as c:
        rows = [dict(r) for r in c.execute(sql, args)]
    if not rows:
        return 0
    col = _collection(model)
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        vectors = await ai.embed([r["text"] for r in batch])
        await asyncio.to_thread(
            col.upsert,
            ids=[f"c{r['id']}" for r in batch], embeddings=vectors,
            documents=[r["text"] for r in batch],
            metadatas=[{"document_id": r["document_id"], "subject_id": r["subject_id"], "page": r["page"] or 0,
                        "filename": r["filename"], "chapter": r["chapter"]} for r in batch])
        with db() as c:
            c.executemany("UPDATE chunks SET indexed_model=? WHERE id=?", [(model, r["id"]) for r in batch])
    return len(rows)


async def search(query: str, subject_id: int | None = None, k: int = 5) -> list[dict]:
    model = load_settings()["embedding_model"]
    col = _collection(model)
    if col.count() == 0:
        return []
    qv = (await ai.embed([query]))[0]
    where = {"$or": [{"subject_id": subject_id}, {"subject_id": 0}]} if subject_id else None
    res = await asyncio.to_thread(col.query, query_embeddings=[qv], n_results=min(k, col.count()), where=where)
    out = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        out.append({"text": text, "distance": round(dist, 3), **meta})
    return out


# ---------------- endpoints ----------------
@router.get("/status")
def rag_status():
    model = load_settings()["embedding_model"]
    with db() as c:
        total = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        done = c.execute("SELECT COUNT(*) FROM chunks WHERE indexed_model=?", (model,)).fetchone()[0]
    return {"embedding_model": model, "chunks_totali": total, "chunks_indicizzati": done,
            "in_corso": state["running"], "ultimo_errore": state["last_error"]}


async def _run(document_id, subject_id):
    state.update(running=True, last_error=None)
    try:
        await index_pending(document_id, subject_id)
    except (AIUnavailable, ModelMissing) as e:
        state["last_error"] = str(e)
    except ImportError:
        state["last_error"] = "ChromaDB non è installato: esegui 'pip install chromadb' nell'ambiente del backend."
    except Exception as e:
        import logging
        logging.exception("Errore di indicizzazione")
        state["last_error"] = f"Errore di indicizzazione: {e.__class__.__name__}: {e}"
    finally:
        state["running"] = False


@router.post("/index")
async def start_index(background: BackgroundTasks, document_id: int | None = None, subject_id: int | None = None):
    try:  # controlli sincroni, così l'utente vede subito il problema
        await ai._require_model("embedding")
        import chromadb  # noqa: F401
    except (AIUnavailable, ModelMissing) as e:
        raise HTTPException(503 if isinstance(e, AIUnavailable) else 409, str(e))
    except ImportError:
        raise HTTPException(500, "ChromaDB non è installato: esegui 'pip install chromadb'.")
    if state["running"]:
        raise HTTPException(409, "Un'indicizzazione è già in corso.")
    background.add_task(_run, document_id, subject_id)
    return {"started": True}


class SearchIn(BaseModel):
    query: str
    subject_id: int | None = None
    k: int = 5


@router.post("/search")
async def rag_search(body: SearchIn):
    try:
        return await search(body.query, body.subject_id, body.k)
    except AIUnavailable as e:
        raise HTTPException(503, str(e))
    except ModelMissing as e:
        raise HTTPException(409, str(e))
    except ImportError:
        raise HTTPException(500, "ChromaDB non è installato: esegui 'pip install chromadb'.")


# ---------------- capitoli con Ollama ----------------
@router.get("/chapters/{doc_id}")
def get_chapters(doc_id: int):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM chapters WHERE document_id=? ORDER BY position", (doc_id,))]


@router.post("/analyze/{doc_id}")
async def analyze(doc_id: int):
    with db() as c:
        pages = c.execute("SELECT page, GROUP_CONCAT(text, ' ') AS t FROM chunks WHERE document_id=? "
                          "GROUP BY page ORDER BY page", (doc_id,)).fetchall()
    if not pages:
        raise HTTPException(409, "Il documento non ha testo estratto.")
    per_page = max(120, min(400, 12000 // len(pages)))
    outline = "\n".join(f"[Pagina {p['page']}] {(p['t'] or '')[:per_page].replace(chr(10), ' ')}" for p in pages)
    prompt = ("Analizza questi estratti di un documento universitario e individua i capitoli o gli argomenti principali, "
              "in ordine. Rispondi SOLO con un oggetto JSON, senza altro testo, in questo formato: "
              '{"capitoli": [{"title": "Titolo", "page_start": 1}]}. Usa solo numeri di pagina che compaiono negli estratti.\n\n' + outline)
    try:
        raw = await ai.chat([{"role": "user", "content": prompt}], json_mode=True)
    except AIUnavailable as e:
        raise HTTPException(503, str(e))
    except ModelMissing as e:
        raise HTTPException(409, str(e))
    try:
        items = parse_json_array(raw) or []
        items = [{"title": str(i.get("title") or i.get("titolo"))[:150],
                  "page_start": int(i.get("page_start") or i.get("pagina") or i.get("page"))} for i in items]
    except (ValueError, KeyError, TypeError):
        items = []
    if not items:
        raise HTTPException(422, "Il modello non ha restituito capitoli leggibili. Riprova o usa un modello più grande.")
    items.sort(key=lambda i: i["page_start"])
    with db() as c:
        c.execute("DELETE FROM chapters WHERE document_id=?", (doc_id,))
        last_page = pages[-1]["page"]
        ids = []
        for pos, it in enumerate(items):
            end = items[pos + 1]["page_start"] - 1 if pos + 1 < len(items) else last_page
            cur = c.execute("INSERT INTO chapters(document_id,title,position,page_start,page_end) VALUES(?,?,?,?,?)",
                            (doc_id, it["title"], pos + 1, it["page_start"], max(end, it["page_start"])))
            ids.append((cur.lastrowid, it["page_start"], max(end, it["page_start"])))
        for cid, a, b in ids:
            c.execute("UPDATE chunks SET chapter_id=? WHERE document_id=? AND page BETWEEN ? AND ?", (cid, doc_id, a, b))
    remove_document_vectors(doc_id)  # i metadati dei capitoli sono cambiati: da reindicizzare
    return get_chapters(doc_id)


@router.get("/diagnostics")
async def diagnostics():
    """Controlla uno per uno i passaggi necessari all'indicizzazione e dice dove si blocca."""
    steps = []

    def add(name: str, ok: bool, detail: str = ""):
        steps.append({"controllo": name, "ok": ok, "dettaglio": detail})

    model = load_settings()["embedding_model"]
    add("Modello embedding scelto", bool(model), model or "Scegli il modello in Impostazioni e premi Salva.")
    try:
        import chromadb
        add("ChromaDB installato", True, "versione " + chromadb.__version__)
    except Exception as e:
        add("ChromaDB installato", False, f"{e.__class__.__name__}: {e}")
    if model:
        try:
            v = await ai.embed(["prova"])
            add("Embedding con Ollama", True, f"{len(v[0])} dimensioni")
        except Exception as e:
            add("Embedding con Ollama", False, str(e))
        try:
            add("Archivio vettori su disco", True, f"{_collection(model).count()} vettori")
        except Exception as e:
            add("Archivio vettori su disco", False, f"{e.__class__.__name__}: {e}")
    with db() as c:
        docs = c.execute("SELECT COUNT(*) FROM documents WHERE status='analizzato'").fetchone()[0]
        chunks = c.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    add("Documenti con testo estratto", chunks > 0, f"{docs} documenti analizzati, {chunks} sezioni di testo")
    return steps


def wipe_vectors() -> None:
    """Elimina tutte le collezioni vettoriali di UniMind (usato dopo un ripristino da backup)."""
    try:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path=str(VECTOR_DIR), settings=Settings(anonymized_telemetry=False))
        for col in client.list_collections():
            name = col if isinstance(col, str) else col.name
            if name.startswith("unimind_"):
                client.delete_collection(name)
    except Exception:
        pass
