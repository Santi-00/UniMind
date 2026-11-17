from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .database import db

router = APIRouter(prefix="/api/schedule")


class EventIn(BaseModel):
    subject_id: int | None = None
    professor: str | None = None
    weekday: int          # 0 = lunedì ... 6 = domenica
    start_time: str       # HH:MM
    end_time: str
    room: str | None = None
    kind: str | None = None
    reminder_minutes: int = 15


SELECT = ("SELECT e.*, s.name AS subject_name, s.color AS subject_color "
          "FROM schedule_events e LEFT JOIN subjects s ON s.id = e.subject_id ")


@router.get("")
def list_events():
    with db() as c:
        return [dict(r) for r in c.execute(SELECT + "ORDER BY e.weekday, e.start_time")]


@router.post("")
def create_event(e: EventIn):
    if not (0 <= e.weekday <= 6) or e.end_time <= e.start_time:
        raise HTTPException(422, "Giorno o orario non validi.")
    with db() as c:
        cur = c.execute(
            "INSERT INTO schedule_events(subject_id,professor,weekday,start_time,end_time,room,kind,reminder_minutes)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (e.subject_id, e.professor, e.weekday, e.start_time, e.end_time, e.room, e.kind, e.reminder_minutes))
        return {"id": cur.lastrowid}


@router.put("/{eid}")
def update_event(eid: int, e: EventIn):
    if e.end_time <= e.start_time:
        raise HTTPException(422, "L'ora di fine deve seguire l'ora di inizio.")
    with db() as c:
        c.execute("UPDATE schedule_events SET subject_id=?,professor=?,weekday=?,start_time=?,end_time=?,"
                  "room=?,kind=?,reminder_minutes=? WHERE id=?",
                  (e.subject_id, e.professor, e.weekday, e.start_time, e.end_time, e.room, e.kind,
                   e.reminder_minutes, eid))
    return {"id": eid}


@router.post("/{eid}/duplicate")
def duplicate_event(eid: int):
    with db() as c:
        r = c.execute("SELECT * FROM schedule_events WHERE id=?", (eid,)).fetchone()
        if not r:
            raise HTTPException(404, "Evento non trovato.")
        cur = c.execute(
            "INSERT INTO schedule_events(subject_id,professor,weekday,start_time,end_time,room,kind,reminder_minutes)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (r["subject_id"], r["professor"], r["weekday"], r["start_time"], r["end_time"], r["room"],
             r["kind"], r["reminder_minutes"]))
        return {"id": cur.lastrowid}


@router.delete("/{eid}")
def delete_event(eid: int):
    with db() as c:
        c.execute("DELETE FROM schedule_events WHERE id=?", (eid,))
    return {"deleted": eid}
