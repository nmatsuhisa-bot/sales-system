# -*- coding: utf-8 -*-
"""工場機械・図面管理 API

docs/工場機械・図面管理_要件整理と実装方針_20260915.md
  1. 機械マスタ（管理ID = 機械一覧表の管理番号）
  2. 固定資産台帳の期ごとの取込と、機械との紐付け（多対多）・突合
  3. 図面（画像）上の配置。ドラッグごとの下書き（eq_moves）→「確定」で有効期間付き配置（eq_placements）に反映
     過去時点の配置は as_of で引ける
既存テーブルは参照も変更もしない（users のログインユーザー名を記録するのみ）。
管理者専用（ルーター全体に require_admin。画面側も AdminRoute で二重に制限）。
"""
from __future__ import annotations
import csv
import hashlib
import io
import re
import uuid
import datetime as dt
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_, func as sqlfunc

from app.db.models import (
    get_db, User,
    EqSite, EqDrawing, EqMachine, EqAsset, EqMachineAsset, EqCommit, EqPlacement, EqMove,
)
from app.api.auth import get_current_user, require_admin

router = APIRouter(dependencies=[Depends(require_admin)])

EQ_TABLES = (EqSite, EqDrawing, EqMachine, EqAsset, EqMachineAsset, EqCommit, EqPlacement, EqMove)

# 勘定科目のうち機械の可能性があるもの（それ以外は突合の対象外）
MACHINE_ACCOUNTS = {"機械装置", "工具器具備品", "一括償却資産", "リース資産"}
# 台帳の資産名先頭に付く工場プレフィックス（SKF-07 = 桜田 + F-07, KK-14 = 小牧 + K-14, D3B-26 = 第3倉庫 + B-26）
SITE_PREFIXES = ("SK", "D3", "K", "F", "H", "S")
CODE_RE = re.compile(r"^(S1|S2|SK|SKW|SW|SA|SR|F|FW|FA|B|BW|K|KW|KA|H|施)-?(\d{1,3})([a-z]?)$")
LEAD_RE = re.compile(r"^([A-Z0-9]{1,5}-[A-Z]?\d{1,3}[a-z]?)")
LINK_TYPES = ("本体", "付帯工事", "移設費", "親資産に含む", "リース", "その他")
MOVE_KINDS = ("place", "move", "remove")

DEFAULT_SITES = [
    ("sakurada_n", "桜田北"), ("sakurada_s", "桜田南"), ("komaki", "小牧"), ("sawashita", "沢下"),
    ("fukue", "福江"), ("daisan", "第3倉庫"), ("honsha", "本社"), ("daini", "第2倉庫"),
]


# ------------------------------------------------------------
# 共通
# ------------------------------------------------------------
def _uuid(v, required: bool = True):
    if v in (None, ""):
        if required:
            raise HTTPException(400, "ID が指定されていません")
        return None
    try:
        return uuid.UUID(str(v))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(400, f"ID の形式が不正です: {v}")


def _f(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return v


def _iso(v: Optional[dt.datetime]) -> Optional[str]:
    """DB の naive UTC を ISO 文字列（末尾 Z）にして返す。画面側でローカル時刻に直す"""
    if v is None:
        return None
    return v.replace(microsecond=0).isoformat() + "Z"


def _now() -> dt.datetime:
    return dt.datetime.utcnow()


def _date(v) -> Optional[dt.date]:
    if v in (None, ""):
        return None
    if isinstance(v, dt.date):
        return v
    s = str(v).strip().replace("/", "-")
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        return None


def _to_int(s) -> Optional[int]:
    """'5,800,000' / '資産 260,000' / '355,000←' などから最初の数値を取る。無ければ None"""
    if s is None:
        return None
    m = re.search(r"\d[\d,]*", str(s))
    if not m:
        return None
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _norm_code(code: str) -> str:
    """管理番号の表記ゆれを揃える（全角→半角、前後空白、ハイフン統一）。S1-13 のような形式はそのまま"""
    s = (code or "").strip().replace("－", "-").replace("Ｆ", "F").replace("　", "")
    m = CODE_RE.match(s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}{m.group(3)}"
    return s


def _asset_code_candidates(name: str) -> list:
    """台帳の資産名先頭から機械番号の候補を順に返す。'SKF-07 施盤' → ['F-07'], 'K-36 アマダ' → ['K-36']"""
    s = (name or "").strip().replace("－", "-").replace("Ｆ", "F")
    m = LEAD_RE.match(s)
    if not m:
        return []
    tok = m.group(1)
    out = []

    def add(t):
        mm = CODE_RE.match(t)
        if mm:
            c = f"{mm.group(1)}-{int(mm.group(2)):02d}{mm.group(3)}"
            if c not in out:
                out.append(c)
    add(tok)
    for p in SITE_PREFIXES:
        if tok.startswith(p) and len(tok) > len(p):
            add(tok[len(p):].lstrip("-"))
    return out


def _decode_csv(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise HTTPException(400, "CSV の文字コードを判定できません（UTF-8 か Shift_JIS にしてください）")


def _machine_dict(m: EqMachine, links: Optional[list] = None, placement: Optional[dict] = None) -> dict:
    d = {
        "id": str(m.id), "code": m.code, "name": m.name, "category1": m.category1, "category2": m.category2,
        "maker": m.maker, "dealer": m.dealer, "model": m.model, "made_year": m.made_year,
        "electric_spec": m.electric_spec, "notes": m.notes, "work_content": m.work_content,
        "legal_inspection": m.legal_inspection, "inspector": m.inspector, "repair_log": m.repair_log,
        "list_site": m.list_site, "price": _f(m.price), "price_raw": m.price_raw,
        "asset_flag_raw": m.asset_flag_raw, "depreciation_raw": m.depreciation_raw, "status": m.status,
        "extra_rows": m.extra_rows or [], "sort_order": m.sort_order,
    }
    if links is not None:
        d["links"] = links
    if placement is not None or links is not None:
        d["placement"] = placement
    return d


def _asset_dict(a: EqAsset) -> dict:
    return {
        "id": str(a.id), "period": a.period, "asset_key": a.asset_key, "asset_no": a.asset_no, "name": a.name,
        "account": a.account, "acquired_on": a.acquired_on.isoformat() if a.acquired_on else None,
        "price": _f(a.price), "ending_balance": _f(a.ending_balance), "site_note": a.site_note,
        "remarks": a.remarks, "department": a.department, "useful_life": a.useful_life,
        "disposed_on": a.disposed_on.isoformat() if a.disposed_on else None,
        "sold_on": a.sold_on.isoformat() if a.sold_on else None,
        "is_machine_account": a.account in MACHINE_ACCOUNTS,
    }


def _link_dict(l: EqMachineAsset, asset: Optional[EqAsset] = None, machine: Optional[EqMachine] = None) -> dict:
    d = {"id": str(l.id), "machine_id": str(l.machine_id), "asset_key": l.asset_key, "link_type": l.link_type,
         "confidence": l.confidence, "note": l.note, "created_by": l.created_by, "created_at": _iso(l.created_at)}
    if asset is not None:
        d["asset"] = _asset_dict(asset)
    if machine is not None:
        d["machine_code"] = machine.code
        d["machine_name"] = machine.name
    return d


def _drawing_dict(d: EqDrawing) -> dict:
    return {
        "id": str(d.id), "site_id": str(d.site_id), "site_name": d.site.name if d.site else None, "name": d.name,
        "version_no": d.version_no, "width_px": d.width_px, "height_px": d.height_px,
        "has_original": d.original is not None, "source_filename": d.source_filename, "scale_note": d.scale_note,
        "valid_from": d.valid_from.isoformat() if d.valid_from else None, "is_active": d.is_active, "notes": d.notes,
        "updated_at": _iso(d.updated_at),
    }


def _latest_period(db: Session) -> Optional[str]:
    r = db.query(sqlfunc.max(EqAsset.period)).scalar()
    return r


def _period_or_latest(db: Session, period: Optional[str]) -> Optional[str]:
    return period or _latest_period(db)


# ------------------------------------------------------------
# セットアップ / 概要
# ------------------------------------------------------------
@router.get("/setup-tables")
def setup_tables(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """eq_* テーブルを作成し、拠点の初期値を投入する（冪等）"""
    from app.db.models import Base, engine
    Base.metadata.create_all(bind=engine, tables=[m.__table__ for m in EQ_TABLES])
    added = 0
    for i, (code, name) in enumerate(DEFAULT_SITES):
        if not db.query(EqSite).filter(EqSite.code == code).first():
            db.add(EqSite(code=code, name=name, sort_order=i))
            added += 1
    db.commit()
    return {"ok": True, "message": f"機械管理テーブルを作成しました（拠点 {added} 件を追加）"}


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    period = _latest_period(db)
    machines = db.query(sqlfunc.count(EqMachine.id)).scalar() or 0
    placed = db.query(sqlfunc.count(sqlfunc.distinct(EqPlacement.machine_id))).filter(EqPlacement.valid_to.is_(None)).scalar() or 0
    linked = db.query(sqlfunc.count(sqlfunc.distinct(EqMachineAsset.machine_id))).scalar() or 0
    assets = db.query(sqlfunc.count(EqAsset.id)).filter(EqAsset.period == period).scalar() if period else 0
    drawings = db.query(sqlfunc.count(EqDrawing.id)).filter(EqDrawing.is_active == True).scalar() or 0
    drafts = db.query(sqlfunc.count(EqMove.id)).filter(EqMove.commit_id.is_(None), EqMove.undone_at.is_(None)).scalar() or 0
    return {"machines": machines, "placed": placed, "linked": linked, "assets": assets or 0,
            "period": period, "drawings": drawings, "draft_moves": drafts}


# ------------------------------------------------------------
# 拠点
# ------------------------------------------------------------
@router.get("/sites")
def list_sites(db: Session = Depends(get_db)):
    rows = db.query(EqSite).order_by(EqSite.sort_order, EqSite.name).all()
    return [{"id": str(s.id), "code": s.code, "name": s.name, "sort_order": s.sort_order, "is_active": s.is_active} for s in rows]


@router.post("/sites")
def create_site(data: dict, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    code = (data.get("code") or "").strip()
    name = (data.get("name") or "").strip()
    if not code or not name:
        raise HTTPException(400, "コードと名称は必須です")
    if db.query(EqSite).filter(EqSite.code == code).first():
        raise HTTPException(400, f"拠点コード {code} は既に存在します")
    s = EqSite(code=code, name=name, sort_order=int(data.get("sort_order") or 0))
    db.add(s); db.commit()
    return {"id": str(s.id)}


@router.put("/sites/{site_id}")
def update_site(site_id: str, data: dict, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    s = db.query(EqSite).filter(EqSite.id == _uuid(site_id)).first()
    if not s:
        raise HTTPException(404, "拠点が見つかりません")
    for k in ("name", "sort_order", "is_active"):
        if k in data:
            setattr(s, k, data[k])
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------
# 図面
# ------------------------------------------------------------
def _png_size(data: bytes):
    """PNG / JPEG のヘッダから幅・高さを読む（Pillow を使わない）"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w = int.from_bytes(data[16:20], "big"); h = int.from_bytes(data[20:24], "big")
        return w, h, "image/png"
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                i += 1; continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2):
                h = int.from_bytes(data[i + 5:i + 7], "big"); w = int.from_bytes(data[i + 7:i + 9], "big")
                return w, h, "image/jpeg"
            seg = int.from_bytes(data[i + 2:i + 4], "big")
            i += 2 + seg
    raise HTTPException(400, "画像は PNG か JPEG にしてください")


@router.get("/drawings")
def list_drawings(site_id: Optional[str] = None, include_inactive: bool = False, db: Session = Depends(get_db)):
    q = db.query(EqDrawing)
    if site_id:
        q = q.filter(EqDrawing.site_id == _uuid(site_id))
    if not include_inactive:
        q = q.filter(EqDrawing.is_active == True)
    rows = q.order_by(EqDrawing.name).all()
    out = []
    for d in rows:
        x = _drawing_dict(d)
        x["placed_count"] = db.query(sqlfunc.count(EqPlacement.id)).filter(
            EqPlacement.drawing_id == d.id, EqPlacement.valid_to.is_(None)).scalar() or 0
        x["draft_count"] = db.query(sqlfunc.count(EqMove.id)).filter(
            EqMove.drawing_id == d.id, EqMove.commit_id.is_(None), EqMove.undone_at.is_(None)).scalar() or 0
        out.append(x)
    return out


@router.post("/drawings")
async def create_drawing(site_id: str = Form(...), name: str = Form(...), file: UploadFile = File(...),
                         original: Optional[UploadFile] = File(None), scale_note: Optional[str] = Form(None),
                         valid_from: Optional[str] = Form(None), notes: Optional[str] = Form(None),
                         db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """図面画像を登録する（背景用。番号入りの元図面は original に任意で）"""
    site = db.query(EqSite).filter(EqSite.id == _uuid(site_id)).first()
    if not site:
        raise HTTPException(404, "拠点が見つかりません")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(400, "画像は 15MB までにしてください")
    w, h, ctype = _png_size(data)
    d = EqDrawing(site_id=site.id, name=name.strip(), width_px=w, height_px=h, image=data, image_type=ctype,
                  source_filename=file.filename, scale_note=scale_note or None, valid_from=_date(valid_from),
                  notes=notes or None)
    if original is not None and original.filename:
        odata = await original.read()
        if odata:
            _, _, otype = _png_size(odata)
            d.original = odata; d.original_type = otype
    db.add(d); db.commit()
    return {"id": str(d.id), "width_px": w, "height_px": h}


@router.put("/drawings/{drawing_id}")
def update_drawing(drawing_id: str, data: dict, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    d = db.query(EqDrawing).filter(EqDrawing.id == _uuid(drawing_id)).first()
    if not d:
        raise HTTPException(404, "図面が見つかりません")
    for k in ("name", "scale_note", "notes", "is_active", "version_no"):
        if k in data:
            setattr(d, k, data[k])
    if "site_id" in data:
        d.site_id = _uuid(data["site_id"])
    if "valid_from" in data:
        d.valid_from = _date(data["valid_from"])
    db.commit()
    return {"ok": True}


@router.post("/drawings/{drawing_id}/image")
async def replace_drawing_image(drawing_id: str, file: Optional[UploadFile] = File(None),
                                original: Optional[UploadFile] = File(None),
                                db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """画像だけ差し替える（同じ縦横比の図面更新用。配置座標は比率なのでそのまま使える）"""
    d = db.query(EqDrawing).filter(EqDrawing.id == _uuid(drawing_id)).first()
    if not d:
        raise HTTPException(404, "図面が見つかりません")
    if file is not None and file.filename:
        data = await file.read()
        w, h, ctype = _png_size(data)
        d.image = data; d.image_type = ctype; d.width_px = w; d.height_px = h; d.source_filename = file.filename
        d.version_no = (d.version_no or 1) + 1
    if original is not None and original.filename:
        odata = await original.read()
        _, _, otype = _png_size(odata)
        d.original = odata; d.original_type = otype
    db.commit()
    return {"ok": True, "version_no": d.version_no}


@router.get("/drawings/{drawing_id}/image")
def drawing_image(drawing_id: str, original: bool = False, db: Session = Depends(get_db)):
    d = db.query(EqDrawing).filter(EqDrawing.id == _uuid(drawing_id)).first()
    if not d:
        raise HTTPException(404, "図面が見つかりません")
    if original:
        if d.original is None:
            raise HTTPException(404, "元図面は登録されていません")
        return Response(content=d.original, media_type=d.original_type or "image/png",
                        headers={"Cache-Control": "private, max-age=3600"})
    return Response(content=d.image, media_type=d.image_type or "image/png",
                    headers={"Cache-Control": "private, max-age=3600"})


@router.delete("/drawings/{drawing_id}")
def delete_drawing(drawing_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """配置・履歴が 1 件でもある図面は削除せず無効化にとどめる"""
    d = db.query(EqDrawing).filter(EqDrawing.id == _uuid(drawing_id)).first()
    if not d:
        raise HTTPException(404, "図面が見つかりません")
    used = db.query(sqlfunc.count(EqPlacement.id)).filter(EqPlacement.drawing_id == d.id).scalar() or 0
    used += db.query(sqlfunc.count(EqMove.id)).filter(EqMove.drawing_id == d.id).scalar() or 0
    if used:
        d.is_active = False
        db.commit()
        return {"ok": True, "message": "配置履歴があるため削除せず無効化しました"}
    db.delete(d); db.commit()
    return {"ok": True, "message": "削除しました"}


# ------------------------------------------------------------
# 機械マスタ
# ------------------------------------------------------------
def _current_placements(db: Session, machine_ids: Optional[list] = None) -> dict:
    """machine_id -> [{drawing_id, drawing_name, site_name, x, y, since}, ...] （現在の配置。
    全体図と詳細図のように同じ機械が複数の図面に載ることがあるため、図面ごとに独立して持つ）"""
    q = db.query(EqPlacement, EqDrawing).join(EqDrawing, EqDrawing.id == EqPlacement.drawing_id).filter(EqPlacement.valid_to.is_(None))
    if machine_ids is not None:
        q = q.filter(EqPlacement.machine_id.in_(machine_ids))
    out = {}
    for p, d in q.order_by(EqDrawing.name).all():
        out.setdefault(p.machine_id, []).append({"drawing_id": str(d.id), "drawing_name": d.name, "site_name": d.site.name if d.site else None,
                                                 "x": _f(p.x), "y": _f(p.y), "since": _iso(p.valid_from)})
    return out


@router.get("/machines")
def list_machines(search: Optional[str] = None, status: Optional[str] = None, list_site: Optional[str] = None,
                  link_state: Optional[str] = None, placed: Optional[str] = None, period: Optional[str] = None,
                  db: Session = Depends(get_db)):
    """機械一覧。link_state = linked / unlinked / candidate、placed = yes / no"""
    q = db.query(EqMachine)
    if search:
        s = f"%{search.strip()}%"
        q = q.filter(or_(EqMachine.code.ilike(s), EqMachine.name.ilike(s), EqMachine.model.ilike(s),
                         EqMachine.maker.ilike(s), EqMachine.notes.ilike(s)))
    if status:
        q = q.filter(EqMachine.status == status)
    if list_site:
        q = q.filter(EqMachine.list_site == list_site)
    rows = q.order_by(EqMachine.sort_order, EqMachine.code).all()
    period = _period_or_latest(db, period)
    assets = {a.asset_key: a for a in db.query(EqAsset).filter(EqAsset.period == period).all()} if period else {}
    links_by_m = {}
    for l in db.query(EqMachineAsset).all():
        links_by_m.setdefault(l.machine_id, []).append(_link_dict(l, assets.get(l.asset_key)))
    placements = _current_placements(db)
    out = []
    for m in rows:
        links = links_by_m.get(m.id, [])
        st = "unlinked" if not links else ("linked" if all(l["confidence"] == "confirmed" for l in links) else "candidate")
        if link_state and link_state != st:
            continue
        pl = placements.get(m.id) or []
        if placed == "yes" and not pl:
            continue
        if placed == "no" and pl:
            continue
        d = _machine_dict(m, links, pl[0] if pl else None)
        d["placements"] = pl
        d["link_state"] = st
        d["in_ledger"] = any(l["asset"] for l in links)
        out.append(d)
    return out


@router.get("/machines/{machine_id}")
def get_machine(machine_id: str, db: Session = Depends(get_db)):
    if _is_uuid(machine_id):
        m = db.query(EqMachine).filter(EqMachine.id == uuid.UUID(machine_id)).first()
    else:
        m = db.query(EqMachine).filter(EqMachine.code == _norm_code(machine_id)).first()
    if not m:
        raise HTTPException(404, "機械が見つかりません")
    period = _latest_period(db)
    assets = {a.asset_key: a for a in db.query(EqAsset).filter(EqAsset.period == period).all()} if period else {}
    links = [_link_dict(l, assets.get(l.asset_key)) for l in
             db.query(EqMachineAsset).filter(EqMachineAsset.machine_id == m.id).order_by(EqMachineAsset.created_at).all()]
    pl = _current_placements(db, [m.id]).get(m.id) or []
    d = _machine_dict(m, links, pl[0] if pl else None)
    d["placements"] = pl
    return d


def _is_uuid(v) -> bool:
    try:
        uuid.UUID(str(v)); return True
    except (ValueError, TypeError):
        return False


MACHINE_FIELDS = ("name", "category1", "category2", "maker", "dealer", "model", "made_year", "electric_spec", "notes",
                  "work_content", "legal_inspection", "inspector", "repair_log", "list_site", "price_raw",
                  "asset_flag_raw", "depreciation_raw", "status", "sort_order")


@router.post("/machines")
def create_machine(data: dict, db: Session = Depends(get_db)):
    code = _norm_code(data.get("code"))
    if not code or not (data.get("name") or "").strip():
        raise HTTPException(400, "管理IDと機器名は必須です")
    if db.query(EqMachine).filter(EqMachine.code == code).first():
        raise HTTPException(400, f"管理ID {code} は既に登録されています")
    m = EqMachine(code=code)
    _apply_machine(m, data)
    db.add(m); db.commit()
    return {"id": str(m.id), "code": m.code}


def _apply_machine(m: EqMachine, data: dict):
    for k in MACHINE_FIELDS:
        if k not in data:
            continue
        v = data[k]
        if k == "sort_order":
            m.sort_order = int(v or 0)
            continue
        if isinstance(v, str):
            v = v.strip()
        setattr(m, k, v or None)
    if "price" in data:
        m.price = _to_int(data["price"])
    elif "price_raw" in data and m.price is None:
        m.price = _to_int(data["price_raw"])
    if not m.status:
        m.status = "active"


@router.put("/machines/{machine_id}")
def update_machine(machine_id: str, data: dict, db: Session = Depends(get_db)):
    m = db.query(EqMachine).filter(EqMachine.id == _uuid(machine_id)).first()
    if not m:
        raise HTTPException(404, "機械が見つかりません")
    if "code" in data:
        code = _norm_code(data["code"])
        if code != m.code and db.query(EqMachine).filter(EqMachine.code == code).first():
            raise HTTPException(400, f"管理ID {code} は既に登録されています")
        m.code = code
    _apply_machine(m, data)
    db.commit()
    return {"ok": True}


@router.delete("/machines/{machine_id}")
def delete_machine(machine_id: str, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    m = db.query(EqMachine).filter(EqMachine.id == _uuid(machine_id)).first()
    if not m:
        raise HTTPException(404, "機械が見つかりません")
    if db.query(sqlfunc.count(EqPlacement.id)).filter(EqPlacement.machine_id == m.id).scalar():
        raise HTTPException(400, "配置履歴がある機械は削除できません。状態を「除去」等にしてください")
    db.delete(m); db.commit()
    return {"ok": True}


@router.get("/machines/{machine_id}/history")
def machine_history(machine_id: str, db: Session = Depends(get_db)):
    """機械ごとの配置履歴（有効期間）と移動履歴（確定済み・下書き・取消を含む）"""
    m = db.query(EqMachine).filter(EqMachine.id == _uuid(machine_id)).first()
    if not m:
        raise HTTPException(404, "機械が見つかりません")
    dnames = {d.id: d for d in db.query(EqDrawing).all()}
    pls = db.query(EqPlacement).filter(EqPlacement.machine_id == m.id).order_by(EqPlacement.valid_from.desc()).all()
    mvs = db.query(EqMove).filter(EqMove.machine_id == m.id).order_by(EqMove.moved_at.desc()).all()
    commits = {c.id: c for c in db.query(EqCommit).filter(EqCommit.id.in_([x.commit_id for x in mvs if x.commit_id] or [uuid.uuid4()])).all()}
    return {
        "machine": _machine_dict(m),
        "placements": [{"drawing_id": str(p.drawing_id), "drawing_name": dnames.get(p.drawing_id).name if dnames.get(p.drawing_id) else None,
                        "x": _f(p.x), "y": _f(p.y), "valid_from": _iso(p.valid_from), "valid_to": _iso(p.valid_to),
                        "commit_id": str(p.commit_id) if p.commit_id else None} for p in pls],
        "moves": [_move_dict(x, dnames.get(x.drawing_id), commits.get(x.commit_id)) for x in mvs],
    }


# ------------------------------------------------------------
# 機械一覧表の取込（CSV。tools/equipment_machine_list_pdf2csv.py で PDF から作る）
# ------------------------------------------------------------
LIST_COLS = {"工場": "list_site", "決算資産記載": "asset_flag_raw", "償却資": "depreciation_raw", "価格": "price_raw",
             "管理番号": "code", "機器名": "name", "分類1": "category1", "分類2": "category2", "メーカ": "maker",
             "商社": "dealer", "型式・仕様": "model", "製造年": "made_year", "電気仕様": "electric_spec", "備考": "notes",
             "工場作業内容": "work_content", "法令点検": "legal_inspection", "検査委託先": "inspector", "修理記録": "repair_log"}


def _status_from_flag(flag: str) -> str:
    f = (flag or "").strip()
    if "除去" in f or "除" in f or "削" in f:
        return "removed"
    if "処分" in f:
        return "disposed"
    if "無い" in f:
        return "unknown"
    return "active"


@router.post("/import/machines")
async def import_machines(file: UploadFile = File(...), apply: bool = Form(False), overwrite: bool = Form(False),
                          db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """機械一覧表 CSV を取り込む。apply=false はプレビューのみ。
    同じ管理番号が複数行ある場合（本体＋電気工事など）は最初の行を本体とし、残りは extra_rows に入れる。
    管理番号の無い「桜田工場移設」行は直前行の付帯行、「機械移設工事」行は移設費（管理番号 なし）として集計に含めない。
    overwrite=false のとき既存の機械は更新しない（新規のみ追加）。"""
    text = _decode_csv(await file.read())
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "管理番号" not in reader.fieldnames or "機器名" not in reader.fieldnames:
        raise HTTPException(400, "ヘッダーに『管理番号』『機器名』が必要です（機械一覧表の列名のまま）")
    rows = []
    for r in reader:
        rec = {LIST_COLS[k]: (v or "").strip() for k, v in r.items() if k in LIST_COLS}
        rec["code"] = _norm_code(rec.get("code", ""))
        rows.append(rec)
    grouped, order, skipped, attached = {}, [], [], 0
    last_code = None
    for rec in rows:
        code = rec["code"]
        if not code:
            if rec.get("name", "").startswith("桜田工場移設") and last_code and last_code in grouped:
                grouped[last_code]["extra_rows"].append({k: v for k, v in rec.items() if v})
                attached += 1
            else:
                skipped.append(rec.get("name") or "(名称なし)")
            continue
        if code in grouped:
            grouped[code]["extra_rows"].append({k: v for k, v in rec.items() if v and k != "code"})
            attached += 1
        else:
            grouped[code] = dict(rec, extra_rows=[])
            order.append(code)
        last_code = code
    existing = {m.code: m for m in db.query(EqMachine).all()}
    created = updated = unchanged = 0
    for i, code in enumerate(order):
        rec = grouped[code]
        m = existing.get(code)
        if m and not overwrite:
            unchanged += 1
            continue
        if not m:
            m = EqMachine(code=code)
            created += 1
        else:
            updated += 1
        data = dict(rec); data["sort_order"] = i
        # 状態は新規のときだけ一覧表の「決算資産記載」から推定する（上書き取込では手で直した状態を守る）
        data["status"] = m.status if m.status else _status_from_flag(rec.get("asset_flag_raw"))
        if not data.get("name"):
            data["name"] = "(名称なし)"
        _apply_machine(m, data)
        m.price = _to_int(rec.get("price_raw"))
        m.extra_rows = rec["extra_rows"] or None
        if apply and not existing.get(code):
            db.add(m)
    result = {"rows": len(rows), "machines": len(order), "created": created, "updated": updated, "unchanged": unchanged,
              "attached_rows": attached, "skipped": skipped, "applied": bool(apply)}
    if apply:
        db.commit()
    else:
        db.rollback()
    return result


# ------------------------------------------------------------
# 固定資産台帳の取込・照会
# ------------------------------------------------------------
LEDGER_COLS = {"固定資産名": "name", "管理番号": "asset_no", "取得日": "acquired_on", "事業供用開始日": "in_service_on",
               "取得価額": "price", "勘定科目": "account", "数量又は面積": "quantity", "部門": "department",
               "償却方法": "method", "耐用年数": "useful_life", "未償却残高": "ending_balance", "摘要": "remarks",
               "除却日": "disposed_on", "売却日": "sold_on", "仕訳摘要": "site_note"}


def _guess_period(filename: str) -> Optional[str]:
    m = re.search(r"(\d{4})年(\d{1,2})月", filename or "")
    return f"{m.group(1)}-{int(m.group(2)):02d}" if m else None


@router.post("/import/assets")
async def import_assets(file: UploadFile = File(...), period: Optional[str] = Form(None), apply: bool = Form(False),
                        db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """固定資産台帳 CSV（会計ソフト出力・Shift_JIS 可）を期ごとに取り込む。同じ期を再取込すると置き換える。
    戻り値に前期との差分（新規・消滅・価額変更）を含める"""
    text = _decode_csv(await file.read())
    period = (period or _guess_period(file.filename) or "").strip()
    if not re.match(r"^\d{4}-\d{2}$", period):
        raise HTTPException(400, "期を YYYY-MM で指定してください（例 2026-02）")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "固定資産名" not in reader.fieldnames or "取得価額" not in reader.fieldnames:
        raise HTTPException(400, "ヘッダーに『固定資産名』『取得価額』が必要です（固定資産台帳CSVの列名のまま）")
    recs, keys_seen = [], {}
    for r in reader:
        rec = {LEDGER_COLS[k]: (v or "").strip() for k, v in r.items() if k in LEDGER_COLS}
        if not rec.get("name"):
            continue
        no = rec.get("asset_no") or ""
        if no:
            key = no
        else:
            base = "N" + hashlib.sha1(f"{rec['name']}|{rec.get('acquired_on')}|{rec.get('price')}".encode("utf-8")).hexdigest()[:10]
            key = base
        n = keys_seen.get(key, 0) + 1
        keys_seen[key] = n
        if n > 1:
            key = f"{key}-{n}"
        rec["asset_key"] = key
        rec["raw"] = {k: (v or "") for k, v in r.items() if k}
        recs.append(rec)
    prev_period = db.query(sqlfunc.max(EqAsset.period)).filter(EqAsset.period < period).scalar()
    prev = {a.asset_key: a for a in db.query(EqAsset).filter(EqAsset.period == prev_period).all()} if prev_period else {}
    cur_keys = {r["asset_key"] for r in recs}
    diff = {"prev_period": prev_period,
            "added": [{"asset_key": r["asset_key"], "name": r["name"], "account": r.get("account"), "price": _to_int(r.get("price"))}
                      for r in recs if r["asset_key"] not in prev],
            "removed": [{"asset_key": k, "name": a.name, "account": a.account, "price": _f(a.price)} for k, a in prev.items() if k not in cur_keys],
            "price_changed": [{"asset_key": r["asset_key"], "name": r["name"], "before": _f(prev[r["asset_key"]].price), "after": _to_int(r.get("price"))}
                              for r in recs if r["asset_key"] in prev and _f(prev[r["asset_key"]].price) != _to_int(r.get("price"))]}
    accounts = {}
    for r in recs:
        accounts[r.get("account") or "(空欄)"] = accounts.get(r.get("account") or "(空欄)", 0) + 1
    result = {"period": period, "rows": len(recs), "accounts": accounts, "diff": diff, "applied": bool(apply),
              "replaced": db.query(sqlfunc.count(EqAsset.id)).filter(EqAsset.period == period).scalar() or 0}
    if apply:
        db.query(EqAsset).filter(EqAsset.period == period).delete()
        for r in recs:
            db.add(EqAsset(period=period, asset_key=r["asset_key"], asset_no=r.get("asset_no") or None, name=r["name"],
                           account=r.get("account") or None, acquired_on=_date(r.get("acquired_on")),
                           in_service_on=_date(r.get("in_service_on")), price=_to_int(r.get("price")),
                           quantity=r.get("quantity") or None, department=r.get("department") or None,
                           method=r.get("method") or None, useful_life=r.get("useful_life") or None,
                           ending_balance=_to_int(r.get("ending_balance")), site_note=r.get("site_note") or None,
                           remarks=r.get("remarks") or None, disposed_on=_date(r.get("disposed_on")),
                           sold_on=_date(r.get("sold_on")), raw=r["raw"]))
        db.commit()
    return result


@router.get("/assets/periods")
def asset_periods(db: Session = Depends(get_db)):
    rows = db.query(EqAsset.period, sqlfunc.count(EqAsset.id)).group_by(EqAsset.period).order_by(EqAsset.period.desc()).all()
    return [{"period": p, "count": c} for p, c in rows]


@router.get("/assets")
def list_assets(period: Optional[str] = None, search: Optional[str] = None, machine_only: bool = False,
                unlinked: bool = False, account: Optional[str] = None, db: Session = Depends(get_db)):
    period = _period_or_latest(db, period)
    if not period:
        return {"period": None, "items": []}
    q = db.query(EqAsset).filter(EqAsset.period == period)
    if search:
        s = f"%{search.strip()}%"
        q = q.filter(or_(EqAsset.name.ilike(s), EqAsset.asset_no.ilike(s), EqAsset.site_note.ilike(s), EqAsset.remarks.ilike(s)))
    if machine_only:
        q = q.filter(EqAsset.account.in_(MACHINE_ACCOUNTS))
    if account:
        q = q.filter(EqAsset.account == account)
    rows = q.order_by(EqAsset.acquired_on, EqAsset.name).all()
    links = {}
    for l, m in db.query(EqMachineAsset, EqMachine).join(EqMachine, EqMachine.id == EqMachineAsset.machine_id).all():
        links.setdefault(l.asset_key, []).append(_link_dict(l, None, m))
    items = []
    for a in rows:
        ls = links.get(a.asset_key, [])
        if unlinked and ls:
            continue
        d = _asset_dict(a); d["links"] = ls
        items.append(d)
    return {"period": period, "items": items}


# ------------------------------------------------------------
# 紐付け
# ------------------------------------------------------------
@router.get("/links")
def list_links(period: Optional[str] = None, db: Session = Depends(get_db)):
    period = _period_or_latest(db, period)
    assets = {a.asset_key: a for a in db.query(EqAsset).filter(EqAsset.period == period).all()} if period else {}
    rows = db.query(EqMachineAsset, EqMachine).join(EqMachine, EqMachine.id == EqMachineAsset.machine_id).order_by(EqMachine.code).all()
    return [_link_dict(l, assets.get(l.asset_key), m) for l, m in rows]


def _find_machine(db: Session, data: dict) -> EqMachine:
    if data.get("machine_id"):
        m = db.query(EqMachine).filter(EqMachine.id == _uuid(data["machine_id"])).first()
    else:
        m = db.query(EqMachine).filter(EqMachine.code == _norm_code(data.get("machine_code"))).first()
    if not m:
        raise HTTPException(404, "機械が見つかりません")
    return m


@router.post("/links")
def create_link(data: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = _find_machine(db, data)
    key = (data.get("asset_key") or "").strip()
    if not key:
        raise HTTPException(400, "台帳側のキー（管理番号）が指定されていません")
    if not db.query(EqAsset).filter(EqAsset.asset_key == key).first():
        raise HTTPException(404, f"台帳に {key} がありません")
    if db.query(EqMachineAsset).filter(EqMachineAsset.machine_id == m.id, EqMachineAsset.asset_key == key).first():
        raise HTTPException(400, "この紐付けは既に登録されています")
    lt = data.get("link_type") or "本体"
    if lt not in LINK_TYPES:
        raise HTTPException(400, f"種別は {'/'.join(LINK_TYPES)} のいずれかです")
    l = EqMachineAsset(machine_id=m.id, asset_key=key, link_type=lt,
                       confidence="confirmed" if data.get("confidence") == "confirmed" else "candidate",
                       note=data.get("note") or None, created_by=user.full_name)
    db.add(l); db.commit()
    return {"id": str(l.id)}


@router.put("/links/{link_id}")
def update_link(link_id: str, data: dict, db: Session = Depends(get_db)):
    l = db.query(EqMachineAsset).filter(EqMachineAsset.id == _uuid(link_id)).first()
    if not l:
        raise HTTPException(404, "紐付けが見つかりません")
    if "link_type" in data:
        if data["link_type"] not in LINK_TYPES:
            raise HTTPException(400, "種別が不正です")
        l.link_type = data["link_type"]
    if "confidence" in data:
        l.confidence = "confirmed" if data["confidence"] == "confirmed" else "candidate"
    if "note" in data:
        l.note = data["note"] or None
    db.commit()
    return {"ok": True}


@router.delete("/links/{link_id}")
def delete_link(link_id: str, db: Session = Depends(get_db)):
    l = db.query(EqMachineAsset).filter(EqMachineAsset.id == _uuid(link_id)).first()
    if not l:
        raise HTTPException(404, "紐付けが見つかりません")
    db.delete(l); db.commit()
    return {"ok": True}


@router.post("/links/auto")
def auto_link(data: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """台帳の資産名先頭の番号（工場プレフィックス付きを含む）から機械を探し、候補として紐付ける。
    価額が機械一覧の価格（付帯行を含む合計）と一致するものは confirmed、それ以外は candidate。既存の紐付けは触らない"""
    period = _period_or_latest(db, data.get("period"))
    if not period:
        raise HTTPException(400, "台帳が取り込まれていません")
    machines = {m.code: m for m in db.query(EqMachine).all()}
    linked = {(l.machine_id, l.asset_key) for l in db.query(EqMachineAsset).all()}
    linked_assets = {k for _, k in linked}
    created, confirmed, skipped = 0, 0, 0
    for a in db.query(EqAsset).filter(EqAsset.period == period).all():
        if a.account not in MACHINE_ACCOUNTS or a.asset_key in linked_assets:
            continue
        cands = _asset_code_candidates(a.name)
        hit = next((machines[c] for c in cands if c in machines), None)
        if not hit:
            skipped += 1
            continue
        if (hit.id, a.asset_key) in linked:
            continue
        total = int(hit.price or 0) + sum(_to_int(x.get("price_raw")) or 0 for x in (hit.extra_rows or []))
        price = int(a.price or 0)
        conf = "confirmed" if price and price in (total, int(hit.price or 0)) else "candidate"
        note = f"自動: 資産名先頭→{hit.code}" + ("（価額一致）" if conf == "confirmed" else f"（価額 台帳{price:,} / 一覧{total:,}）")
        db.add(EqMachineAsset(machine_id=hit.id, asset_key=a.asset_key, link_type="本体", confidence=conf, note=note,
                              created_by=user.full_name))
        linked.add((hit.id, a.asset_key)); created += 1
        if conf == "confirmed":
            confirmed += 1
    db.commit()
    return {"period": period, "created": created, "confirmed": confirmed, "candidate": created - confirmed, "no_match": skipped}


@router.post("/import/links")
async def import_links(file: UploadFile = File(...), apply: bool = Form(False),
                       db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """紐付け CSV（machine_code, asset_key, link_type, confidence, note）を取り込む。既存と重複する行は飛ばす"""
    text = _decode_csv(await file.read())
    reader = csv.DictReader(io.StringIO(text))
    need = {"machine_code", "asset_key"}
    if not reader.fieldnames or not need.issubset(set(reader.fieldnames)):
        raise HTTPException(400, "ヘッダーに machine_code, asset_key が必要です")
    machines = {m.code: m for m in db.query(EqMachine).all()}
    asset_keys = {a.asset_key for a in db.query(EqAsset).all()}
    existing = {(l.machine_id, l.asset_key) for l in db.query(EqMachineAsset).all()}
    created, errors = 0, []
    for i, r in enumerate(reader, 2):
        code = _norm_code(r.get("machine_code")); key = (r.get("asset_key") or "").strip()
        m = machines.get(code)
        if not m:
            errors.append(f"{i}行目: 機械 {code} が無い"); continue
        if key not in asset_keys:
            errors.append(f"{i}行目: 台帳 {key} が無い"); continue
        if (m.id, key) in existing:
            continue
        lt = (r.get("link_type") or "本体").strip()
        if lt not in LINK_TYPES:
            lt = "その他"
        if apply:
            db.add(EqMachineAsset(machine_id=m.id, asset_key=key, link_type=lt,
                                  confidence="confirmed" if (r.get("confidence") or "").strip() == "confirmed" else "candidate",
                                  note=(r.get("note") or "").strip() or None, created_by=user.full_name))
        existing.add((m.id, key)); created += 1
    if apply:
        db.commit()
    return {"created": created, "errors": errors, "applied": bool(apply)}


@router.get("/reconcile")
def reconcile(period: Optional[str] = None, db: Session = Depends(get_db)):
    """突合の一覧。
    machines_without_asset: 機械一覧にあって台帳に紐付いていない機械（一覧表の「決算資産記載」列付き）
    assets_without_machine: 台帳の機械系科目で機械に紐付いていない資産
    candidates: 確度が candidate の紐付け（人が確定する）"""
    period = _period_or_latest(db, period)
    assets = {a.asset_key: a for a in db.query(EqAsset).filter(EqAsset.period == period).all()} if period else {}
    links = db.query(EqMachineAsset, EqMachine).join(EqMachine, EqMachine.id == EqMachineAsset.machine_id).all()
    linked_machines = {m.id for _, m in links}
    linked_assets = {l.asset_key for l, _ in links}
    machines = db.query(EqMachine).order_by(EqMachine.sort_order, EqMachine.code).all()
    mw = [_machine_dict(m) for m in machines if m.id not in linked_machines]
    aw = [_asset_dict(a) for k, a in assets.items() if a.account in MACHINE_ACCOUNTS and k not in linked_assets]
    cands = [_link_dict(l, assets.get(l.asset_key), m) for l, m in links if l.confidence != "confirmed"]
    flagged = [x for x in mw if (x["asset_flag_raw"] or "").strip() in ("有", "有 工", "あり")]
    return {"period": period, "machines_without_asset": mw, "machines_flagged_but_unlinked": flagged,
            "assets_without_machine": aw, "candidates": cands,
            "summary": {"machines": len(machines), "machines_without_asset": len(mw), "flagged_but_unlinked": len(flagged),
                        "assets_machine_accounts": sum(1 for a in assets.values() if a.account in MACHINE_ACCOUNTS),
                        "assets_without_machine": len(aw), "candidates": len(cands)}}


# ------------------------------------------------------------
# 図面上の配置・移動（下書き → 確定）
# ------------------------------------------------------------
def _move_dict(x: EqMove, drawing: Optional[EqDrawing] = None, commit: Optional[EqCommit] = None, machine: Optional[EqMachine] = None) -> dict:
    d = {"id": str(x.id), "drawing_id": str(x.drawing_id), "machine_id": str(x.machine_id), "seq": x.seq, "kind": x.kind,
         "from_x": _f(x.from_x), "from_y": _f(x.from_y), "to_x": _f(x.to_x), "to_y": _f(x.to_y),
         "moved_at": _iso(x.moved_at), "user_name": x.user_name,
         "commit_id": str(x.commit_id) if x.commit_id else None, "undone_at": _iso(x.undone_at)}
    if drawing is not None:
        d["drawing_name"] = drawing.name
    if commit is not None:
        d["committed_at"] = _iso(commit.committed_at)
    if machine is not None:
        d["machine_code"] = machine.code; d["machine_name"] = machine.name
    return d


def _as_of_dt(as_of: Optional[str]) -> Optional[dt.datetime]:
    """as_of は日時（ISO）か日付。日付だけならその日の終わり（翌日 0:00 の直前）として扱う"""
    if not as_of:
        return None
    s = as_of.strip().replace("Z", "")
    try:
        if len(s) == 10:
            return dt.datetime.fromisoformat(s) + dt.timedelta(days=1) - dt.timedelta(seconds=1)
        return dt.datetime.fromisoformat(s)
    except ValueError:
        raise HTTPException(400, "as_of は YYYY-MM-DD か ISO 日時で指定してください")


def _placements_as_of(db: Session, drawing_id, at: Optional[dt.datetime]):
    q = db.query(EqPlacement).filter(EqPlacement.drawing_id == drawing_id)
    if at is None:
        q = q.filter(EqPlacement.valid_to.is_(None))
    else:
        q = q.filter(EqPlacement.valid_from <= at, or_(EqPlacement.valid_to.is_(None), EqPlacement.valid_to > at))
    return q.all()


def _draft_moves(db: Session, drawing_id):
    return db.query(EqMove).filter(EqMove.drawing_id == drawing_id, EqMove.commit_id.is_(None), EqMove.undone_at.is_(None)) \
        .order_by(EqMove.seq).all()


def _effective_state(db: Session, drawing_id) -> dict:
    """確定済みの現在配置に下書きを順に適用した状態。machine_id -> (x, y) （remove されたものは含まない）"""
    state = {p.machine_id: (_f(p.x), _f(p.y)) for p in _placements_as_of(db, drawing_id, None)}
    for mv in _draft_moves(db, drawing_id):
        if mv.kind == "remove":
            state.pop(mv.machine_id, None)
        else:
            state[mv.machine_id] = (_f(mv.to_x), _f(mv.to_y))
    return state


@router.get("/drawings/{drawing_id}/board")
def drawing_board(drawing_id: str, as_of: Optional[str] = None, db: Session = Depends(get_db)):
    """図面画面のデータ一式。as_of 指定時はその時点の確定配置のみ（下書き・未配置リストは付けない）"""
    d = db.query(EqDrawing).filter(EqDrawing.id == _uuid(drawing_id)).first()
    if not d:
        raise HTTPException(404, "図面が見つかりません")
    at = _as_of_dt(as_of)
    machines = {m.id: m for m in db.query(EqMachine).all()}
    committed = {p.machine_id: p for p in _placements_as_of(db, d.id, at)}
    # 台帳紐付け（チップ選択時の表示用。最新期の台帳で引く）
    period = _latest_period(db)
    assets = {a.asset_key: a for a in db.query(EqAsset).filter(EqAsset.period == period).all()} if period else {}
    links_by_m = {}
    for l in db.query(EqMachineAsset).all():
        links_by_m.setdefault(l.machine_id, []).append(_link_dict(l, assets.get(l.asset_key)))
    md = lambda mid: _machine_dict(machines[mid], links_by_m.get(mid, []))
    out = {"drawing": _drawing_dict(d), "as_of": _iso(at) if at else None}
    if at is not None:
        out["placements"] = [dict(md(mid), x=_f(p.x), y=_f(p.y), since=_iso(p.valid_from), draft=None)
                             for mid, p in committed.items() if mid in machines]
        out["draft_moves"] = []; out["unplaced"] = []
        return out
    drafts = _draft_moves(db, d.id)
    state = dict((mid, (_f(p.x), _f(p.y))) for mid, p in committed.items())
    draft_kind = {}
    for mv in drafts:
        if mv.kind == "remove":
            state.pop(mv.machine_id, None)
        else:
            state[mv.machine_id] = (_f(mv.to_x), _f(mv.to_y))
        draft_kind[mv.machine_id] = mv.kind
    placements = []
    for mid, (x, y) in state.items():
        if mid not in machines:
            continue
        p = committed.get(mid)
        placements.append(dict(md(mid), x=x, y=y, since=_iso(p.valid_from) if p else None,
                               draft=draft_kind.get(mid), committed_x=_f(p.x) if p else None, committed_y=_f(p.y) if p else None))
    removed = [dict(md(mid), x=_f(p.x), y=_f(p.y), since=_iso(p.valid_from), draft="remove")
               for mid, p in committed.items() if draft_kind.get(mid) == "remove" and mid in machines]
    # 未配置 = この図面に置かれていない稼働中の機械（他の図面に載っていてもよい。全体図と詳細図の両方に置けるようにするため）。
    # 図面の拠点と一覧表の「工場」が合うものを先に出す
    elsewhere = _current_placements(db)
    site_name = d.site.name if d.site else ""

    def same_site(m):
        ls = (m.list_site or "").replace("？", "")
        return bool(ls) and (site_name.startswith(ls) or ls.startswith(site_name[:2]))
    unplaced = [dict(md(m.id), same_site=same_site(m),
                     placed_elsewhere=[p["drawing_name"] for p in elsewhere.get(m.id, []) if p["drawing_id"] != str(d.id)]) for m in
                sorted(machines.values(), key=lambda m: (not same_site(m), m.sort_order or 0, m.code))
                if m.id not in state and m.status == "active"]
    out.update({"placements": placements, "removed_in_draft": removed,
                "draft_moves": [_move_dict(mv, machine=machines.get(mv.machine_id)) for mv in drafts],
                "unplaced": unplaced,
                "last_commit": _commit_dict(db.query(EqCommit).filter(EqCommit.drawing_id == d.id).order_by(EqCommit.committed_at.desc()).first())})
    return out


def _commit_dict(c: Optional[EqCommit]) -> Optional[dict]:
    if c is None:
        return None
    return {"id": str(c.id), "drawing_id": str(c.drawing_id), "committed_at": _iso(c.committed_at), "user_name": c.user_name,
            "memo": c.memo, "move_count": c.move_count}


@router.post("/drawings/{drawing_id}/moves")
def add_move(drawing_id: str, data: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """ドラッグ 1 回 = 下書き 1 件。kind: place（未配置→配置）/ move / remove。座標は 0〜1"""
    d = db.query(EqDrawing).filter(EqDrawing.id == _uuid(drawing_id)).first()
    if not d:
        raise HTTPException(404, "図面が見つかりません")
    m = _find_machine(db, data)
    kind = data.get("kind")
    if kind not in MOVE_KINDS:
        raise HTTPException(400, "kind は place / move / remove のいずれかです")
    state = _effective_state(db, d.id)
    cur = state.get(m.id)
    if kind == "remove":
        if cur is None:
            raise HTTPException(400, "この図面に配置されていない機械は外せません")
        to_x = to_y = None
    else:
        try:
            to_x = float(data.get("x")); to_y = float(data.get("y"))
        except (TypeError, ValueError):
            raise HTTPException(400, "座標が不正です")
        if not (0 <= to_x <= 1 and 0 <= to_y <= 1):
            raise HTTPException(400, "座標は 0〜1 の比率で指定してください")
        if kind == "move" and cur is None:
            kind = "place"
        if kind == "place" and cur is not None:
            kind = "move"
    seq =(db.query(sqlfunc.max(EqMove.seq)).filter(EqMove.drawing_id == d.id).scalar() or 0) + 1
    mv = EqMove(drawing_id=d.id, machine_id=m.id, seq=seq, kind=kind,
                from_x=cur[0] if cur else None, from_y=cur[1] if cur else None, to_x=to_x, to_y=to_y,
                moved_at=_now(), user_id=user.id, user_name=user.full_name)
    db.add(mv); db.commit()
    return _move_dict(mv, machine=m)


@router.post("/drawings/{drawing_id}/moves/undo")
def undo_move(drawing_id: str, db: Session = Depends(get_db)):
    """最後の下書き 1 件を取り消す（行は残し undone_at を入れる）"""
    drafts = _draft_moves(db, _uuid(drawing_id))
    if not drafts:
        raise HTTPException(400, "取り消す下書きがありません")
    last = drafts[-1]
    last.undone_at = _now()
    db.commit()
    return {"ok": True, "undone": _move_dict(last), "remaining": len(drafts) - 1}


@router.delete("/drawings/{drawing_id}/draft")
def discard_draft(drawing_id: str, db: Session = Depends(get_db)):
    """この図面の下書きをすべて取り消す"""
    drafts = _draft_moves(db, _uuid(drawing_id))
    now = _now()
    for mv in drafts:
        mv.undone_at = now
    db.commit()
    return {"ok": True, "discarded": len(drafts)}


@router.post("/drawings/{drawing_id}/commit")
def commit_draft(drawing_id: str, data: Optional[dict] = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """下書きを確定する。機械ごとの最終状態だけを配置に反映し、有効期間を切り替える。
    取り消し済みの下書きも同じ確定に紐づけて履歴に残す"""
    d = db.query(EqDrawing).filter(EqDrawing.id == _uuid(drawing_id)).first()
    if not d:
        raise HTTPException(404, "図面が見つかりません")
    data = data or {}
    drafts = _draft_moves(db, d.id)
    if not drafts:
        raise HTTPException(400, "確定する下書きがありません")
    now = _now()
    c = EqCommit(drawing_id=d.id, committed_at=now, user_id=user.id, user_name=user.full_name,
                 memo=(data.get("memo") or "").strip() or None, move_count=len(drafts))
    db.add(c); db.flush()
    committed = {p.machine_id: p for p in _placements_as_of(db, d.id, None)}
    final = {}
    for mv in drafts:
        final[mv.machine_id] = ("remove", None, None) if mv.kind == "remove" else ("put", _f(mv.to_x), _f(mv.to_y))
    changed = 0
    for mid, (act, x, y) in final.items():
        cur = committed.get(mid)
        if act == "remove":
            if cur is not None:
                cur.valid_to = now; changed += 1
            continue
        if cur is not None and abs(_f(cur.x) - x) < 1e-9 and abs(_f(cur.y) - y) < 1e-9:
            continue  # 動かして元に戻した場合は履歴を切らない
        # この図面の現在の配置を閉じて新しい配置を開く（他の図面の配置には触らない）
        if cur is not None:
            cur.valid_to = now
        db.add(EqPlacement(machine_id=mid, drawing_id=d.id, x=x, y=y, valid_from=now, commit_id=c.id))
        changed += 1
    # 下書き（取り消し済みを含む）を確定に紐づける
    for mv in db.query(EqMove).filter(EqMove.drawing_id == d.id, EqMove.commit_id.is_(None)).all():
        mv.commit_id = c.id
    db.commit()
    return {"ok": True, "commit": _commit_dict(c), "changed": changed}


@router.post("/import/placements")
async def import_placements(file: UploadFile = File(...), apply: bool = Form(False), memo: Optional[str] = Form(None),
                            db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """初期配置 CSV（drawing, machine_code, x, y）を取り込む。drawing は図面名（完全一致）、x/y は画像に対する 0〜1。
    図面ごとに下書きを作って確定する（既にその図面に置かれている機械は飛ばす）。apply=false はプレビューのみ"""
    text = _decode_csv(await file.read())
    reader = csv.DictReader(io.StringIO(text))
    need = {"drawing", "machine_code", "x", "y"}
    if not reader.fieldnames or not need.issubset(set(reader.fieldnames)):
        raise HTTPException(400, "ヘッダーに drawing, machine_code, x, y が必要です")
    # 図面は名前、または登録時の画像ファイル名（拡張子あり／なし）で引ける
    drawings = {}
    for d in db.query(EqDrawing).filter(EqDrawing.is_active == True).all():
        drawings.setdefault(d.name, d)
        if d.source_filename:
            drawings.setdefault(d.source_filename, d)
            drawings.setdefault(d.source_filename.rsplit(".", 1)[0], d)
    machines = {m.code: m for m in db.query(EqMachine).all()}
    plan, errors, skipped = {}, [], []
    for i, r in enumerate(reader, 2):
        dn = (r.get("drawing") or "").strip(); code = _norm_code(r.get("machine_code"))
        d = drawings.get(dn) or drawings.get(dn.rsplit(".", 1)[0]); m = machines.get(code)
        if not d:
            errors.append(f"{i}行目: 図面「{dn}」が無い"); continue
        if not m:
            errors.append(f"{i}行目: 機械 {code} が無い"); continue
        try:
            x = float(r.get("x")); y = float(r.get("y"))
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{i}行目: 座標が不正 ({r.get('x')}, {r.get('y')})"); continue
        plan.setdefault(d.id, {})
        if m.id in plan[d.id]:
            skipped.append(f"{dn}: {code} が重複（後の行を無視）"); continue
        plan[d.id][m.id] = (x, y, code)
    created, per_drawing = 0, []
    now = _now()
    for did, items in plan.items():
        d = db.query(EqDrawing).filter(EqDrawing.id == did).first()
        state = _effective_state(db, did)
        todo = {mid: v for mid, v in items.items() if mid not in state}
        for mid, (x, y, code) in items.items():
            if mid in state:
                skipped.append(f"{d.name}: {code} は既に配置済み")
        per_drawing.append({"drawing": d.name, "rows": len(items), "to_place": len(todo)})
        if not apply or not todo:
            continue
        seq = (db.query(sqlfunc.max(EqMove.seq)).filter(EqMove.drawing_id == did).scalar() or 0)
        c = EqCommit(drawing_id=did, committed_at=now, user_id=user.id, user_name=user.full_name,
                     memo=(memo or "初期配置（CSV取込）").strip(), move_count=len(todo))
        db.add(c); db.flush()
        for mid, (x, y, code) in todo.items():
            seq += 1
            db.add(EqMove(drawing_id=did, machine_id=mid, seq=seq, kind="place", to_x=x, to_y=y, moved_at=now,
                          user_id=user.id, user_name=user.full_name, commit_id=c.id))
            db.add(EqPlacement(machine_id=mid, drawing_id=did, x=x, y=y, valid_from=now, commit_id=c.id))
            created += 1
    if apply:
        db.commit()
    return {"applied": bool(apply), "placed": created if apply else sum(p["to_place"] for p in per_drawing),
            "drawings": per_drawing, "skipped": skipped, "errors": errors}


@router.get("/drawings/{drawing_id}/commits")
def list_commits(drawing_id: str, db: Session = Depends(get_db)):
    rows = db.query(EqCommit).filter(EqCommit.drawing_id == _uuid(drawing_id)).order_by(EqCommit.committed_at.desc()).all()
    return [_commit_dict(c) for c in rows]


@router.get("/commits/{commit_id}")
def get_commit(commit_id: str, db: Session = Depends(get_db)):
    c = db.query(EqCommit).filter(EqCommit.id == _uuid(commit_id)).first()
    if not c:
        raise HTTPException(404, "確定履歴が見つかりません")
    machines = {m.id: m for m in db.query(EqMachine).all()}
    moves = db.query(EqMove).filter(EqMove.commit_id == c.id).order_by(EqMove.seq).all()
    return {"commit": _commit_dict(c), "moves": [_move_dict(x, machine=machines.get(x.machine_id)) for x in moves]}


@router.get("/moves")
def list_moves(drawing_id: Optional[str] = None, machine_id: Optional[str] = None, limit: int = Query(200, le=2000),
               db: Session = Depends(get_db)):
    """移動履歴（新しい順）。確定済み・下書き・取り消しをすべて含む"""
    q = db.query(EqMove)
    if drawing_id:
        q = q.filter(EqMove.drawing_id == _uuid(drawing_id))
    if machine_id:
        q = q.filter(EqMove.machine_id == _uuid(machine_id))
    rows = q.order_by(EqMove.moved_at.desc()).limit(limit).all()
    machines = {m.id: m for m in db.query(EqMachine).all()}
    drawings = {d.id: d for d in db.query(EqDrawing).all()}
    commits = {c.id: c for c in db.query(EqCommit).all()}
    return [_move_dict(x, drawings.get(x.drawing_id), commits.get(x.commit_id), machines.get(x.machine_id)) for x in rows]
