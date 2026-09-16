"""週間スケジュール API（従業員×日付×午前/午後）

1行 = 1人 × 1日 × 午前または午後。複数参加者の予定は人数分の行になるため、
同時に作った行へ同じ group_id を持たせ、1件の変更を全員分へ反映できるようにしている。
"""
import uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.models import get_db, TeamSchedule
from datetime import date as _date

router = APIRouter()


def _dict(s: TeamSchedule):
    return {
        "id": str(s.id), "user_id": s.user_id, "full_name": s.full_name,
        "date": str(s.date) if s.date else None, "slot": s.slot,
        "title": s.title, "color": s.color, "group_id": s.group_id,
    }


def _group_members(db: Session, s: TeamSchedule):
    """同じ予定の行（自分を含む）。

    group_id があればそれで束ねる。無い行（この仕組みより前に作った予定）は
    「同じ日・同じ時間帯・同じ内容」を同じ予定とみなす。
    """
    if s.group_id:
        return db.query(TeamSchedule).filter(TeamSchedule.group_id == s.group_id).all()
    return db.query(TeamSchedule).filter(
        TeamSchedule.date == s.date, TeamSchedule.slot == s.slot,
        TeamSchedule.title == s.title,
    ).all()


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
        group_id=data.get("group_id") or str(_uuid.uuid4()),
    )
    db.add(s); db.commit(); db.refresh(s)
    return _dict(s)


@router.put("/{schedule_id}")
def update_schedule(schedule_id: str, data: dict, scope: str = Query("one"),
                    db: Session = Depends(get_db)):
    """予定を変更する。

    scope=group を付けると、同じ予定の参加者全員分をまとめて変更する
    （内容・色・日付・時間帯）。時間帯は am / pm のほか all（終日）を指定でき、
    終日では参加者ごとに午前・午後の行を揃える。
    """
    s = db.query(TeamSchedule).filter(TeamSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(404)
    if scope != "group":
        for k in ["user_id", "full_name", "slot", "title", "color"]:
            if k in data:
                setattr(s, k, data[k])
        if data.get("date"):
            s.date = _date.fromisoformat(data["date"])
        db.commit(); db.refresh(s)
        return _dict(s)

    members = _group_members(db, s)
    gid = s.group_id or str(_uuid.uuid4())
    new_date = _date.fromisoformat(data["date"]) if data.get("date") else s.date
    new_slot = data.get("slot") or s.slot

    for m in members:
        m.group_id = gid
        m.date = new_date
        if "title" in data:
            m.title = data["title"]
        if "color" in data:
            m.color = data["color"]

    if new_slot in ("am", "pm"):
        # 全員を同じ時間帯へ。同じ人が同じ日時で重複したら1行に寄せる
        seen, dups = set(), []
        for m in members:
            key = (m.user_id, str(m.date), new_slot)
            if key in seen:
                dups.append(m)
            else:
                seen.add(key)
                m.slot = new_slot
        for m in dups:
            db.delete(m)
        members = [m for m in members if m not in dups]
    elif new_slot == "all":
        # 参加者ごとに午前・午後を揃える（足りない側を作る）
        by_user = {}
        for m in members:
            by_user.setdefault(m.user_id, []).append(m)
        for uid, rows in by_user.items():
            have = {r.slot for r in rows}
            for sl in ("am", "pm"):
                if sl not in have:
                    src = rows[0]
                    db.add(TeamSchedule(
                        user_id=src.user_id, full_name=src.full_name, date=new_date,
                        slot=sl, title=src.title, color=src.color, group_id=gid,
                    ))
    db.commit()
    return {"ok": True, "updated": len(members), "group_id": gid}


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str, scope: str = Query("one"), db: Session = Depends(get_db)):
    """予定を削除する。scope=group で参加者全員分を削除する"""
    s = db.query(TeamSchedule).filter(TeamSchedule.id == schedule_id).first()
    if not s:
        raise HTTPException(404)
    targets = _group_members(db, s) if scope == "group" else [s]
    n = len(targets)
    for t in targets:
        db.delete(t)
    db.commit()
    return {"ok": True, "deleted": n}


@router.get("/setup")
def setup_schedule(db: Session = Depends(get_db)):
    """group_id 列の追加（冪等）。既存の予定は日付・時間帯・内容が同じものを同じ予定とみなす"""
    from sqlalchemy import text
    try:
        db.execute(text("ALTER TABLE team_schedules ADD COLUMN IF NOT EXISTS group_id VARCHAR(64)"))
        db.commit()
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}
    return {"ok": True, "column": "group_id"}
