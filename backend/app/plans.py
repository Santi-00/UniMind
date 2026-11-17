import json
from datetime import date, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .context import ask, parse_json_array
from .database import db

router = APIRouter(prefix="/api/plans")
GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]


class PlanIn(BaseModel):
    subject_id: int
    hours_per_day: float = 2
    reorganize: bool = False


def validate_plan(items, valid_dates: set[str], max_minutes: int) -> list[dict]:
    out = []
    for d in items or []:
        try:
            if d["date"] not in valid_dates:
                continue
            acts = [str(a) for a in d["activities"]][:8]
            out.append({"date": d["date"], "minutes": min(int(d.get("minutes", max_minutes)), max_minutes), "activities": acts})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(out, key=lambda x: x["date"])


@router.post("/generate")
async def generate(b: PlanIn):
    with db() as c:
        s = c.execute("SELECT * FROM subjects WHERE id=?", (b.subject_id,)).fetchone()
        if not s:
            raise HTTPException(404, "Materia non trovata.")
        if not s["exam_date"]:
            raise HTTPException(409, "Imposta la data d'esame nella materia (Le mie materie → Modifica).")
        lessons = [dict(r) for r in c.execute("SELECT title, studied FROM lessons WHERE subject_id=?", (b.subject_id,))]
        chapters = [r[0] for r in c.execute(
            "SELECT DISTINCT ch.title FROM chapters ch JOIN documents d ON d.id=ch.document_id WHERE d.subject_id=?", (b.subject_id,))]
        weak = [r["topic"] for r in c.execute("SELECT topic FROM progress WHERE subject_id=? AND state IN ('caricato','studiato','verificato')", (b.subject_id,))]
        events = [dict(r) for r in c.execute("SELECT weekday, start_time, end_time FROM schedule_events ORDER BY weekday, start_time")]
    today, exam = date.today(), date.fromisoformat(s["exam_date"])
    days = [(today + timedelta(days=i)) for i in range((exam - today).days)][:60]
    if not days:
        raise HTTPException(409, "La data d'esame è oggi o già passata.")
    todo = [l["title"] for l in lessons if not l["studied"]]
    topics = sorted(set(todo + chapters + weak))
    if not topics:
        raise HTTPException(409, "Servono argomenti: genera almeno una lezione o analizza i capitoli dei documenti.")
    max_min = int(b.hours_per_day * 60)
    busy = "; ".join(f"{GIORNI[e['weekday']]} {e['start_time']}-{e['end_time']}" for e in events) or "nessuna lezione inserita"
    prompt = (f"Crea un piano di studio in italiano per l'esame di {s['name']} (data esame {s['exam_date']}). "
              f"Tempo massimo: {max_min} minuti al giorno. Giorni disponibili (usa SOLO queste date): "
              f"{', '.join(d.isoformat() + ' ' + GIORNI[d.weekday()] for d in days)}. "
              f"Orario universitario settimanale (nei giorni con più lezioni pianifica meno studio): {busy}. "
              f"Argomenti ancora da studiare o rinforzare: {'; '.join(topics)}. "
              "Distribuisci gli argomenti in modo realistico, parti da quelli più deboli, negli ultimi giorni inserisci ripasso e test. "
              + ("Il piano precedente non è stato completato: riorganizza gli argomenti rimasti sui giorni rimanenti. " if b.reorganize else "")
              + 'Rispondi SOLO con un oggetto JSON: {"piano": [{"date": "AAAA-MM-GG", "minutes": numero, "activities": ["..."]}]}.')
    plan = validate_plan(parse_json_array(await ask([{"role": "user", "content": prompt}], json_mode=True)), {d.isoformat() for d in days}, max_min)
    if not plan:
        raise HTTPException(422, "Il modello non ha prodotto un piano valido. Riprova o usa un modello più grande.")
    with db() as c:
        c.execute("INSERT INTO study_plans(subject_id, plan) VALUES(?,?)", (b.subject_id, json.dumps(plan, ensure_ascii=False)))
    return plan


@router.get("/{subject_id}")
def latest(subject_id: int):
    with db() as c:
        r = c.execute("SELECT plan, created_at FROM study_plans WHERE subject_id=? ORDER BY id DESC LIMIT 1", (subject_id,)).fetchone()
    return {"plan": json.loads(r["plan"]), "created_at": r["created_at"]} if r else {"plan": [], "created_at": None}
