"""Backup, ripristino ed esportazione dei dati. Tutto locale, tutto in file .zip."""
import io
import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, Response

from . import config as cfg

router = APIRouter(prefix="/api")
KEEP_AUTO = 7
NAME_RE = re.compile(r"^unimind_[a-z_]+_\d{8}_\d{6}\.zip$")
EXPORT_TABLES = ["profile", "subjects", "schedule_events", "documents", "chapters", "lessons", "tests",
                 "test_attempts", "progress", "study_sessions", "study_plans", "conversations", "messages"]


def _copy_db(src_path: Path, dst_path: Path) -> None:
    """Copia coerente di un database SQLite anche mentre l'app lo sta usando."""
    src, dst = sqlite3.connect(src_path), sqlite3.connect(dst_path)
    try:
        with dst:
            src.backup(dst)
    finally:
        src.close(); dst.close()


def create_backup(kind: str = "manual") -> Path:
    cfg.ensure_dirs()
    dest = cfg.BACKUP_DIR / f"unimind_{kind}_{datetime.now():%Y%m%d_%H%M%S}.zip"
    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "unimind.db"
        _copy_db(cfg.DB_FILE, snapshot)
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snapshot, "database/unimind.db")
            for f in cfg.STORAGE_DIR.rglob("*"):
                if f.is_file():
                    z.write(f, "storage/" + f.relative_to(cfg.STORAGE_DIR).as_posix())
            z.writestr("manifest.json", json.dumps({"app": "UniMind", "format": 1, "kind": kind,
                                                      "created": datetime.now().isoformat(timespec="seconds")}))
    if kind == "auto":
        for old in sorted(cfg.BACKUP_DIR.glob("unimind_auto_*.zip"))[:-KEEP_AUTO]:
            old.unlink(missing_ok=True)
    return dest


def auto_backup() -> Path | None:
    """Un backup automatico al giorno, all'avvio (ne conserva gli ultimi 7)."""
    cfg.ensure_dirs()
    recent = [f for f in cfg.BACKUP_DIR.glob("unimind_auto_*.zip")
              if datetime.fromtimestamp(f.stat().st_mtime) > datetime.now() - timedelta(hours=24)]
    return None if recent else create_backup("auto")


def restore_backup(zip_path: Path) -> dict:
    try:
        z = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise ValueError("Il file non è uno zip valido.")
    with z:
        names = z.namelist()
        try:
            manifest = json.loads(z.read("manifest.json"))
        except (KeyError, ValueError):
            raise ValueError("Non è un backup di UniMind.")
        if manifest.get("app") != "UniMind" or "database/unimind.db" not in names:
            raise ValueError("Non è un backup di UniMind.")
        for n in names:  # protezione zip-slip
            p = PurePosixPath(n)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError("Backup non sicuro: contiene percorsi non validi.")
        safety = create_backup("prima_ripristino")  # rete di sicurezza: stato attuale salvato prima di sostituirlo
        with tempfile.TemporaryDirectory() as tmp:
            z.extract("database/unimind.db", tmp)
            _copy_db(Path(tmp) / "database" / "unimind.db", cfg.DB_FILE)
        restored = 0
        for n in names:
            if n.startswith("storage/") and not n.endswith("/"):
                target = cfg.STORAGE_DIR / PurePosixPath(n).relative_to("storage")
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as s, open(target, "wb") as d:
                    shutil.copyfileobj(s, d)
                restored += 1
    _fix_document_paths()
    conn = sqlite3.connect(cfg.DB_FILE)
    try:
        with conn:  # i vettori non fanno parte del backup: vanno rigenerati
            conn.execute("UPDATE chunks SET indexed_model=NULL")
    finally:
        conn.close()
    try:
        from .rag import wipe_vectors
        wipe_vectors()
    except Exception:
        pass
    return {"restored_files": restored, "safety_backup": safety.name}


def _fix_document_paths() -> None:
    """I percorsi dei file salvati nel database possono riferirsi a un altro PC: li riallinea alla cartella attuale."""
    from .documents import target_folder
    conn = sqlite3.connect(cfg.DB_FILE)
    try:
        with conn:
            for doc_id, stored in conn.execute("SELECT id, stored_path FROM documents").fetchall():
                p = Path(stored)
                if not p.exists():
                    fname = re.split(r"[\\/]", stored)[-1]  # funziona anche con percorsi Windows letti su Linux/macOS
                    cand = target_folder(Path(fname).suffix.lower()) / fname
                    if cand.exists():
                        conn.execute("UPDATE documents SET stored_path=? WHERE id=?", (str(cand), doc_id))
    finally:
        conn.close()


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (t or "").lower()).strip("-")[:50] or "lezione"


def export_zip() -> bytes:
    """Esporta i dati in formato leggibile: data.json + una lezione per file Markdown."""
    conn = sqlite3.connect(cfg.DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        data = {t: [dict(r) for r in conn.execute(f"SELECT * FROM {t}")] for t in EXPORT_TABLES}
    finally:
        conn.close()
    for d in data["documents"]:
        d.pop("stored_path", None)  # niente percorsi del tuo PC nell'export
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("data.json", json.dumps(data, ensure_ascii=False, indent=2))
        for l in data["lessons"]:
            body = l["content"] or ""
            if l.get("notes"):
                body += f"\n\n---\n## Appunti personali\n{l['notes']}\n"
            z.writestr(f"lessons/{l['id']:03d}_{_slug(l['title'])}.md", body)
    return buf.getvalue()


# ---------------- endpoint ----------------
def _info(f: Path) -> dict:
    kind = f.name[len("unimind_"):].rsplit("_", 2)[0]
    st = f.stat()
    return {"name": f.name, "kind": kind, "size_bytes": st.st_size,
            "created": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")}


def _safe(name: str) -> Path:
    if not NAME_RE.match(name):
        raise HTTPException(400, "Nome del backup non valido.")
    f = cfg.BACKUP_DIR / name
    if not f.exists():
        raise HTTPException(404, "Backup non trovato.")
    return f


@router.get("/backup")
def list_backups():
    cfg.ensure_dirs()
    return [_info(f) for f in sorted(cfg.BACKUP_DIR.glob("unimind_*.zip"), reverse=True)]


@router.post("/backup")
def new_backup():
    return _info(create_backup("manual"))


@router.get("/backup/{name}/download")
def download_backup(name: str):
    return FileResponse(_safe(name), filename=name)


@router.delete("/backup/{name}")
def delete_backup(name: str):
    _safe(name).unlink()
    return {"deleted": name}


@router.post("/backup/{name}/restore")
def restore_named(name: str):
    try:
        return restore_backup(_safe(name))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/backup-restore-upload")
async def restore_upload(file: UploadFile = File(...)):
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "upload.zip"
        with open(p, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
        try:
            return restore_backup(p)
        except ValueError as e:
            raise HTTPException(422, str(e))


@router.get("/export")
def export_data():
    return Response(export_zip(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="unimind_export.zip"'})
