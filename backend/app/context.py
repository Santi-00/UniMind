"""Utilità condivise da lezioni, test e piani: recupero del materiale e chiamate AI con errori gestiti."""
import json
import re
from fastapi import HTTPException
from .ai_service import ai, AIUnavailable, ModelMissing
from .database import db


async def ask(messages: list[dict], json_mode: bool = False) -> str:
    try:
        return await ai.chat(messages, json_mode=json_mode)
    except AIUnavailable as e:
        raise HTTPException(503, str(e))
    except ModelMissing as e:
        raise HTTPException(409, str(e))


_BAD_ESC = re.compile(r'\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})')


def _loads(s: str):
    """json.loads tollerante: le formule LaTeX (\\alpha, \\sum...) contengono backslash non validi in JSON."""
    try:
        return json.loads(s)
    except ValueError:
        return json.loads(_BAD_ESC.sub(r"\\\\", s))


def fix_latex(s: str) -> str:
    """Ripara i comandi LaTeX 'mangiati' dal JSON: \\frac -> form feed, \\theta -> tab, \\beta -> backspace, ecc."""
    s = s.replace("\x0c", "\\f").replace("\x08", "\\b").replace("\t", "\\t").replace("\r", "\\r")
    return re.sub(r"\n(?=(?:eq|abla|otin|ot|u|e|i|mid|leq|geq|sim|cong|rightarrow|parallel|less|gtr)\b)", r"\\n", s)


def parse_json_array(raw: str):
    """Accetta un array, oppure un oggetto che contiene un array (es. {"capitoli": [...]}), anche con testo attorno."""
    try:
        v = _loads(raw)
        if isinstance(v, dict):
            v = next((x for x in v.values() if isinstance(x, list)), None)
        if isinstance(v, list):
            return v
    except ValueError:
        pass
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return None
    try:
        v = _loads(m.group(0))
        return v if isinstance(v, list) else None
    except ValueError:
        return None


async def get_context(subject_id: int | None, document_id: int | None, topic: str | None,
                      max_chars: int = 12000) -> str:
    text = ""
    if topic and not document_id:
        try:  # ricerca semantica, se RAG e embedding sono disponibili
            from .rag import search
            res = await search(topic, subject_id, k=8)
            text = "\n\n".join(f"({r['filename']}, pag. {r['page']}) {r['text']}" for r in res)
        except (AIUnavailable, ModelMissing, ImportError):
            text = ""
    if not text:
        sql = ("SELECT k.text, k.page, d.filename FROM chunks k JOIN documents d ON d.id=k.document_id WHERE ")
        args: list = []
        if document_id:
            sql += "k.document_id=?"; args.append(document_id)
        elif subject_id:
            sql += "k.subject_id=?"; args.append(subject_id)
        else:
            sql += "1=1"
        with db() as c:
            rows = [dict(r) for r in c.execute(sql + " ORDER BY k.id", args)]
            if topic:
                words = [w for w in re.findall(r"\w{4,}", topic.lower())]
                hits = [r for r in rows if any(w in r["text"].lower() for w in words)]
                rows = hits or rows
        out, size = [], 0
        for r in rows:
            piece = f"({r['filename']}, pag. {r['page']}) {r['text']}"
            if size + len(piece) > max_chars:
                break
            out.append(piece); size += len(piece)
        text = "\n\n".join(out)
    if not text.strip():
        raise HTTPException(409, "Non ci sono materiali analizzati per questa richiesta. "
                                 "Carica un documento in Materiali e attendi lo stato 'analizzato'.")
    return text
