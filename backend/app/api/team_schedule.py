"""週間スケジュール API（従業員×日付×午前/午後）

1行 = 1人 × 1日 × 午前または午後。複数参加者の予定は人数分の行になるため、
同時に作った行へ同じ group_id を持たせ、1件の変更を全員分へ反映できるようにしている。
"""
import os
import uuid as _uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.models import get_db, TeamSchedule
from datetime import (date as _date, datetime as _datetime, timedelta as _td,
                      timezone as _tz)

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


# =============================================
# 今週の予定まとめ（月曜 6:00 に全ユーザーへメール）
# =============================================
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
SLOT_LABEL = {"am": "午前", "pm": "午後"}
JST = _tz(_td(hours=9))


def week_range(d: _date):
    """その日を含む週（月曜〜日曜）"""
    monday = d - _td(days=d.weekday())
    return monday, monday + _td(days=6)


def _fmt_day(d: _date) -> str:
    return f"{d.month}/{d.day}({WEEKDAYS[d.weekday()]})"


def _slot_of(rows) -> str:
    """午前・午後が揃っていれば終日と書く"""
    slots = {r.slot for r in rows}
    return "終日" if slots >= {"am", "pm"} else SLOT_LABEL.get(rows[0].slot, rows[0].slot)


def _grouped(rows):
    """同じ予定（group_id、無ければ日付＋時間帯＋内容）でまとめる"""
    groups = {}
    for r in rows:
        key = r.group_id or f"{r.date}|{r.slot}|{r.title}"
        groups.setdefault(key, []).append(r)
    return groups


def build_digest(db: Session, user, start: _date, end: _date) -> str:
    """1人分のメール本文。本人の予定と、全員の予定を載せる"""
    from app.mailer import app_base_url
    rows = db.query(TeamSchedule).filter(
        TeamSchedule.date >= start, TeamSchedule.date <= end
    ).order_by(TeamSchedule.date, TeamSchedule.slot).all()

    # 参加者名の索引（同じ予定に誰がいるか）
    members = {k: sorted({r.full_name or "—" for r in v}) for k, v in _grouped(rows).items()}

    lines = [f"{user.full_name} 様", "",
             f"今週（{_fmt_day(start)} 〜 {_fmt_day(end)}）の予定をお知らせします。", "",
             "■ あなたの予定"]
    mine = [r for r in rows if str(r.user_id) == str(user.id)]
    if not mine:
        lines.append("　予定はありません")
    else:
        seen = set()
        for r in mine:
            key = r.group_id or f"{r.date}|{r.slot}|{r.title}"
            same = [x for x in mine if (x.group_id or f"{x.date}|{x.slot}|{x.title}") == key]
            dkey = (r.date, key)
            if dkey in seen:
                continue
            seen.add(dkey)
            others = [n for n in members.get(key, []) if n != (user.full_name or "")]
            with_who = f"（{'、'.join(others)} と）" if others else ""
            lines.append(f"　{_fmt_day(r.date)} {_slot_of(same):<2} {r.title or ''}{with_who}")

    lines += ["", "■ 全員の予定"]
    by_date = {}
    for r in rows:
        by_date.setdefault(r.date, []).append(r)
    if not by_date:
        lines.append("　登録された予定はありません")
    for d in sorted(by_date):
        lines.append(f"　{_fmt_day(d)}")
        for slot in ("am", "pm"):
            srows = [r for r in by_date[d] if r.slot == slot]
            if not srows:
                continue
            items = []
            for key, g in _grouped(srows).items():
                names = "、".join(sorted({r.full_name or "—" for r in g}))
                items.append(f"{names}: {g[0].title or ''}")
            lines.append(f"　　{SLOT_LABEL[slot]}　" + " ／ ".join(items))
    lines += ["", f"▼ スケジュール画面", f"{app_base_url()}/schedule", "",
              "--", "井上電設 販売管理システム（自動送信）"]
    return "\n".join(lines)


def send_weekly_digest(db: Session, target: _date = None, force: bool = False) -> dict:
    """今週の予定をメール登録のある全ユーザーへ送る。

    同じ週に二重送信しないよう、送信済みの週を記録しておく（force=True で無視）。
    """
    from app.mailer import send_mail, mail_configured
    from app.db.models import User, FormDocument
    today = target or _datetime.now(JST).date()
    start, end = week_range(today)
    week_key = f"{start.isoformat()}"
    doc = db.query(FormDocument).filter(
        FormDocument.form_type == "schedule-digest", FormDocument.entity_id == week_key).first()
    if doc and not force:
        return {"ok": True, "skipped": "この週は送信済みです", "week": week_key,
                "sent_at": (doc.data_json or {}).get("sent_at")}
    if not mail_configured():
        return {"ok": False, "error": "メール未設定（MAIL_FROM / MAIL_APP_PASSWORD）", "week": week_key}

    users = db.query(User).filter(User.is_active == True, User.email.isnot(None)).all()  # noqa: E712
    sent, failed = [], []
    subject = f"【今週の予定】{_fmt_day(start)}〜{_fmt_day(end)}"
    for u in users:
        if not (u.email or "").strip():
            continue
        r = send_mail(u.email, subject, build_digest(db, u, start, end))
        (sent if r.get("sent") else failed).append(
            u.email if r.get("sent") else f"{u.email}: {r.get('reason')}")
    if not doc:
        doc = FormDocument(form_type="schedule-digest", entity_id=week_key)
        db.add(doc)
    doc.data_json = {"sent_at": _datetime.now(JST).isoformat(), "sent": len(sent), "failed": failed}
    db.commit()
    return {"ok": True, "week": week_key, "sent": len(sent), "failed": failed}


@router.get("/weekly-digest/preview")
def preview_weekly_digest(email: str = Query(None), date: str = Query(None),
                          db: Session = Depends(get_db)):
    """送信せずに本文を確認する。email を省略すると先頭のユーザーで作る"""
    from app.db.models import User
    d = _date.fromisoformat(date) if date else _datetime.now(JST).date()
    start, end = week_range(d)
    q = db.query(User).filter(User.is_active == True)  # noqa: E712
    u = q.filter(User.email == email).first() if email else q.first()
    if not u:
        raise HTTPException(404, "ユーザーが見つかりません")
    return {"to": u.email, "subject": f"【今週の予定】{_fmt_day(start)}〜{_fmt_day(end)}",
            "body": build_digest(db, u, start, end)}


@router.post("/weekly-digest/send")
def post_weekly_digest(force: bool = Query(False), date: str = Query(None),
                       db: Session = Depends(get_db)):
    """今週の予定メールを送る（月曜6:00の自動送信と同じ処理）。

    Render の Cron Job からこのURLを叩く運用もできる。同じ週の二重送信は防いでいる。
    """
    d = _date.fromisoformat(date) if date else None
    return send_weekly_digest(db, target=d, force=force)


@router.get("/weekly-digest/status")
def weekly_digest_status(db: Session = Depends(get_db)):
    """自動送信の状態と、直近の送信記録"""
    from app.db.models import FormDocument
    rows = db.query(FormDocument).filter(FormDocument.form_type == "schedule-digest") \
        .order_by(FormDocument.entity_id.desc()).limit(5).all()
    from app.mailer import mail_configured
    return {
        "enabled": os.getenv("SCHEDULE_DIGEST_ENABLED", "1") != "0",
        "mail_configured": mail_configured(),
        "now_jst": _datetime.now(JST).isoformat(),
        "history": [{"week_start": r.entity_id, **(r.data_json or {})} for r in rows],
    }


def start_digest_scheduler():
    """月曜 6:00（日本時間）に今週の予定メールを送る常駐スレッドを起動する。

    外部のジョブ機能に頼らず、アプリが動いていれば送れるようにしている。
    サーバ再起動や多重起動があっても、送信済みの週は記録で弾くため二重送信しない。
    SCHEDULE_DIGEST_ENABLED=0 で止められる。
    """
    import threading
    import time

    if os.getenv("SCHEDULE_DIGEST_ENABLED", "1") == "0":
        print("[schedule] 週次メールの自動送信は無効です（SCHEDULE_DIGEST_ENABLED=0）")
        return

    def loop():
        from app.db.models import SessionLocal
        while True:
            try:
                now = _datetime.now(JST)
                # 月曜の 6:00〜6:59。送信済みの週は send_weekly_digest 側で弾く
                if now.weekday() == 0 and now.hour == 6:
                    db = SessionLocal()
                    try:
                        r = send_weekly_digest(db)
                        if not r.get("skipped"):
                            print(f"[schedule] 今週の予定メール: {r}")
                    finally:
                        db.close()
            except Exception as e:  # noqa: BLE001  常駐スレッドは落とさない
                print(f"[schedule] 週次メールの送信に失敗: {e}")
            time.sleep(600)   # 10分ごとに時刻を確認

    threading.Thread(target=loop, name="weekly-digest", daemon=True).start()
    print("[schedule] 週次メールの自動送信を開始しました（月曜 6:00 JST）")


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
