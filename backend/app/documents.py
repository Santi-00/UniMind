"""Upload ed estrazione del testo, tutto in locale. Nessun file viene mai sovrascritto."""
import re
import uuid
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from .config import STORAGE_DIR, load_settings
from .database import db

router = APIRouter(prefix="/api/documents")

ALLOWED = {".pdf", ".ppt", ".pptx", ".doc", ".docx", ".txt", ".jpg", ".jpeg", ".png"}


def target_folder(ext: str) -> Path:
    if ext in (".jpg", ".jpeg", ".png"):
        return STORAGE_DIR / "images"
    if ext in (".ppt", ".pptx"):
        return STORAGE_DIR / "presentations"
    return STORAGE_DIR / "documents"


# ---------- estrazione: restituisce [(pagina_o_slide, testo)] ----------
def extract(path: Path) -> list[tuple[int, str]]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        import fitz  # PyMuPDF
        with fitz.open(path) as pdf:
            pages = [(i + 1, p.get_text()) for i, p in enumerate(pdf)]
        if not any(t.strip() for _, t in pages):
            raise RuntimeError("PDF senza testo selezionabile (probabile scansione). "
                               "Serve l'OCR locale: installa Tesseract e pytesseract.")
        return pages
    if ext == ".pptx":
        from pptx import Presentation
        out = []
        for i, slide in enumerate(Presentation(path).slides, start=1):
            parts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
            out.append((i, "\n".join(parts)))
        return out
    if ext == ".docx":
        import docx
        d = docx.Document(path)
        return [(1, "\n".join(p.text for p in d.paragraphs))]
    if ext == ".txt":
        return [(1, path.read_text(encoding="utf-8", errors="replace"))]
    if ext in (".jpg", ".jpeg", ".png"):
        try:
            import pytesseract
            from PIL import Image
            return [(1, pytesseract.image_to_string(Image.open(path)))]
        except ImportError:
            raise RuntimeError("OCR locale non installato: servono pytesseract, pillow e Tesseract.")
    raise RuntimeError("Formato legacy (.ppt/.doc) non leggibile: salvalo come .pptx/.docx e ricaricalo.")


def chunk_text(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    out, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) > size and cur:
            out.append(cur.strip())
            cur = cur[-overlap:] + "\n\n"
        cur += para + "\n\n"
        while len(cur) > size * 2:  # paragrafo gigante
            out.append(cur[:size].strip())
            cur = cur[size - overlap:]
    if cur.strip():
        out.append(cur.strip())
    return out


def process(doc_id: int) -> None:
    with db() as c:
        row = c.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        c.execute("UPDATE documents SET status='in elaborazione', error=NULL WHERE id=?", (doc_id,))
    try:
        from .rag import remove_document_vectors
        remove_document_vectors(doc_id)
        pages = extract(Path(row["stored_path"]))
        with db() as c:
            c.execute("DELETE FROM chunks WHERE document_id=?", (doc_id,))
            n = 0
            for page, text in pages:
                for ch in chunk_text(text):
                    c.execute("INSERT INTO chunks(document_id,subject_id,page,text) VALUES(?,?,?,?)",
                              (doc_id, row["subject_id"], page, ch))
                    n += 1
            if n == 0:
                raise RuntimeError("Nessun testo estratto dal documento.")
            c.execute("UPDATE documents SET status='analizzato' WHERE id=?", (doc_id,))
    except Exception as e:  # errore gestito: il documento resta, con stato 'errore'
        with db() as c:
            c.execute("UPDATE documents SET status='errore', error=? WHERE id=?", (str(e), doc_id))


@router.post("")
async def upload(background: BackgroundTasks, files: list[UploadFile] = File(...),
                 subject_id: int | None = Form(None)):
    limit = load_settings()["max_upload_mb"] * 1024 * 1024
    created, rejected = [], []
    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in ALLOWED:
            rejected.append({"filename": f.filename, "motivo": f"Formato {ext or 'sconosciuto'} non supportato."})
            continue
        dest = target_folder(ext) / f"{uuid.uuid4().hex[:8]}_{Path(f.filename).name}"
        size = 0
        with open(dest, "wb") as out:
            while chunk := await f.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    break
                out.write(chunk)
        if size > limit:
            dest.unlink(missing_ok=True)
            rejected.append({"filename": f.filename, "motivo": "File troppo grande."})
            continue
        with db() as c:
            cur = c.execute("INSERT INTO documents(subject_id,filename,stored_path,mime,size_bytes) VALUES(?,?,?,?,?)",
                            (subject_id, f.filename, str(dest), f.content_type, size))
        created.append(cur.lastrowid)
        background.add_task(process, cur.lastrowid)
    return {"created": created, "rejected": rejected}


@router.get("")
def list_documents(subject_id: int | None = None, status: str | None = None,
                   q: str | None = None, sort: str = "recenti"):
    sql = ("SELECT d.*, s.name AS subject_name, s.color AS subject_color, "
           "(SELECT COUNT(*) FROM chunks WHERE document_id=d.id) AS n_chunks, "
           "(SELECT COUNT(*) FROM chunks WHERE document_id=d.id AND indexed_model IS NOT NULL) AS n_indexed "
           "FROM documents d LEFT JOIN subjects s ON s.id=d.subject_id WHERE 1=1")
    args: list = []
    if subject_id:
        sql += " AND d.subject_id=?"; args.append(subject_id)
    if status:
        sql += " AND d.status=?"; args.append(status)
    if q:
        sql += (" AND (d.filename LIKE ? OR EXISTS (SELECT 1 FROM chunks k WHERE k.document_id=d.id AND k.text LIKE ?))")
        args += [f"%{q}%", f"%{q}%"]
    sql += {"nome": " ORDER BY d.filename", "dimensione": " ORDER BY d.size_bytes DESC"}.get(sort, " ORDER BY d.id DESC")
    with db() as c:
        return [dict(r) for r in c.execute(sql, args)]


class DocPatch(BaseModel):
    filename: str | None = None
    subject_id: int | None = None


@router.patch("/{did}")
def patch_document(did: int, p: DocPatch):
    with db() as c:
        if p.filename:
            c.execute("UPDATE documents SET filename=? WHERE id=?", (p.filename, did))
        if p.subject_id is not None:
            c.execute("UPDATE documents SET subject_id=? WHERE id=?", (p.subject_id, did))
            c.execute("UPDATE chunks SET subject_id=? WHERE document_id=?", (p.subject_id, did))
    if p.subject_id is not None:
        from .rag import remove_document_vectors
        remove_document_vectors(did)  # da reindicizzare con la nuova materia
    return {"id": did}


@router.get("/{did}/preview")
def preview(did: int):
    with db() as c:
        rows = c.execute("SELECT page, text FROM chunks WHERE document_id=? ORDER BY id LIMIT 12", (did,)).fetchall()
    return [dict(r) for r in rows]


@router.get("/{did}/download")
def download(did: int):
    with db() as c:
        r = c.execute("SELECT filename, stored_path FROM documents WHERE id=?", (did,)).fetchone()
    if not r or not Path(r["stored_path"]).exists():
        raise HTTPException(404, "File non trovato.")
    return FileResponse(r["stored_path"], filename=r["filename"])


@router.post("/{did}/reprocess")
def reprocess(did: int, background: BackgroundTasks):
    background.add_task(process, did)
    return {"id": did}


@router.delete("/{did}")
def delete_document(did: int):
    with db() as c:
        r = c.execute("SELECT stored_path FROM documents WHERE id=?", (did,)).fetchone()
        c.execute("DELETE FROM documents WHERE id=?", (did,))
    if r:
        Path(r["stored_path"]).unlink(missing_ok=True)
    from .rag import remove_document_vectors
    remove_document_vectors(did)
    return {"deleted": did}
