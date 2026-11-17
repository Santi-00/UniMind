"""Test generati da Ollama sui documenti, con correzione e aggiornamento dei progressi."""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .context import ask, get_context, parse_json_array, fix_latex
from .database import db
from .progress import set_state

router = APIRouter(prefix="/api/tests")
TYPES = {"multipla", "vero_falso", "aperta", "completamento", "esercizio", "programmazione", "logica"}
LEVELS = [(90, "Ottimo"), (75, "Buono"), (60, "Discreto"), (40, "Iniziale"), (0, "Insufficiente")]


def level(pct: float) -> str:
    return next(name for floor, name in LEVELS if pct >= floor)


def validate_questions(items, default_topic: str) -> list[dict]:
    out = []
    for q in items or []:
        try:
            t, text = q["type"], fix_latex(str(q["question"]).strip())
            if t not in TYPES or not text:
                continue
            item = {"type": t, "question": text, "topic": str(q.get("topic") or default_topic)[:100],
                    "explanation": fix_latex(str(q.get("explanation") or "")), "answer": fix_latex(str(q["answer"]).strip())}
            if t == "multipla":
                opts = [fix_latex(str(o)) for o in q["options"]]
                letter = item["answer"][:1].upper()
                if len(opts) < 2 or letter not in "ABCDEF"[:len(opts)]:
                    continue
                item.update(options=opts, answer=letter)
            elif t == "vero_falso":
                a = item["answer"].lower()
                if a not in ("vero", "falso"):
                    continue
                item["answer"] = a
            out.append(item)
        except (KeyError, TypeError):
            continue
    return out


def grade_closed(q: dict, given: str) -> float:
    g = (given or "").strip()
    if q["type"] == "multipla":
        return 1.0 if g[:1].upper() == q["answer"] else 0.0
    return 1.0 if g.lower() == q["answer"] else 0.0


def topic_states(results: list[dict]) -> dict[str, str]:
    by: dict[str, list[float]] = {}
    for r in results:
        by.setdefault(r["topic"], []).append(r["score"])
    return {t: ("assimilato" if sum(v) / len(v) >= 0.75 else "verificato") for t, v in by.items()}


class GenIn(BaseModel):
    subject_id: int
    topic: str | None = None
    n: int = 5
    difficulty: str = "media"
    types: list[str] = ["multipla", "vero_falso", "aperta"]


@router.post("/generate")
async def generate(b: GenIn):
    types = [t for t in b.types if t in TYPES] or ["multipla"]
    n = max(1, min(b.n, 20))
    ctx = await get_context(b.subject_id, None, b.topic)
    prompt = (f"Crea un test universitario in italiano di {n} domande, difficoltà {b.difficulty}, basato SOLO sul MATERIALE. "
              f"Tipologie ammesse: {', '.join(types)}. "
              'Scrivi ogni formula matematica in LaTeX tra $...$ e, dentro il JSON, raddoppia i backslash (es. $\\\\frac{a}{b}$). '
              'Rispondi SOLO con un oggetto JSON {"domande": [...]}. Ogni elemento dell\'array: '
              '{"type": "...", "question": "...", "options": ["testo A","testo B","testo C","testo D"] (solo per multipla), '
              '"answer": "lettera A-D per multipla, vero/falso per vero_falso, risposta o soluzione di riferimento per le altre", '
              '"explanation": "spiegazione breve", "topic": "argomento della domanda"}.\n\nMATERIALE:\n' + ctx)
    questions = validate_questions(parse_json_array(await ask([{"role": "user", "content": prompt}], json_mode=True)), b.topic or "Generale")
    if not questions:
        raise HTTPException(422, "Il modello non ha prodotto domande valide. Riprova o usa un modello più grande.")
    with db() as c:
        cur = c.execute("INSERT INTO tests(subject_id, topic, difficulty, questions) VALUES(?,?,?,?)",
                        (b.subject_id, b.topic, b.difficulty, json.dumps(questions, ensure_ascii=False)))
    return {"id": cur.lastrowid}


def public(q: dict) -> dict:  # nasconde le soluzioni finché il test non è consegnato
    return {k: v for k, v in q.items() if k not in ("answer", "explanation")}


@router.get("/{tid}")
def get_test(tid: int):
    with db() as c:
        r = c.execute("SELECT * FROM tests WHERE id=?", (tid,)).fetchone()
    if not r:
        raise HTTPException(404, "Test non trovato.")
    return {**dict(r), "questions": [public(q) for q in json.loads(r["questions"])]}


@router.get("")
def list_tests(subject_id: int | None = None):
    sql = ("SELECT t.id, t.topic, t.difficulty, t.created_at, s.name AS subject_name, "
           "(SELECT score_pct FROM test_attempts WHERE test_id=t.id ORDER BY id DESC LIMIT 1) AS last_pct "
           "FROM tests t LEFT JOIN subjects s ON s.id=t.subject_id")
    with db() as c:
        rows = c.execute(sql + (" WHERE t.subject_id=?" if subject_id else "") + " ORDER BY t.id DESC",
                         [subject_id] if subject_id else [])
        return [dict(r) for r in rows]


class SubmitIn(BaseModel):
    answers: dict[str, str]


@router.post("/{tid}/submit")
async def submit(tid: int, b: SubmitIn):
    with db() as c:
        t = c.execute("SELECT * FROM tests WHERE id=?", (tid,)).fetchone()
    if not t:
        raise HTTPException(404, "Test non trovato.")
    qs = json.loads(t["questions"])
    results, to_eval = [], []
    for i, q in enumerate(qs):
        given = b.answers.get(str(i), "")
        r = {"index": i, "type": q["type"], "topic": q["topic"], "given": given, "correct_answer": q["answer"],
             "explanation": q["explanation"], "feedback": ""}
        if q["type"] in ("multipla", "vero_falso"):
            r["score"] = grade_closed(q, given)
        elif not given.strip():
            r["score"] = 0.0
            r["feedback"] = "Nessuna risposta."
        else:
            r["score"] = None
            to_eval.append(i)
        results.append(r)

    if to_eval:  # valutazione AI con criteri espliciti, in una sola richiesta
        items = "\n".join(f"{i}. Domanda: {qs[i]['question']}\n   Riferimento: {qs[i]['answer']}\n   Risposta dello studente: {results[i]['given']}"
                          for i in to_eval)
        prompt = ("Valuta le risposte di uno studente. Criteri: correttezza concettuale, completezza, uso corretto dei termini. "
                  "NON penalizzare risposte corrette formulate in modo diverso dal riferimento. Assegna un punteggio da 0 a 1 "
                  "(0.5 = parzialmente corretta) e un breve feedback in italiano che spieghi l'errore. Rispondi SOLO con un array "
                  'JSON: {"valutazioni": [{"i": numero, "score": 0..1, "feedback": "..."}]}.\n\n' + items)
        evals = parse_json_array(await ask([{"role": "user", "content": prompt}], json_mode=True)) or []
        by = {}
        for e in evals:
            try:
                by[int(e["i"])] = (max(0.0, min(1.0, float(e["score"]))), fix_latex(str(e.get("feedback", ""))))
            except (KeyError, ValueError, TypeError):
                pass
        missing = [i for i in to_eval if i not in by]
        if missing:  # niente voti inventati: il test non viene salvato
            raise HTTPException(422, "Il modello non ha valutato tutte le risposte aperte. Riprova a consegnare.")
        for i in to_eval:
            results[i]["score"], results[i]["feedback"] = by[i]

    pct = round(100 * sum(r["score"] for r in results) / len(results), 1)
    grade = round(30 * pct / 100, 1)
    weak = sorted({r["topic"] for r in results if r["score"] < 0.6})
    with db() as c:
        cur = c.execute("INSERT INTO test_attempts(test_id, answers, score_pct, grade_30, weak_topics) VALUES(?,?,?,?,?)",
                        (tid, json.dumps(results, ensure_ascii=False), pct, grade, json.dumps(weak, ensure_ascii=False)))
        for topic, state in topic_states(results).items():
            set_state(c, t["subject_id"], topic, state, allow_downgrade=True)
    return {"attempt_id": cur.lastrowid, "score_pct": pct, "grade_30": grade, "level": level(pct),
            "weak_topics": weak, "results": results,
            "note": "Il voto in trentesimi è indicativo: percentuale × 30."}
