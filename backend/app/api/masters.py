"""商社・納入先の読み口。

実体は取引先マスタ（suppliers＋supplier_branches）に統合した。同じ会社が
「納入先であり商社」「納入先であり仕入先」になるため、会社を1行にして
役割（is_agency / is_customer / is_supplier）で見分ける。

ここは旧マスタと同じ形で返す窓口。案件登録などの画面が商社コード・納入先コードで
値を持っているため、画面を変えずに参照先だけ差し替えられるようにしている。
登録・修正もこの窓口から取引先マスタへ書く。

拠点（工場・営業所・支店）はコードを持つことがあり、案件がそのコードで納入先を
指している。そのため「会社＋拠点」を1件として並べる。
従業員マスタは 2026-09-17 にユーザーマスタ（/api/auth/users）へ統合した。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from pydantic import BaseModel
from app.db.models import get_db, Supplier, SupplierBranch
from app.normalize import nfkc
import uuid as _uuid

router = APIRouter()


def _branches(db: Session, ids, role: str):
    """その用途で使える拠点。role が空の拠点はどの用途でも使う"""
    out = {}
    if not ids:
        return out
    for b in (db.query(SupplierBranch)
                .filter(SupplierBranch.supplier_id.in_(list(ids)),
                        SupplierBranch.is_active == True,  # noqa: E712
                        or_(SupplierBranch.role.is_(None), SupplierBranch.role == role))
                .order_by(SupplierBranch.name).all()):
        out.setdefault(str(b.supplier_id), []).append(b)
    return out


def _rows(db: Session, role_col, search: Optional[str], role: str, expand: bool = True):
    """役割で絞った取引先を並べる。

    expand=True（納入先）は拠点ごとに1件にする。工場ごとにコードが振られており、
    案件がそのコードで納入先を指しているため。拠点があれば会社そのものは出さない。
    expand=False（商社）は会社1件にまとめ、支店名だけ添える。
    """
    q = db.query(Supplier).filter(Supplier.is_active == True, role_col == True)  # noqa: E712
    if search:
        like = f"%{nfkc(search)}%"
        q = q.filter(or_(Supplier.name.ilike(like), Supplier.short_name.ilike(like),
                         Supplier.name_kana.ilike(like), Supplier.supplier_code.ilike(like)))
    sups = q.order_by(Supplier.supplier_code).all()
    bm = _branches(db, [s.id for s in sups], role)
    out = []
    for s in sups:
        bs = bm.get(str(s.id)) or []
        if not expand:
            out.append((s, bs[0] if len(bs) == 1 else None))
        elif bs:
            out.extend((s, b) for b in bs)
        else:
            out.append((s, None))
    return out


def _pick(*vals):
    for v in vals:
        if (v or "").strip():
            return v
    return None


def _agency_dict(s: Supplier, b=None):
    return {
        "id": str(b.id) if b is not None else str(s.id),
        "supplier_id": str(s.id),
        "agency_code": (b.code if b is not None else None) or s.supplier_code,
        "agency_name": s.name,
        "branch_name": b.name if b is not None else None,
        "trade_terms": s.trade_terms,
        "address": _pick(b.address if b is not None else None, s.address),
        "contact_person": _pick(b.contact_person if b is not None else None, s.contact_person),
        "phone": _pick(b.phone if b is not None else None, s.phone),
        "is_active": True,
    }


def _dest_dict(s: Supplier, b=None):
    factory = b.name if b is not None else None
    return {
        "id": str(b.id) if b is not None else str(s.id),
        "supplier_id": str(s.id),
        "customer_id": (b.code if b is not None else None) or s.supplier_code,
        "company_name": s.name,
        "factory_name": factory,
        "company_factory_name": (s.name + " " + factory) if factory else s.name,
        "address": _pick(b.address if b is not None else None, s.address),
        "prefecture": s.prefecture,
        "postal_code": _pick(b.postal_code if b is not None else None, s.postal_code),
        "tel": _pick(b.phone if b is not None else None, s.phone),
        "fax": _pick(b.fax if b is not None else None, s.fax),
        "contact_person": _pick(b.contact_person if b is not None else None, s.contact_person),
        "customer_rank": s.customer_rank,
        "notes": _pick(b.notes if b is not None else None, s.notes),
        "is_active": True,
    }


def _looks_uuid(v):
    try:
        _uuid.UUID(str(v))
        return True
    except Exception:
        return False


def _find(db: Session, ident: str):
    """コード・拠点コード・IDのどれでも引けるようにする。返すのは (会社, 拠点)"""
    ident = (ident or "").strip()
    if not ident:
        return None, None
    cond = [SupplierBranch.code == ident]
    if _looks_uuid(ident):
        cond.append(SupplierBranch.id == ident)
    b = db.query(SupplierBranch).filter(or_(*cond)).first()
    if b is not None:
        return db.query(Supplier).filter(Supplier.id == b.supplier_id).first(), b
    cond = [Supplier.supplier_code == ident]
    if _looks_uuid(ident):
        cond.append(Supplier.id == ident)
    return db.query(Supplier).filter(or_(*cond)).first(), None


# =============================================
# 商社
# =============================================
class AgencyIn(BaseModel):
    agency_code: str
    agency_name: str
    branch_name: Optional[str] = None
    trade_terms: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None


@router.get("/agencies")
def list_agencies(search: Optional[str] = None, db: Session = Depends(get_db)):
    return [_agency_dict(s, b) for s, b in
            _rows(db, Supplier.is_agency, search, "agency", expand=False)]


@router.post("/agencies", status_code=201)
def create_agency(data: AgencyIn, db: Session = Depends(get_db)):
    code = nfkc(data.agency_code.strip())
    if db.query(Supplier).filter(Supplier.supplier_code == code).first():
        raise HTTPException(400, f"取引先コード {code} は既に登録されています")
    s = Supplier(supplier_code=code, name=data.agency_name, trade_terms=data.trade_terms,
                 address=data.address, contact_person=data.contact_person, phone=data.phone,
                 is_supplier=False, is_agency=True, is_customer=False, is_active=True)
    db.add(s)
    db.flush()
    if (data.branch_name or "").strip():
        db.add(SupplierBranch(supplier_id=s.id, name=data.branch_name,
                              role="agency", is_active=True))
    db.commit()
    db.refresh(s)
    return _agency_dict(s)


@router.put("/agencies/{agency_id}")
def update_agency(agency_id: str, data: AgencyIn, db: Session = Depends(get_db)):
    s, b = _find(db, agency_id)
    if not s:
        raise HTTPException(404)
    s.name = data.agency_name
    s.trade_terms = data.trade_terms
    s.is_agency = True
    target = b if b is not None else s
    target.address = data.address
    target.contact_person = data.contact_person
    target.phone = data.phone
    if b is not None and (data.branch_name or "").strip():
        b.name = data.branch_name
    db.commit()
    db.refresh(s)
    return _agency_dict(s, b)


@router.delete("/agencies/{agency_id}", status_code=204)
def delete_agency(agency_id: str, db: Session = Depends(get_db)):
    s, b = _find(db, agency_id)
    if not s:
        raise HTTPException(404)
    if b is not None:
        b.is_active = False
    else:
        s.is_agency = False          # 他の役割が残るなら取引先そのものは消さない
        if not (s.is_supplier or s.is_customer):
            s.is_active = False
    db.commit()


# =============================================
# 納入先
# =============================================
class DeliveryDestinationIn(BaseModel):
    customer_id: str
    company_name: str
    factory_name: Optional[str] = None
    company_factory_name: Optional[str] = None
    address: Optional[str] = None
    prefecture: Optional[str] = None
    postal_code: Optional[str] = None
    tel: Optional[str] = None
    fax: Optional[str] = None
    contact_person: Optional[str] = None   # 先方のご担当者（送り状・依頼書の宛先に使う）
    customer_rank: Optional[str] = None
    notes: Optional[str] = None


@router.get("/delivery-destinations")
def list_delivery_destinations(search: Optional[str] = None, db: Session = Depends(get_db)):
    return [_dest_dict(s, b) for s, b in
            _rows(db, Supplier.is_customer, search, "customer")]


@router.post("/delivery-destinations", status_code=201)
def create_delivery_destination(data: DeliveryDestinationIn, db: Session = Depends(get_db)):
    code = nfkc(data.customer_id.strip())
    if db.query(Supplier).filter(Supplier.supplier_code == code).first():
        raise HTTPException(400, f"取引先コード {code} は既に登録されています")
    s = Supplier(supplier_code=code, name=data.company_name, address=data.address,
                 prefecture=data.prefecture, postal_code=data.postal_code,
                 phone=data.tel, fax=data.fax, contact_person=data.contact_person,
                 customer_rank=data.customer_rank, notes=data.notes,
                 is_supplier=False, is_agency=False, is_customer=True, is_active=True)
    db.add(s)
    db.flush()
    if (data.factory_name or "").strip():
        db.add(SupplierBranch(supplier_id=s.id, name=data.factory_name,
                              role="customer", is_active=True))
    db.commit()
    db.refresh(s)
    return _dest_dict(s)


@router.put("/delivery-destinations/{dest_id}")
def update_delivery_destination(dest_id: str, data: DeliveryDestinationIn,
                                db: Session = Depends(get_db)):
    s, b = _find(db, dest_id)
    if not s:
        raise HTTPException(404)
    s.name = data.company_name
    s.prefecture = data.prefecture
    s.customer_rank = data.customer_rank
    s.is_customer = True
    target = b if b is not None else s
    target.address = data.address
    target.postal_code = data.postal_code
    target.contact_person = data.contact_person
    target.notes = data.notes
    if b is not None:
        b.phone, b.fax = data.tel, data.fax
        if (data.factory_name or "").strip():
            b.name = data.factory_name
    else:
        s.phone, s.fax = data.tel, data.fax
    db.commit()
    db.refresh(s)
    return _dest_dict(s, b)


@router.delete("/delivery-destinations/{dest_id}", status_code=204)
def delete_delivery_destination(dest_id: str, db: Session = Depends(get_db)):
    s, b = _find(db, dest_id)
    if not s:
        raise HTTPException(404)
    if b is not None:
        b.is_active = False
    else:
        s.is_customer = False
        if not (s.is_supplier or s.is_agency):
            s.is_active = False
    db.commit()
