from fastapi import APIRouter
from pydantic import BaseModel
from .database import db

router = APIRouter(prefix="/api/profile")


class ProfileIn(BaseModel):
    name: str = ""
    info: str = ""


@router.get("")
def get_profile():
    with db() as c:
        r = c.execute("SELECT name, info FROM profile WHERE id=1").fetchone()
    return {"name": (r["name"] if r else "") or "", "info": (r["info"] if r else "") or ""}


@router.put("")
def save_profile(p: ProfileIn):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO profile(id, name, info) VALUES(1, ?, ?)", (p.name.strip()[:60], p.info.strip()[:500]))
    return get_profile()
