"""週間スケジュール API（従業員×日付×午前/午後）"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.models import get_db, TeamSchedule
from datetime import date as _date

router = APIRouter()


def _dict(s: TeamSchedule):
    return {
        "id": str(s.id), "user_id": s.user_id, "full_name": s.full_name,
        "date": str(s.date) if s.date else None, "slot": s.slot,
        "title": s.title, "color": s.color,
    }


@router.get("")
@router.get("/")
def list_schedules(start: str = Query(None), end: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(TeamSchedule)
    if start:
        q = q.filter(TeamSchedule.date >= _date.fromisoformat(start))
    if end:
        q = q.filter(TeamSchedule.date <= _date.fromisoformat(end))
    return [_dict(s) for s in q.order_by(TeamSchedule.date, TeamSchedule.slot).all()]


@router.post("")
@router.post("/")
def create_schedule(data: dict, db: Session = Depends(get_db)):
    if not data.get("date") or not data.get("slot"):
        raise HTTPException(400, "日付と時間帯は必須です")
    s = TeamSchedule(
        user_id=str(data.get("user_id") or ""),
        full_name=data.get("full_name"),
        date=_date.fromisoformat(data["date"]),
        slot=data["slot"], title=data.get("title"), color=data.get("color"),
    )
    db.add(s); db.commit(); db.refresh(s)
    return _dict(s)


@router.put("/{schedule_id}")
def update_schedule(schedule_id: str, data: dict, db: Session = Depends(get_db)):
    s = db.query(TeamSchedule).filter(TeamSchedule.id == schedule_id).first()
    if not s: raise HTTPException(404)
    for k in ["user_id", "full_name", "slot", "title", "color"]:
        if k in data: setattr(s, k, data[k])
    if "date" in data and data["date"]:
        s.date = _date.fromisoformat(data["date"])
    db.commit(); db.refresh(s)
    return _dict(s)


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    s = db.query(TeamSchedule).filter(TeamSchedule.id == schedule_id).first()
    if not s: raise HTTPException(404)
    db.delete(s); db.commit()
    return {"ok": True}
