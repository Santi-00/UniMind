from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from .context import ask, get_context
from .database import db
from .progress import set_state

router = APIRouter(prefix="/api/lessons")

PROMPT = """Sei un professore universitario. Scrivi in italiano una lezione completa a partire dal MATERIALE qui sotto.
Non limitarti a riassumere: insegna, spiegando gradualmente anche gli argomenti difficili.
Struttura obbligatoria (usa queste intestazioni, nell'ordine):
# <Titolo della lezione>
## Introduzione
## Spiegazione teorica
## Definizioni
## Formule
## Esempi pratici
## Applicazioni
## Errori comuni
## Riepilogo
## Domande di verifica
Regole: le informazioni che provengono dal materiale vanno tenute distinte da quelle che aggiungi tu; ogni paragrafo
tuo, non presente nel materiale, deve iniziare con 'Approfondimento AI:'. Se una sezione non ha contenuto nel materiale
(ad esempio le formule) scrivi 'Non presenti nel materiale.' seguito, se utile, da un 'Approfondimento AI:'. Se
l'argomento è di programmazione includi codice commentato. Scrivi OGNI formula matematica in LaTeX: nel testo tra $...$ (es. $x^2$), in evidenza su una riga propria tra $$...$$.
Non usare altri delimitatori e non scrivere formule in testo semplice. Non inventare riferimenti o fonti.
{focus}
MATERIALE:
{context}"""


class GenIn(BaseModel):
    subject_id: int
    document_id: int | None = None
    topic: str | None = None


class LessonPatch(BaseModel):
    title: str | None = None
    content: str | None = None
    notes: str | None = None


async def build(subject_id: int, document_id: int | None, topic: str | None) -> tuple[str, str]:
    ctx = await get_context(subject_id, document_id, topic)
    focus = f"Argomento richiesto: {topic}." if topic else "Scegli tu l'argomento principale del materiale."
    content = await ask([{"role": "user", "content": PROMPT.format(focus=focus, context=ctx)}])
    first = next((l for l in content.splitlines() if l.startswith("# ")), "")
    title = first[2:].strip() or topic or "Lezione"
    return title[:150], content


@router.post("/generate")
async def generate(b: GenIn):
    title, content = await build(b.subject_id, b.document_id, b.topic)
    with db() as c:
        cur = c.execute("INSERT INTO lessons(subject_id, document_id, title, content) VALUES(?,?,?,?)",
                        (b.subject_id, b.document_id, title, content))
        set_state(c, b.subject_id, title, "caricato")
        return {"id": cur.lastrowid, "title": title}


@router.get("")
def list_lessons(subject_id: int | None = None):
    sql = ("SELECT l.id, l.subject_id, l.title, l.studied, l.created_at, s.name AS subject_name, s.color AS subject_color "
           "FROM lessons l LEFT JOIN subjects s ON s.id=l.subject_id")
    with db() as c:
        rows = c.execute(sql + (" WHERE l.subject_id=?" if subject_id else "") + " ORDER BY l.id DESC",
                         [subject_id] if subject_id else [])
        return [dict(r) for r in rows]


@router.get("/{lid}")
def get_lesson(lid: int):
    with db() as c:
        r = c.execute("SELECT * FROM lessons WHERE id=?", (lid,)).fetchone()
    if not r:
        raise HTTPException(404, "Lezione non trovata.")
    return dict(r)


@router.put("/{lid}")
def update_lesson(lid: int, p: LessonPatch):
    with db() as c:
        for col in ("title", "content", "notes"):
            v = getattr(p, col)
            if v is not None:
                c.execute(f"UPDATE lessons SET {col}=? WHERE id=?", (v, lid))
    return {"id": lid}


@router.post("/{lid}/studied")
def mark_studied(lid: int, studied: bool = True):
    with db() as c:
        r = c.execute("SELECT subject_id, title FROM lessons WHERE id=?", (lid,)).fetchone()
        if not r:
            raise HTTPException(404, "Lezione non trovata.")
        c.execute("UPDATE lessons SET studied=? WHERE id=?", (1 if studied else 0, lid))
        if studied:
            set_state(c, r["subject_id"], r["title"], "studiato")
    return {"id": lid, "studied": studied}


@router.post("/{lid}/regenerate")
async def regenerate(lid: int):
    with db() as c:
        r = c.execute("SELECT * FROM lessons WHERE id=?", (lid,)).fetchone()
    if not r:
        raise HTTPException(404, "Lezione non trovata.")
    title, content = await build(r["subject_id"], r["document_id"], r["title"])
    with db() as c:  # gli appunti personali restano
        c.execute("UPDATE lessons SET title=?, content=?, studied=0 WHERE id=?", (title, content, lid))
    return {"id": lid, "title": title}


@router.delete("/{lid}")
def delete_lesson(lid: int):
    with db() as c:
        c.execute("DELETE FROM lessons WHERE id=?", (lid,))
    return {"deleted": lid}


async def build_for_chapter(chapter_id: int) -> dict:
    with db() as c:
        ch = c.execute("SELECT ch.id, ch.title, ch.document_id, d.subject_id, d.filename FROM chapters ch "
                       "JOIN documents d ON d.id=ch.document_id WHERE ch.id=?", (chapter_id,)).fetchone()
        if not ch:
            raise HTTPException(404, "Capitolo non trovato.")
        rows = c.execute("SELECT text, page FROM chunks WHERE chapter_id=? ORDER BY id", (chapter_id,)).fetchall()
    out, size = [], 0
    for r in rows:
        piece = f"({ch['filename']}, pag. {r['page']}) {r['text']}"
        if size + len(piece) > 12000:
            break
        out.append(piece); size += len(piece)
    if not out:
        raise HTTPException(409, "Il capitolo non ha testo associato: rifai 'Riconosci capitoli'.")
    content = await ask([{"role": "user", "content": PROMPT.format(
        focus=f"Capitolo da spiegare: {ch['title']}.", context="\n\n".join(out))}])
    first = next((l for l in content.splitlines() if l.startswith("# ")), "")
    return {"subject_id": ch["subject_id"], "document_id": ch["document_id"],
            "title": (first[2:].strip() or ch["title"])[:150], "content": content}
