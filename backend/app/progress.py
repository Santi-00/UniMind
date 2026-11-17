from datetime import date
from fastapi import APIRouter
from pydantic import BaseModel
from .database import db

router = APIRouter(prefix="/api/progress")
RANK = {"caricato": 0, "studiato": 1, "verificato": 2, "assimilato": 3}


def set_state(c, subject_id: int, topic: str, state: str, allow_downgrade: bool = False) -> None:
    row = c.execute("SELECT id, state FROM progress WHERE subject_id=? AND topic=?", (subject_id, topic)).fetchone()
    if row is None:
        c.execute("INSERT INTO progress(subject_id, topic, state) VALUES(?,?,?)", (subject_id, topic, state))
    elif allow_downgrade or RANK[state] > RANK.get(row["state"], 0):
        c.execute("UPDATE progress SET state=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (state, row["id"]))


def preparation(studied_ratio: float, avg_test_pct: float | None) -> int:
    """30% = lezioni studiate, 70% = media degli ultimi test. Senza test il massimo è 30%."""
    return round(30 * studied_ratio + 0.7 * (avg_test_pct or 0))


@router.get("")
def overview():
    out = []
    with db() as c:
        for s in c.execute("SELECT * FROM subjects ORDER BY name").fetchall():
            sid = s["id"]
            docs = c.execute("SELECT COUNT(*) FROM documents WHERE subject_id=?", (sid,)).fetchone()[0]
            lessons = c.execute("SELECT COUNT(*), COALESCE(SUM(studied),0) FROM lessons WHERE subject_id=?", (sid,)).fetchone()
            attempts = [dict(r) for r in c.execute(
                "SELECT a.score_pct, a.grade_30, a.weak_topics, a.created_at, t.topic FROM test_attempts a "
                "JOIN tests t ON t.id=a.test_id WHERE t.subject_id=? ORDER BY a.id", (sid,))]
            last5 = [a["score_pct"] for a in attempts[-5:]]
            avg = round(sum(last5) / len(last5), 1) if last5 else None
            weak: dict[str, int] = {}
            import json
            for a in attempts[-5:]:
                for t in json.loads(a["weak_topics"] or "[]"):
                    weak[t] = weak.get(t, 0) + 1
            states = {r["state"]: r["n"] for r in c.execute(
                "SELECT state, COUNT(*) AS n FROM progress WHERE subject_id=? GROUP BY state", (sid,))}
            strong = [r["topic"] for r in c.execute(
                "SELECT topic FROM progress WHERE subject_id=? AND state='assimilato' ORDER BY updated_at DESC LIMIT 5", (sid,))]
            minutes = c.execute("SELECT COALESCE(SUM(minutes),0) FROM study_sessions WHERE subject_id=?", (sid,)).fetchone()[0]
            ratio = (lessons[1] / lessons[0]) if lessons[0] else 0
            out.append({
                "id": sid, "name": s["name"], "color": s["color"], "exam_date": s["exam_date"],
                "documenti": docs, "lezioni": lessons[0], "lezioni_studiate": lessons[1],
                "argomenti": states, "media_test": avg, "andamento": [a["score_pct"] for a in attempts[-10:]],
                "punti_deboli": sorted(weak, key=weak.get, reverse=True)[:5], "punti_forti": strong,
                "minuti_studio": minutes, "preparazione": preparation(ratio, avg),
            })
    return out


class SessionIn(BaseModel):
    subject_id: int
    minutes: int


@router.post("/session")
def log_session(b: SessionIn):
    with db() as c:
        c.execute("INSERT INTO study_sessions(subject_id, minutes, day) VALUES(?,?,?)",
                  (b.subject_id, max(1, b.minutes), date.today().isoformat()))
    return {"ok": True}
