"""SQLite locale con migrazioni additive (nessuna cancellazione di dati)."""
import sqlite3
from contextlib import contextmanager
from .config import DB_FILE, ensure_dirs

MIGRATIONS = [
    # v1: schema iniziale
    """
    CREATE TABLE profile (id INTEGER PRIMARY KEY, name TEXT, info TEXT, preferences TEXT);
    CREATE TABLE subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, professor TEXT,
        description TEXT, color TEXT DEFAULT '#7c3aed', exam_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE schedule_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
        professor TEXT, weekday INTEGER NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL,
        room TEXT, kind TEXT, reminder_minutes INTEGER DEFAULT 15);
    CREATE TABLE documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
        filename TEXT NOT NULL, stored_path TEXT NOT NULL, mime TEXT, size_bytes INTEGER,
        status TEXT DEFAULT 'caricato', error TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE chapters (
        id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
        title TEXT, position INTEGER, page_start INTEGER, page_end INTEGER);
    CREATE TABLE chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
        subject_id INTEGER, chapter_id INTEGER, page INTEGER, text TEXT NOT NULL);
    CREATE TABLE lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
        document_id INTEGER, title TEXT, content TEXT, notes TEXT, studied INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER, mode TEXT DEFAULT 'spiegazione',
        title TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
        role TEXT NOT NULL, content TEXT NOT NULL, sources TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE tests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER, topic TEXT, difficulty TEXT,
        questions TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE test_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, test_id INTEGER REFERENCES tests(id) ON DELETE CASCADE,
        answers TEXT, score_pct REAL, grade_30 REAL, weak_topics TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER, topic TEXT,
        state TEXT DEFAULT 'caricato', updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE study_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER, minutes INTEGER, day TEXT);
    CREATE TABLE study_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER, plan TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    """,
    # v2: traccia quali chunk sono indicizzati e con quale modello di embedding
    "ALTER TABLE chunks ADD COLUMN indexed_model TEXT;",
    # v3: collega le lezioni ai capitoli (studio in sequenza)
    "ALTER TABLE lessons ADD COLUMN chapter_id INTEGER;",
]


def connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        for i, script in enumerate(MIGRATIONS, start=1):
            if i > version:
                conn.executescript(script)
                conn.execute(f"PRAGMA user_version = {i}")
