"""Configurazione locale di UniMind (nessuna dipendenza esterna)."""
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE = BASE_DIR / "config" / "config.json"
DB_FILE = BASE_DIR / "database" / "unimind.db"
STORAGE_DIR = BASE_DIR / "storage"
VECTOR_DIR = BASE_DIR / "vectorstore"
BACKUP_DIR = BASE_DIR / "backups"
LOG_DIR = BASE_DIR / "logs"

DEFAULTS = {
    "ollama_url": "http://localhost:11434",
    "llm_model": "",          # scelto dall'utente nelle impostazioni
    "embedding_model": "",    # scelto dall'utente nelle impostazioni
    "request_timeout": 300,
    "max_context_chars": 24000,
    "max_upload_mb": 100,
}


def ensure_dirs() -> None:
    for d in (CONFIG_FILE.parent, DB_FILE.parent, STORAGE_DIR / "documents",
              STORAGE_DIR / "images", STORAGE_DIR / "presentations",
              VECTOR_DIR, BACKUP_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    ensure_dirs()
    data = dict(DEFAULTS)
    if CONFIG_FILE.exists():
        try:
            data.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            pass
    return data


def save_settings(updates: dict) -> dict:
    data = load_settings()
    for k, v in updates.items():
        if k in DEFAULTS:
            data[k] = v
    CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data
