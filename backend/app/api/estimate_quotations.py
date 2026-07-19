# -*- coding: utf-8 -*-
"""見積書 API"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse, HTMLResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, or_, func
from typing import Optional, List
from pydantic import BaseModel
from datetime import date, datetime
import io, uuid, collections

from app.normalize import nfkc
from app.db.models import (
    get_db, pk_or_code, QuotationHeader, QuotationLineItem, QuotationLaborDetail,
    OrderTicket, OrderTicketFile, ApprovalToken, ProjectOrder, Project,
    EstimateBfrBody, EstimateBfrFan, EstimateBfrRv,
    EstimateBfqSeries, EstimateBfqBody, EstimateBfqFan, EstimateBfqOption,
    EstimateScaBody, EstimatePlFan, EstimateCyclone, EstimateAutoDamper, EstimateLaborItem
)

router = APIRouter()

# 工番/単番は案件子ID(ProjectOrder.ticket_type)で登録時に選択する（2026-07-18〜）。
# 税抜300万円による自動判定は廃止したため、しきい値は使用しない。

# メールの承認リンクの有効期間（時間）。1回使うと無効になる
APPROVAL_LINK_HOURS = 72

# CAD図面(DXF)を直接アップロードする場合の上限。
# 実運用の図面(13〜101MB)はブラウザ側で走査して /from-cad-extract へ送るため、
# ここは小さい図面の直叩き用。サーバのメモリを守るため小さく抑えている。
MAX_CAD_FILE_SIZE = 8 * 1024 * 1024

# 承認権限者はユーザーマスタの機能権限「検印承認者」(approver) を持つ人。
# 以前はここに氏名をハードコードしていたが、ユーザー管理画面で設定する方式に変更した。

def net_amount(q: "QuotationHeader") -> int:
    """見積の税抜合計（機器・工事 + 社内工数 − 出精値引）。
    案件金額・受注票・売上計画表など社内の集計金額はすべてこの税抜金額で統一する。
    総額(total_amount)は税込のまま保持し、見積書の印字にのみ使う。"""
    return int((q.subtotal or 0) + (q.labor_total or 0) - (q.discount_amount or 0))

def _sync_project_final_amount(project_order: "ProjectOrder", db: Session):
    """受注票発行・見積採用時に親案件の最終受注金額を子ID合計で自動更新する"""
    if not project_order.project_id:
        return
    total = db.query(func.sum(ProjectOrder.quotation_total)).filter(
        ProjectOrder.project_id == project_order.project_id
    ).scalar() or 0
    parent = db.query(Project).filter(Project.id == project_order.project_id).first()
    if parent:
        parent.final_order_amount = int(total)

# =============================================
# 見積パターンマスタ取得
# =============================================
@router.post("/from-cad", status_code=201)
async def create_quotation_from_cad(
    file: UploadFile = File(...),
    project_order_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """CAD図面(DXF)ファイルを直接アップロードして見積を自動生成する（小さい図面用）。

    ※ 実運用の図面は13〜101MBあり、このエンドポイントでは扱えない。
    画面からは /from-cad-extract（ブラウザで走査した結果だけを送る）を使うこと。

    【メモリ事故の再発防止】2026-07-18、59MBの図面をここへ直接アップロードした結果
    Renderのメモリ上限を超えてインスタンスが自動再起動した。原因は
    「file.read() で全体をメモリに載せてから」サイズ検査していたこと。
    現在は 1MB ずつ temp ファイルへ書き出し、上限超過を検知した時点で中断する。
    上限も実運用サイズより十分小さく設定してある（下記 MAX_CAD_FILE_SIZE）。
    """
    import tempfile, os as _os
    from app.cad_extract import extract_from_dxf

    fname = file.filename or ""
    if not fname.lower().endswith(".dxf"):
        raise HTTPException(400, "DXFファイルを指定してください（DWGはAutoCADのDXFOUTで変換）")

    limit_mb = MAX_CAD_FILE_SIZE // 1024 // 1024
    tmp_path = None
    try:
        # メモリに全体を載せないよう、チャンクで temp ファイルへ流す
        size = 0
        with tempfile.NamedTemporaryFile(suffix=".dxf", delete=False) as tf:
            tmp_path = tf.name
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_CAD_FILE_SIZE:
                    raise HTTPException(
                        413,
                        f"ファイルが大きすぎます（上限{limit_mb}MB）。"
                        "実運用サイズの図面は画面の「CADから見積作成」をお使いください"
                        "（ブラウザ側で解析するためサイズ制限がありません）",
                    )
                tf.write(chunk)
        try:
            info = extract_from_dxf(tmp_path)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"DXFの解析に失敗しました: {e}")
    finally:
        if tmp_path and _os.path.exists(tmp_path):
            _os.unlink(tmp_path)

    return _build_quotation_from_cad_info(info, fname, project_order_id, title, db)


class CadExtractIn(BaseModel):
    """ブラウザでDXFを走査した結果（アップロード量を数KBに抑えるため）"""
    filename: str
    block_names: List[str] = []          # INSERTのブロック名（重複はそのまま）
    texts: List[str] = []                # TEXT/MTEXT/ATTRIBの文字（関連するもののみ）
    insunits: Optional[str] = None
    acadver: Optional[str] = None
    project_order_id: Optional[str] = None
    title: Optional[str] = None


@router.post("/from-cad-extract", status_code=201)
def create_quotation_from_cad_extract(data: CadExtractIn, db: Session = Depends(get_db)):
    """ブラウザで走査済みのCAD情報から見積の骨格を自動生成する（画面はこちらを使う）。

    実運用の図面は13〜101MBあり、そのままアップロードするとサーバの
    リクエスト上限・タイムアウトに掛かる。ブラウザ側でDXFを1行ずつ走査し、
    ブロック名と関連テキストだけ（数KB）を送る。
    """
    from app.cad_extract import analyze
    if not data.block_names and not data.texts:
        raise HTTPException(400, "図面から情報を抽出できませんでした")
    # 想定は数KB（実測: 59MBの図面でブロック920件・文字92件＝14.8KB）。
    # 桁違いの入力でメモリを消費しないよう上限を設ける
    if len(data.block_names) > 200000 or len(data.texts) > 50000:
        raise HTTPException(413, "抽出結果が大きすぎます。図面を分割してください")
    info = analyze(data.block_names, data.texts, data.insunits, data.acadver)
    return _build_quotation_from_cad_info(
        info, data.filename, data.project_order_id, data.title, db
    )


def _build_quotation_from_cad_info(info: dict, fname: str, project_order_id, title, db: Session):
    """抽出結果 → パターンマスタ照合 → 見積(draft)作成。

    ダクトは図面から実長が取れないため概算。単価が引けない行は0円で作成され、要手入力。
    """
    from app.cad_extract import (
        duct_estimate, family_of, FAMILY, SECTION_NAMES,
        DUCT_RATE_PER_MM_M, DUCT_DEFAULT_RUN_M,
    )

    # ---- 型式をパターンマスタと照合して単価を決める ----
    def _lookup_price(model: str, fam: str):
        """(単価, 出典) を返す。マスタに無ければ (0, None)"""
        if fam == "BFQ":
            b = db.query(EstimateBfqBody).filter(EstimateBfqBody.model_code == model).first() \
                or db.query(EstimateBfqBody).filter(EstimateBfqBody.model_code.ilike(f"{model}%")).first()
            if b and b.base_price is not None:
                return int(b.base_price), "BFQパターンマスタ"
            if b:
                return 0, "BFQパターンマスタ(本体価格未確定)"
        elif fam == "BFR":
            b = db.query(EstimateBfrBody).filter(EstimateBfrBody.model_code == model).first()
            if not b:
                # BFR5X6 ⇔ BFR5×6 の表記差を吸収
                alt = model.replace("X", "×")
                b = db.query(EstimateBfrBody).filter(EstimateBfrBody.model_code == alt).first()
            if b:
                base = int(b.base_price or 0)
                filt = int(b.filter_price or 0) * int(b.filter_count or 0)
                return base + filt, "BFRパターンマスタ(本体+フィルター)"
        elif fam in ("SCA", "SCD"):
            b = db.query(EstimateScaBody).filter(EstimateScaBody.model_code == model).first()
            if b:
                return int(b.base_price or 0), "SCAパターンマスタ"
        elif fam in ("PL", "PLD"):
            b = db.query(EstimatePlFan).filter(EstimatePlFan.model_code == model).first()
            if b:
                return int(b.price or 0), "PLファンマスタ"
        elif fam in ("CY", "CYP", "CYT"):
            b = db.query(EstimateCyclone).filter(EstimateCyclone.model_code == model).first()
            if b:
                return int(b.price or 0), "サイクロンマスタ"
        elif fam == "ADC":
            b = db.query(EstimateAutoDamper).filter(EstimateAutoDamper.model_code == model).first()
            if b:
                return int(b.price or 0), "オートダンパマスタ"
        return 0, None

    # ---- 大項目ごとに明細を組み立てる ----
    sections = collections.defaultdict(list)   # 大項目番号 → [明細dict]
    unmatched = []                             # マスタで単価が引けなかった型式
    for model, cnt in sorted(info["models"].items()):
        fam = family_of(model)
        if not fam:
            continue
        sec, label = FAMILY[fam]
        price, src = _lookup_price(model, fam)
        if not price:
            unmatched.append(model)
        spec = [f"型式: {model}", f"図面内の出現: {cnt}箇所"]
        if src:
            spec.append(f"単価出典: {src}")
        else:
            spec.append("※パターンマスタに該当なし。単価を手入力してください")
        sections[sec].append({
            "name": f"{label} {model}", "spec": "\n".join(spec),
            "qty": 1, "unit": "式", "price": price,
        })

    # 制御盤（図面テキスト・制御盤ブロックから）
    if info["panel_texts"] or info["panel_blocks"]:
        spec = ["図面の記載:"] + [f"・{t}" for t in info["panel_texts"]] if info["panel_texts"] else []
        spec = spec or ["図面に制御盤ブロックあり"]
        spec.append("※単価を手入力してください")
        sections[5].append({
            "name": "制御盤", "spec": "\n".join(spec),
            "qty": 1, "unit": "式", "price": 0,
        })

    # ダクト部品（概算）
    duct = duct_estimate(info["dia"])
    if duct["lines"]:
        detail = [
            "★概算（図面からダクト実長は取得できないため下式で算出）",
            f"概算式: 径(mm) × {DUCT_RATE_PER_MM_M}円 × 想定延長(m)",
            f"想定延長: 図面の径注記1件あたり {DUCT_DEFAULT_RUN_M}m",
            "",
        ]
        for l in duct["lines"]:
            detail.append(
                f"φ{l['dia']}: 注記{l['count']}件 → {l['run_m']}m × {l['rate_per_m']:,}円/m = {l['amount']:,}円"
            )
        detail.append("")
        detail.append("※係数は仮値。実長の自動積算にはダクトを専用レイヤーに中心線1本で作図する必要あり")
        sections[6].append({
            "name": "ﾀﾞｸﾄ部品（概算）", "spec": "\n".join(detail),
            "qty": 1, "unit": "式", "price": duct["total"],
        })

    if not sections:
        raise HTTPException(400, "図面から自社製品の型式を抽出できませんでした。ブロック名に型式が入っているか確認してください")

    # ---- 見積を作成（draft・未承認）----
    customer_name = delivery_name = sales_person_name = None
    child_no = None
    po = None
    if project_order_id:
        po = db.query(ProjectOrder).filter(
            pk_or_code(ProjectOrder.id, ProjectOrder.child_no, project_order_id)
        ).first()
        if po:
            customer_name = po.agency_name or po.customer_name
            delivery_name = po.customer_name
            sales_person_name = po.sales_person_name
            child_no = po.child_no

    q = QuotationHeader(
        quotation_no=_gen_quotation_no(db),
        project_order_id=po.id if po else None,
        child_no=child_no,
        customer_name=nfkc(customer_name),
        delivery_name=nfkc(delivery_name),
        title=nfkc(title or (po.project_name if po else None) or f"CAD自動生成: {fname}"),
        issue_date=date.today(),
        sales_person_name=nfkc(sales_person_name),
        tax_display="excluded",
        status="draft",
        internal_notes=(
            f"CAD自動生成（{fname}）\n"
            f"DXF={info['dxf_version']} 単位コード={info['insunits']}\n"
            f"抽出型式: {', '.join(sorted(info['models'])) or 'なし'}\n"
            f"ダクトは概算（径{len(info['dia'])}種）。単価未確定の型式: {', '.join(unmatched) or 'なし'}"
            + ("\n※図面に「既設」の記載あり。見積対象外の機器が含まれていないか確認してください"
               if info["has_existing_note"] else "")
        ),
    )
    db.add(q)
    db.flush()

    line_no = 1
    for sec in sorted(sections):
        for item in sections[sec]:
            db.add(QuotationLineItem(
                quotation_id=q.id, line_no=line_no,
                section=SECTION_NAMES[sec], sub_section=None,
                item_name=nfkc(item["name"]), spec_detail=item["spec"],
                quantity=item["qty"], unit=item["unit"],
                unit_price=item["price"], amount=int(item["price"] * item["qty"]),
                product_type="CAD自動生成",
            ))
            line_no += 1

    subtotal = sum(int(i["price"] * i["qty"]) for s in sections.values() for i in s)
    q.subtotal = subtotal
    q.labor_total = 0
    q.tax_amount = int(subtotal * 0.1)
    q.total_amount = subtotal + int(subtotal * 0.1)
    db.commit()
    db.refresh(q)

    return {
        "id": str(q.id),
        "quotation_no": q.quotation_no,
        "subtotal": subtotal,
        "models": info["models"],
        "duct": {"total": duct["total"], "lines": duct["lines"]},
        "unmatched_models": unmatched,
        "has_existing_note": info["has_existing_note"],
        "warnings": (
            ([f"単価がマスタに無い型式: {', '.join(unmatched)}"] if unmatched else [])
            + (["ダクトは概算です。係数は仮値のため必ず確認してください"] if duct["lines"] else [])
            + (["図面に「既設」の記載があります。見積対象外の機器が含まれていないか確認してください"]
               if info["has_existing_note"] else [])
        ),
    }


@router.get("/approve-by-link")
def approve_by_link(token: str, request: Request, db: Session = Depends(get_db)):
    """メールの承認リンク。有効期限内・未使用のトークンでのみ承認する。

    ブラウザで開かれるため、結果はHTMLで返す。
    """
    def _page(title: str, msg: str, color: str) -> HTMLResponse:
        return HTMLResponse(f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<title>{title}</title></head>
<body style="font-family:'Hiragino Sans','Yu Gothic',sans-serif;background:#f3f4f6;padding:40px">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:28px;box-shadow:0 1px 4px rgba(0,0,0,.1)">
    <h1 style="font-size:20px;color:{color};margin:0 0 12px">{title}</h1>
    <p style="font-size:14px;color:#374151;line-height:1.8;white-space:pre-wrap">{msg}</p>
    <p style="margin-top:20px"><a href="{app_base_url_safe()}" style="color:#2563eb">販売管理システムを開く</a></p>
  </div>
</body></html>""")

    t = db.query(ApprovalToken).filter(ApprovalToken.token == token).first()
    if not t:
        return _page("リンクが無効です", "承認リンクが見つかりません。メールのURLが途中で切れていないかご確認ください。", "#c0392b")
    if t.used_at:
        return _page("このリンクは使用済みです",
                     f"{t.used_at.strftime('%Y/%m/%d %H:%M')} に承認済みです。\n再度承認する場合は画面から操作してください。", "#c0392b")
    if t.expires_at and t.expires_at < datetime.now():
        return _page("リンクの有効期限が切れています",
                     f"承認リンクは発行から{APPROVAL_LINK_HOURS}時間で失効します。\n依頼者に再送を依頼してください。", "#c0392b")

    q = db.query(QuotationHeader).filter(QuotationHeader.id == t.quotation_id).first()
    if not q:
        return _page("見積が見つかりません", "対象の見積が削除された可能性があります。", "#c0392b")
    if (q.approval_status or "none") != "pending":
        return _page("承認待ちではありません",
                     f"現在の状態: {q.approval_status}\n見積の内容が変更されると承認依頼は取り消されます。", "#c0392b")

    q.approval_status = "approved"
    q.approved_at = datetime.now()
    q.approver_name = t.approver_name
    t.used_at = datetime.now()
    t.used_from_ip = (request.client.host if request.client else None)
    db.commit()
    return _page("承認しました",
                 f"{q.quotation_no}　{q.title or ''}\n検印: {t.approver_name}\n\n"
                 "見積書の「draft」透かしが外れ、正式に発行できる状態になりました。", "#15803d")


def app_base_url_safe() -> str:
    from app.mailer import app_base_url
    return app_base_url()


@router.get("/pending-approvals")
def list_pending_approvals(approver_name: Optional[str] = None, db: Session = Depends(get_db)):
    """承認待ちの見積一覧。approver_name を指定するとその人宛のものだけ返す。

    承認依頼は「相手のログイン後の画面に承認待ちとして出る」方式で通知している
    （メール送信は未実装。SMTPの設定が必要なため別途）。
    ※ /{quotation_id} より先に定義すること（ルート衝突防止）
    """
    q = db.query(QuotationHeader).filter(QuotationHeader.approval_status == "pending")
    if approver_name:
        q = q.filter(QuotationHeader.approver_name == nfkc(approver_name))
    rows = q.order_by(desc(QuotationHeader.approval_requested_at)).all()
    return {
        "total": len(rows),
        "items": [{
            "id": str(r.id), "quotation_no": r.quotation_no, "title": r.title,
            "customer_name": r.customer_name, "child_no": r.child_no,
            "approver_name": r.approver_name,
            "created_by_name": r.created_by_name,
            "sales_person_name": r.sales_person_name,
            "net_amount": net_amount(r),
            "approval_requested_at": r.approval_requested_at.isoformat() if r.approval_requested_at else None,
        } for r in rows],
    }


@router.get("/approvers")
def list_approvers(db: Session = Depends(get_db)):
    """承認権限者の候補。ユーザーマスタで機能権限「検印承認者」を付与された人を返す。
    ※ /{quotation_id} より先に定義すること（ルート衝突防止）"""
    from app.roles import users_with_role
    users = users_with_role(db, "approver")
    return {
        "approvers": [u.full_name for u in users],
        "users": [{"id": str(u.id), "full_name": u.full_name, "department": u.department} for u in users],
    }

@router.get("/patterns/bfr-bodies")
def get_bfr_bodies(db: Session = Depends(get_db)):
    items = db.query(EstimateBfrBody).filter(EstimateBfrBody.is_active == True).order_by(EstimateBfrBody.model_code).all()
    result = {}
    for i in items:
        key = i.model_code
        if key not in result:
            result[key] = {"model_code": key, "airflow": i.airflow, "filter_length": i.filter_length, "variants": []}
        result[key]["variants"].append({
            "id": str(i.id), "filter_type": i.filter_type,
            "base_price": int(i.base_price or 0), "filter_price": int(i.filter_price or 0),
            "filter_count": i.filter_count
        })
    return list(result.values())

@router.get("/patterns/bfr-fans/{bfr_model}")
def get_bfr_fans(bfr_model: str, db: Session = Depends(get_db)):
    items = db.query(EstimateBfrFan).filter(EstimateBfrFan.bfr_model == bfr_model, EstimateBfrFan.is_active == True).all()
    return [{"id": str(i.id), "fan_model": i.fan_model, "price": int(i.price or 0), "quantity": i.quantity} for i in items]

@router.get("/patterns/bfr-rvs/{bfr_model}")
def get_bfr_rvs(bfr_model: str, db: Session = Depends(get_db)):
    items = db.query(EstimateBfrRv).filter(EstimateBfrRv.bfr_model == bfr_model, EstimateBfrRv.is_active == True).all()
    return [{"id": str(i.id), "rv_model": i.rv_model, "kw": float(i.kw or 0), "price": int(i.price or 0), "quantity": i.quantity} for i in items]

@router.get("/patterns/bfq")
def get_bfq_patterns(db: Session = Depends(get_db)):
    """BFQ見積パターン一式（系列・本体・排風型式・オプション）をまとめて返す。
    周波数/電圧/シェーカー位置/スイッチは全系列共通の選択肢。"""
    series = db.query(EstimateBfqSeries).filter(EstimateBfqSeries.is_active == True).order_by(EstimateBfqSeries.sort_order).all()
    bodies = db.query(EstimateBfqBody).filter(EstimateBfqBody.is_active == True).order_by(EstimateBfqBody.sort_order).all()
    fans = db.query(EstimateBfqFan).filter(EstimateBfqFan.is_active == True).all()
    opts = db.query(EstimateBfqOption).filter(EstimateBfqOption.is_active == True).order_by(EstimateBfqOption.sort_order).all()
    return {
        "series": [{
            "series": s.series, "indoor_outdoor": s.indoor_outdoor, "flange_type": s.flange_type,
            "maker": s.maker, "slide_base": s.slide_base, "remarks": s.remarks,
            "panel_price": int(s.panel_price or 0),
            "case_breaker": s.case_breaker,
            "case_breaker_price": int(s.case_breaker_price) if s.case_breaker_price is not None else None,
            "push_switch": s.push_switch,
            "push_switch_price": int(s.push_switch_price) if s.push_switch_price is not None else None,
        } for s in series],
        "bodies": [{
            "id": str(b.id), "model_code": b.model_code, "series": b.series,
            "base_price": int(b.base_price) if b.base_price is not None else None,
            "price_note": b.price_note, "fan_kw": float(b.fan_kw or 0),
            "filter_dia": b.filter_dia, "filter_length": b.filter_length, "filter_count": b.filter_count,
            "shaker": b.shaker, "shaker_kw": float(b.shaker_kw) if b.shaker_kw is not None else None,
            "dust_recovery": b.dust_recovery,
        } for b in bodies],
        "fans": [{"series": f.series, "hz": f.hz, "fan_model": f.fan_model} for f in fans],
        "options": [{
            "id": str(o.id), "category": o.category, "series": o.series,
            "option_name": o.option_name, "spec": o.spec,
            "price": int(o.price or 0),
            "unit_price": int(o.unit_price) if o.unit_price is not None else None,
            "is_provisional": bool(o.is_provisional),
        } for o in opts],
        "choices": {
            "hz": [50, 60],
            "voltage": [200, 380, 400, 440],
            "shaker_position": ["標準", "逆勝手"],
            "switch": ["なし", "モーターブレーカー", "モーターブレーカー+押しボタンスイッチ", "制御盤"],
        },
    }


@router.get("/patterns/sca-bodies")
def get_sca_bodies(db: Session = Depends(get_db)):
    items = db.query(EstimateScaBody).filter(EstimateScaBody.is_active == True).order_by(EstimateScaBody.model_code).all()
    return [{
        "id": str(i.id), "model_code": i.model_code, "diameter": i.diameter,
        "capacity": float(i.capacity or 0), "base_price": int(i.base_price or 0),
        "ab_kw": float(i.ab_kw or 0), "sc_count": i.sc_count,
        "sc1_kw": float(i.sc1_kw or 0), "rv1_model": i.rv1_model,
        "rv1_kw": float(i.rv1_kw or 0), "slope_sc": i.slope_sc
    } for i in items]

@router.get("/patterns/pl-fans")
def get_pl_fans(db: Session = Depends(get_db)):
    items = db.query(EstimatePlFan).filter(EstimatePlFan.is_active == True).order_by(EstimatePlFan.model_code, EstimatePlFan.kw).all()
    return [{"id": str(i.id), "model_code": i.model_code, "kw": float(i.kw or 0), "price": int(i.price or 0)} for i in items]

@router.get("/patterns/cyclones")
def get_cyclones(db: Session = Depends(get_db)):
    items = db.query(EstimateCyclone).filter(EstimateCyclone.is_active == True).all()
    return [{"id": str(i.id), "model_code": i.model_code, "shape": i.shape, "material": i.material, "price": int(i.price or 0)} for i in items]

@router.get("/labor-items")
def get_labor_items(db: Session = Depends(get_db)):
    items = db.query(EstimateLaborItem).filter(EstimateLaborItem.is_active == True).order_by(EstimateLaborItem.sort_order).all()
    return [{
        "id": str(i.id), "category": i.category, "item_name": i.item_name,
        "unit": i.unit, "unit_price": int(i.unit_price or 0)
    } for i in items]

# =============================================
# 見積書 CRUD
# =============================================
class LaborDetailIn(BaseModel):
    labor_item_id: Optional[str] = None
    item_name: str
    quantity: float = 0
    unit: str = '人日'
    unit_price: int = 0
    crane_type: Optional[str] = None
    notes: Optional[str] = None
    sort_order: int = 0

class LineItemIn(BaseModel):
    line_no: int
    section: Optional[str] = None
    sub_section: Optional[str] = None
    item_name: str
    spec_detail: Optional[str] = None
    quantity: float = 1
    unit: str = '式'
    unit_price: int = 0
    hide_amount: bool = False          # True=見積書で金額欄を空欄（一式内訳の構成部品）
    amount_text: Optional[str] = None  # 「含まず」等の文字列表示（単価0で運用）
    product_type: Optional[str] = None
    spec_json: Optional[dict] = None

class QuotationHeaderCreate(BaseModel):
    project_order_id: Optional[str] = None
    child_no: Optional[str] = None
    customer_name: Optional[str] = None
    customer_contact: Optional[str] = None
    delivery_name: Optional[str] = None
    delivery_place: Optional[str] = None
    title: Optional[str] = None
    delivery_terms: Optional[str] = None
    payment_terms: Optional[str] = None
    valid_until: Optional[date] = None
    valid_until_text: Optional[str] = None
    tax_display: Optional[str] = None          # included / excluded
    exclusions: Optional[str] = None           # 御見積除外事項（1行1項目）
    issue_date: Optional[date] = None
    sales_person_name: Optional[str] = None
    created_by_name: Optional[str] = None
    approver_name: Optional[str] = None
    discount_amount: int = 0                    # 出精値引（正の値）
    notes: Optional[str] = None
    internal_notes: Optional[str] = None
    expected_updated_at: Optional[str] = None   # 楽観ロック用（読込時の更新日時）
    line_items: List[LineItemIn] = []
    labor_details: List[LaborDetailIn] = []

def _gen_quotation_no(db: Session) -> str:
    # B004修正: 文字列ソートから数値ソートへ変更し、採番競合を防ぐadvisory lockを追加
    from sqlalchemy import text as sa_text, cast, Integer
    db.execute(sa_text("SELECT pg_advisory_xact_lock(hashtext('quotation_no_lock'))"))
    year = datetime.now().year
    prefix = f"Q{year}-"
    rows = db.execute(
        sa_text(f"SELECT quotation_no FROM quotation_headers WHERE quotation_no LIKE :prefix ORDER BY CAST(SPLIT_PART(quotation_no, '-', 2) AS INTEGER) DESC LIMIT 1"),
        {"prefix": f"{prefix}%"}
    ).fetchone()
    seq = int(rows[0].split("-")[-1]) + 1 if rows else 1
    return f"{prefix}{seq:04d}"

def _calc_totals(line_items, labor_details, discount=0):
    subtotal = sum(int(i.unit_price * i.quantity) for i in line_items)
    labor_total = sum(int(l.unit_price * l.quantity) for l in labor_details)
    total_before_tax = subtotal + labor_total - int(discount or 0)
    tax = int(total_before_tax * 0.1)
    return subtotal, labor_total, tax, total_before_tax + tax

def _q_to_dict(q: QuotationHeader) -> dict:
    return {
        "id": str(q.id), "quotation_no": q.quotation_no,
        "project_order_id": str(q.project_order_id) if q.project_order_id else None,
        "child_no": q.child_no, "customer_name": q.customer_name,
        "customer_contact": q.customer_contact,
        "delivery_name": q.delivery_name, "delivery_place": q.delivery_place, "title": q.title,
        "delivery_terms": q.delivery_terms, "payment_terms": q.payment_terms,
        "valid_until": q.valid_until.isoformat() if q.valid_until else None,
        "valid_until_text": q.valid_until_text,
        "tax_display": q.tax_display or "included",
        "exclusions": q.exclusions,
        "issue_date": q.issue_date.isoformat() if q.issue_date else None,
        "sales_person_name": q.sales_person_name,
        "created_by_name": q.created_by_name, "approver_name": q.approver_name,
        "approval_status": q.approval_status or "none",
        "approval_requested_at": q.approval_requested_at.isoformat() if q.approval_requested_at else None,
        "approved_at": q.approved_at.isoformat() if q.approved_at else None,
        "subtotal": int(q.subtotal or 0),
        "discount_amount": int(q.discount_amount or 0),
        "net_amount": net_amount(q),
        "tax_rate": float(q.tax_rate or 10),
        "tax_amount": int(q.tax_amount or 0), "total_amount": int(q.total_amount or 0),
        "labor_total": int(q.labor_total or 0), "status": q.status,
        "notes": q.notes, "internal_notes": q.internal_notes,
        "is_adopted": q.status == "adopted",
        # 工番/単番は案件子IDで登録された区分（金額による自動判定は廃止）
        "ticket_type": q.project_order.ticket_type if getattr(q, "project_order", None) else None,
        "created_at": q.created_at.isoformat() if q.created_at else None,
        "updated_at": q.updated_at.isoformat() if q.updated_at else None,
        "line_items": sorted([{
            "id": str(i.id), "line_no": i.line_no, "section": i.section,
            "sub_section": i.sub_section, "item_name": i.item_name,
            "spec_detail": i.spec_detail, "quantity": float(i.quantity or 1),
            "unit": i.unit, "unit_price": int(i.unit_price or 0),
            "amount": int(i.amount or 0),
            "hide_amount": bool(i.hide_amount), "amount_text": i.amount_text,
            "product_type": i.product_type,
            "spec_json": i.spec_json
        } for i in q.line_items], key=lambda x: x["line_no"]),
        "labor_details": sorted([{
            "id": str(l.id), "item_name": l.item_name,
            "quantity": float(l.quantity or 0), "unit": l.unit,
            "unit_price": int(l.unit_price or 0), "amount": int(l.amount or 0),
            "crane_type": l.crane_type, "notes": l.notes, "sort_order": l.sort_order
        } for l in q.labor_details], key=lambda x: x["sort_order"])
    }

@router.get("/")
def list_quotations(
    child_no: Optional[str] = None, project_order_id: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1), per_page: int = Query(20),
    db: Session = Depends(get_db)
):
    q = db.query(QuotationHeader).options(joinedload(QuotationHeader.line_items), joinedload(QuotationHeader.labor_details))
    if child_no: q = q.filter(QuotationHeader.child_no == child_no)
    if project_order_id: q = q.filter(QuotationHeader.project_order_id == project_order_id)
    if search:
        q = q.filter(or_(
            QuotationHeader.quotation_no.ilike(f"%{search}%"),
            QuotationHeader.customer_name.ilike(f"%{search}%"),
            QuotationHeader.title.ilike(f"%{search}%"),
            QuotationHeader.child_no.ilike(f"%{search}%"),
        ))
    total = q.count()
    items = q.order_by(desc(QuotationHeader.created_at)).offset((page-1)*per_page).limit(per_page).all()
    return {"total": total, "items": [_q_to_dict(i) for i in items]}

@router.post("/", status_code=201)
def create_quotation(data: QuotationHeaderCreate, db: Session = Depends(get_db)):
    subtotal, labor_total, tax, total = _calc_totals(data.line_items, data.labor_details, data.discount_amount)

    # 子IDから案件情報を自動参照
    customer_name = data.customer_name
    delivery_name = data.delivery_name
    sales_person_name = data.sales_person_name
    title = data.title
    if data.project_order_id:
        po = db.query(ProjectOrder).filter(ProjectOrder.id == data.project_order_id).first()
        if po:
            # 注文主＝商社優先（商社が無ければ納入先＝エンドユーザー）／納入先＝エンドユーザー
            customer_name = customer_name or po.agency_name or po.customer_name
            delivery_name = delivery_name or po.customer_name
            sales_person_name = sales_person_name or po.sales_person_name
            title = title or po.project_name

    q = QuotationHeader(
        quotation_no=_gen_quotation_no(db),
        project_order_id=data.project_order_id,
        child_no=data.child_no,
        customer_name=nfkc(customer_name), customer_contact=nfkc(data.customer_contact),
        delivery_name=nfkc(delivery_name), delivery_place=nfkc(data.delivery_place),
        title=nfkc(title), delivery_terms=nfkc(data.delivery_terms),
        payment_terms=nfkc(data.payment_terms), valid_until=data.valid_until,
        valid_until_text=nfkc(data.valid_until_text),
        tax_display=data.tax_display or "included", exclusions=nfkc(data.exclusions),
        issue_date=data.issue_date or date.today(),
        sales_person_name=nfkc(sales_person_name),
        created_by_name=nfkc(data.created_by_name), approver_name=nfkc(data.approver_name),
        subtotal=subtotal, discount_amount=data.discount_amount,
        tax_amount=tax, total_amount=total, labor_total=labor_total,
        notes=nfkc(data.notes), internal_notes=nfkc(data.internal_notes),
    )
    db.add(q)
    db.flush()

    for item in data.line_items:
        db.add(QuotationLineItem(
            quotation_id=q.id, line_no=item.line_no, section=nfkc(item.section),
            sub_section=nfkc(item.sub_section), item_name=nfkc(item.item_name),
            spec_detail=nfkc(item.spec_detail), quantity=item.quantity, unit=item.unit,
            unit_price=item.unit_price, amount=int(item.unit_price * item.quantity),
            hide_amount=item.hide_amount, amount_text=nfkc(item.amount_text),
            product_type=item.product_type, spec_json=item.spec_json
        ))

    for labor in data.labor_details:
        db.add(QuotationLaborDetail(
            quotation_id=q.id, labor_item_id=labor.labor_item_id,
            item_name=nfkc(labor.item_name), quantity=labor.quantity, unit=labor.unit,
            unit_price=labor.unit_price, amount=int(labor.unit_price * labor.quantity),
            crane_type=labor.crane_type, notes=nfkc(labor.notes), sort_order=labor.sort_order
        ))

    db.commit()
    db.refresh(q)
    return _q_to_dict(q)

@router.post("/{quotation_id}/duplicate")
def duplicate_quotation(quotation_id: str, data: dict, db: Session = Depends(get_db)):
    """見積を複製。案件子IDの紐付けは必須（複製先の子IDを指定）。"""
    src = db.query(QuotationHeader).options(
        joinedload(QuotationHeader.line_items), joinedload(QuotationHeader.labor_details)
    ).filter(QuotationHeader.id == quotation_id).first()
    if not src: raise HTTPException(404, "複製元の見積が見つかりません")

    project_order_id = (data or {}).get("project_order_id")
    if not project_order_id:
        raise HTTPException(400, "案件子IDの選択は必須です")
    po = db.query(ProjectOrder).filter(ProjectOrder.id == project_order_id).first()
    if not po: raise HTTPException(404, "案件子IDが見つかりません")

    # 注文主＝商社優先／納入先＝エンドユーザー（新規作成時と同じ挙動）。無ければ複製元を踏襲。
    customer_name = po.agency_name or po.customer_name or src.customer_name
    delivery_name = po.customer_name or src.delivery_name
    title = po.project_name or src.title
    sales_person_name = po.sales_person_name or src.sales_person_name

    new_q = QuotationHeader(
        quotation_no=_gen_quotation_no(db),
        project_order_id=po.id, child_no=po.child_no,
        customer_name=customer_name, customer_contact=src.customer_contact,
        delivery_name=delivery_name, delivery_place=src.delivery_place,
        title=title, delivery_terms=src.delivery_terms, payment_terms=src.payment_terms,
        valid_until=src.valid_until, valid_until_text=src.valid_until_text,
        tax_display=src.tax_display, exclusions=src.exclusions,
        issue_date=date.today(),
        sales_person_name=sales_person_name,
        created_by_name=src.created_by_name, approver_name=src.approver_name,
        subtotal=src.subtotal, discount_amount=src.discount_amount,
        tax_rate=src.tax_rate, tax_amount=src.tax_amount,
        total_amount=src.total_amount, labor_total=src.labor_total,
        notes=src.notes, internal_notes=src.internal_notes,
        status="draft",  # 複製は未承認から開始（approval_statusはデフォルトnone）
    )
    db.add(new_q); db.flush()
    for it in src.line_items:
        db.add(QuotationLineItem(
            quotation_id=new_q.id, line_no=it.line_no, section=it.section,
            sub_section=it.sub_section, item_name=it.item_name, spec_detail=it.spec_detail,
            quantity=it.quantity, unit=it.unit, unit_price=it.unit_price, amount=it.amount,
            hide_amount=it.hide_amount, amount_text=it.amount_text,
            product_type=it.product_type, spec_json=it.spec_json,
        ))
    for l in src.labor_details:
        db.add(QuotationLaborDetail(
            quotation_id=new_q.id, labor_item_id=l.labor_item_id, item_name=l.item_name,
            quantity=l.quantity, unit=l.unit, unit_price=l.unit_price, amount=l.amount,
            crane_type=l.crane_type, notes=l.notes, sort_order=l.sort_order,
        ))
    db.commit(); db.refresh(new_q)
    return {"id": str(new_q.id), "quotation_no": new_q.quotation_no, "child_no": new_q.child_no}

@router.get("/order-tickets")
def list_order_tickets(
    search: str = None, ticket_type: str = None, status_filter: str = "active",
    per_page: int = 50, db: Session = Depends(get_db)
):
    """受注票一覧"""
    q = db.query(OrderTicket).options(joinedload(OrderTicket.project_order))
    if search:
        q = q.filter(
            or_(
                OrderTicket.ticket_no.ilike(f"%{search}%"),
                OrderTicket.customer_name.ilike(f"%{search}%"),
                OrderTicket.child_no.ilike(f"%{search}%"),
            )
        )
    if ticket_type:
        q = q.filter(OrderTicket.ticket_type == ticket_type)
    if status_filter == "active":
        q = q.filter(OrderTicket.is_active == True)
    elif status_filter == "inactive":
        q = q.filter(OrderTicket.is_active == False)
    total = q.count()
    items = q.order_by(OrderTicket.created_at.desc()).limit(per_page).all()
    return {
        "total": total,
        "items": [
            {
                "id": str(t.id),
                "ticket_no": t.ticket_no,
                "ticket_type": t.ticket_type,
                "child_no": t.child_no,
                "customer_name": t.customer_name,
                "delivery_name": t.delivery_name,
                "sales_person_name": t.sales_person_name,
                "total_amount": int(t.total_amount or 0),
                "order_date": str(t.order_date) if t.order_date else None,
                "has_order_sheet": t.has_order_sheet,
                "has_drawing": t.has_drawing,
                "has_contract": t.has_contract,
                "delivery_date": str(t.delivery_date) if t.delivery_date else None,
                "advance_payment": int(t.advance_payment) if t.advance_payment is not None else None,
                "advance_payments": t.advance_payments or [],
                "shipping_method": t.shipping_method,
                "parts_input_status": t.parts_input_status,
                "parts_order_status": t.parts_order_status,
                "stock_minus_status": t.stock_minus_status,
                # 子ID（案件）から取得する日付
                "expected_shipment_date": str(t.project_order.expected_shipment_date) if t.project_order and t.project_order.expected_shipment_date else None,
                "customer_delivery_date": str(t.project_order.customer_delivery_date) if t.project_order and t.project_order.customer_delivery_date else None,
                "sales_date": str(t.project_order.sales_date) if t.project_order and t.project_order.sales_date else None,
                "quotation_id": str(t.quotation_id) if t.quotation_id else None,
                "quotation_no": t.quotation.quotation_no if t.quotation else None,
                "is_active": t.is_active,
            }
            for t in items
        ]
    }


def _ot_filter(ticket_id: str):
    """UUID・受注番号どちらでも受注票を引けるフィルタ。"""
    return pk_or_code(OrderTicket.id, OrderTicket.ticket_no, ticket_id)

@router.put("/order-ticket/{ticket_id}")
def update_order_ticket(ticket_id: str, data: dict, db: Session = Depends(get_db)):
    """受注票の受注時項目（注文書有無・納期・前受金）と種別（工番/単番）を更新。
    種別は発行時に税抜300万円で自動判定されるが、ここで手動変更できる。"""
    t = db.query(OrderTicket).filter(_ot_filter(ticket_id)).first()
    if not t:
        raise HTTPException(404, "受注票が見つかりません")
    if data.get("ticket_type") in ("koban", "tanban"):
        t.ticket_type = data["ticket_type"]
        # 区分の正は案件子ID側。受注票だけ変えると次回発行で元に戻るため両方を更新する
        if t.project_order_id:
            po = db.query(ProjectOrder).filter(ProjectOrder.id == t.project_order_id).first()
            if po:
                po.ticket_type = data["ticket_type"]
    if "has_order_sheet" in data:
        t.has_order_sheet = data["has_order_sheet"]
    if "has_drawing" in data:
        t.has_drawing = data["has_drawing"]
    if "has_contract" in data:
        t.has_contract = data["has_contract"]
    for _f in ("parts_input_status", "parts_order_status", "stock_minus_status"):
        if _f in data:
            v = data[_f]
            setattr(t, _f, v if v in ("未", "済") else None)
    if "delivery_date" in data:
        t.delivery_date = date.fromisoformat(data["delivery_date"]) if data["delivery_date"] else None
    if "advance_payment" in data:
        v = data["advance_payment"]
        t.advance_payment = int(v) if v not in (None, "") else None
    if "advance_payments" in data:
        # 前受金 最大3回 [{date, amount}]。空要素は除外
        rows = data["advance_payments"] or []
        t.advance_payments = [r for r in rows if r and (r.get("date") or r.get("amount"))][:3]
    if "shipping_method" in data:
        t.shipping_method = data["shipping_method"] or None
    if "order_date" in data:
        t.order_date = date.fromisoformat(data["order_date"]) if data["order_date"] else None
    if "notes" in data:
        t.notes = data["notes"]
    db.commit(); db.refresh(t)
    return {
        "id": str(t.id), "ticket_no": t.ticket_no, "ticket_type": t.ticket_type,
        "has_order_sheet": t.has_order_sheet,
        "has_drawing": t.has_drawing,
        "has_contract": t.has_contract,
        "delivery_date": str(t.delivery_date) if t.delivery_date else None,
        "advance_payment": int(t.advance_payment) if t.advance_payment is not None else None,
        "advance_payments": t.advance_payments or [],
        "shipping_method": t.shipping_method,
        "parts_input_status": t.parts_input_status,
        "parts_order_status": t.parts_order_status,
        "stock_minus_status": t.stock_minus_status,
        "order_date": str(t.order_date) if t.order_date else None,
    }


@router.get("/{quotation_id}")
def get_quotation(quotation_id: str, db: Session = Depends(get_db)):
    q = db.query(QuotationHeader).options(
        joinedload(QuotationHeader.line_items), joinedload(QuotationHeader.labor_details)
    ).filter(pk_or_code(QuotationHeader.id, QuotationHeader.quotation_no, quotation_id)).first()
    if not q: raise HTTPException(404)
    return _q_to_dict(q)

@router.put("/{quotation_id}")
def update_quotation(quotation_id: str, data: QuotationHeaderCreate, db: Session = Depends(get_db)):
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)
    # 楽観ロック: 読込時の更新日時と現在値が異なれば409
    if data.expected_updated_at and q.updated_at and q.updated_at.isoformat() != data.expected_updated_at:
        raise HTTPException(409, "他のユーザーが更新しました。最新の内容を再読込してから保存してください。")
    subtotal, labor_total, tax, total = _calc_totals(data.line_items, data.labor_details, data.discount_amount)
    for k, v in data.dict(exclude={"line_items", "labor_details", "expected_updated_at"}, exclude_none=True).items():
        setattr(q, k, nfkc(v))
    q.subtotal = subtotal; q.labor_total = labor_total; q.tax_amount = tax; q.total_amount = total
    # 内容が変わるため、承認済み/承認待ちは未依頼に戻す（承認後の無断変更を防ぐ）
    if (q.approval_status or "none") != "none":
        q.approval_status = "none"
        q.approval_requested_at = None
        q.approved_at = None
    for i in q.line_items: db.delete(i)
    for l in q.labor_details: db.delete(l)
    db.flush()
    for item in data.line_items:
        db.add(QuotationLineItem(
            quotation_id=q.id, line_no=item.line_no, section=nfkc(item.section),
            sub_section=nfkc(item.sub_section), item_name=nfkc(item.item_name),
            spec_detail=nfkc(item.spec_detail), quantity=item.quantity, unit=item.unit,
            unit_price=item.unit_price, amount=int(item.unit_price * item.quantity),
            hide_amount=item.hide_amount, amount_text=nfkc(item.amount_text),
            product_type=item.product_type, spec_json=item.spec_json
        ))
    for labor in data.labor_details:
        db.add(QuotationLaborDetail(
            quotation_id=q.id, labor_item_id=labor.labor_item_id,
            item_name=nfkc(labor.item_name), quantity=labor.quantity, unit=labor.unit,
            unit_price=labor.unit_price, amount=int(labor.unit_price * labor.quantity),
            crane_type=labor.crane_type, notes=nfkc(labor.notes), sort_order=labor.sort_order
        ))
    db.commit(); db.refresh(q)
    return _q_to_dict(q)

@router.delete("/{quotation_id}", status_code=204)
def delete_quotation(quotation_id: str, db: Session = Depends(get_db)):
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)
    db.delete(q); db.commit()

# =============================================
# B013修正: 見積採用・採用解除エンドポイント
# =============================================
@router.post("/{quotation_id}/adopt")
def adopt_quotation(quotation_id: str, db: Session = Depends(get_db)):
    """見積を採用: statusをadoptedにし、子IDに採用見積情報を反映する"""
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404, "見積が見つかりません")
    if not q.project_order_id: raise HTTPException(400, "この見積は子IDに紐付いていません")

    # 同じ子IDの他の見積を draft に戻す
    db.query(QuotationHeader).filter(
        QuotationHeader.project_order_id == q.project_order_id,
        QuotationHeader.id != q.id
    ).update({"status": "draft"}, synchronize_session=False)

    q.status = "adopted"

    # 子IDに採用見積情報を反映
    po = db.query(ProjectOrder).filter(ProjectOrder.id == q.project_order_id).first()
    if po:
        po.quotation_no = q.quotation_no
        po.quotation_total = net_amount(q)
        po.quotation_amount = net_amount(q)
        po.quotation_issue_date = q.issue_date
        if po.status in ("営業中", None):
            po.status = "内示"
        db.flush()
        _sync_project_final_amount(po, db)

    db.commit()
    return {"message": "採用しました", "child_no": po.child_no if po else None, "quotation_no": q.quotation_no}

@router.delete("/{quotation_id}/adopt")
def unadopt_quotation(quotation_id: str, db: Session = Depends(get_db)):
    """見積採用を解除: statusをdraftに戻す"""
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404, "見積が見つかりません")
    q.status = "draft"
    db.commit()
    return {"message": "採用を解除しました"}

# =============================================
# 承認ワークフロー（会議2026-07-17）
# 作成者が承認者を選択して依頼 → 承認前の印刷は「draft」透かし → 承認で正式発行
# =============================================
@router.post("/{quotation_id}/request-approval")
def request_approval(quotation_id: str, data: dict, db: Session = Depends(get_db)):
    """承認依頼: 検印者（承認者）を指定して承認待ちにする"""
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404, "見積が見つかりません")
    approver = (data or {}).get("approver_name") or q.approver_name
    if not approver:
        raise HTTPException(400, "検印者（承認者）を選択してください")
    # 検印承認者の権限を持つ人か検証（ユーザー管理で権限を外された人を弾く）
    from app.roles import users_with_role
    approver = nfkc(approver)
    if approver not in [u.full_name for u in users_with_role(db, "approver")]:
        raise HTTPException(
            400,
            f"「{approver}」は検印承認者の権限を持っていません。"
            "ユーザー管理で機能権限「検印承認者」を付与してください",
        )
    q.approver_name = approver
    q.approval_status = "pending"
    q.approval_requested_at = datetime.now()
    q.approved_at = None

    # 承認リンク用トークン（72時間・1回限り）。古い未使用トークンは無効化する
    import secrets
    from datetime import timedelta
    db.query(ApprovalToken).filter(
        ApprovalToken.quotation_id == q.id, ApprovalToken.used_at.is_(None)
    ).update({"expires_at": datetime.now()}, synchronize_session=False)
    tok = ApprovalToken(
        token=secrets.token_urlsafe(32), quotation_id=q.id, approver_name=approver,
        expires_at=datetime.now() + timedelta(hours=APPROVAL_LINK_HOURS),
    )
    db.add(tok)
    db.commit()

    mail = _send_approval_mail(q, approver, tok.token, db)
    msg = f"{q.approver_name} に承認依頼しました"
    if mail.get("sent"):
        msg += f"（{mail.get('to')} にメール送信）"
    else:
        msg += f"（メールは送信していません: {mail.get('reason')}）"
    result = {"message": msg, "approval_status": q.approval_status, "mail": mail}
    # メールが送れないときは、承認リンクを画面から伝えられるよう返す
    # （送信できた場合はメール本文にのみ載せ、レスポンスには含めない）
    if not mail.get("sent"):
        from app.mailer import api_base_url
        result["approve_url"] = f"{api_base_url()}/estimate-quotations/approve-by-link?token={tok.token}"
    return result


def _send_approval_mail(q: QuotationHeader, approver: str, token: str, db: Session) -> dict:
    """承認依頼メールを送る。見積書と社内工数試算をPDFで添付し、承認リンクを載せる。

    メールが送れなくても承認依頼自体は成立させる（画面の承認待ちバナーで通知される）。
    """
    from app.mailer import send_mail, app_base_url, api_base_url, mail_configured
    from app.pdf import html_to_pdf
    from app.db.models import User

    if not mail_configured():
        return {"sent": False, "reason": "メール未設定（Renderの環境変数 MAIL_FROM / MAIL_APP_PASSWORD を登録してください）"}

    user = db.query(User).filter(User.full_name == approver, User.is_active == True).first()
    if not user or not user.email:
        return {"sent": False, "reason": f"{approver} のメールアドレスが未登録です"}

    base = app_base_url()
    approve_url = f"{api_base_url()}/estimate-quotations/approve-by-link?token={token}"
    detail_url = f"{base}/estimates/{q.id}/edit"

    amount = net_amount(q)
    body = f"""{approver} 様

見積の承認をお願いします。

  見積番号 : {q.quotation_no}
  件名     : {q.title or '—'}
  注文主   : {q.customer_name or '—'}
  金額     : ¥{amount:,}（税抜）
  依頼者   : {q.created_by_name or q.sales_person_name or '—'}

▼ このリンクを開くと承認が完了します（有効期限 {APPROVAL_LINK_HOURS} 時間・1回限り）
{approve_url}

▼ 内容を確認してから承認する場合はこちら（ログインが必要です）
{detail_url}

添付の見積書をご確認ください。社内工数試算は社内資料のため、取扱いにご注意ください。
承認されるまで、見積書には「draft」の透かしが入ります。

--
井上電設 販売管理システム（自動送信）
"""
    # 添付（PDFを作れない環境ではHTMLで代替する）
    attachments = []
    q_html = _build_quotation_html(q, is_draft=True)
    l_html = _build_labor_html(q, db)
    for name, html in ((f"{q.quotation_no}_見積書", q_html), (f"{q.quotation_no}_社内工数試算", l_html)):
        blob = html_to_pdf(html)
        if blob:
            attachments.append((f"{name}.pdf", blob, "pdf"))
        else:
            attachments.append((f"{name}.html", html.encode("utf-8"), "html"))

    r = send_mail(user.email, f"【承認依頼】{q.quotation_no} {q.title or ''}（¥{amount:,}）", body, attachments)
    r["to"] = user.email
    r["attachments"] = [a[0] for a in attachments]
    return r


@router.post("/{quotation_id}/approve")
def approve_quotation(quotation_id: str, db: Session = Depends(get_db)):
    """承認: draft透かしが外れ、正式発行が可能になる"""
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404, "見積が見つかりません")
    if not q.approver_name:
        raise HTTPException(400, "検印者（承認者）が設定されていません")
    q.approval_status = "approved"
    q.approved_at = datetime.now()
    db.commit()
    return {"message": "承認しました", "approval_status": q.approval_status}

@router.post("/{quotation_id}/reject-approval")
def reject_approval(quotation_id: str, db: Session = Depends(get_db)):
    """差戻し/承認取消: 未依頼状態に戻す（透かしが復活する）"""
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404, "見積が見つかりません")
    q.approval_status = "none"
    q.approval_requested_at = None
    q.approved_at = None
    db.commit()
    return {"message": "差し戻しました", "approval_status": q.approval_status}

# =============================================
# PDF出力(ケイテック形式)
# =============================================
@router.get("/{quotation_id}/pdf")
def export_pdf(quotation_id: str, format: str = "html", db: Session = Depends(get_db)):
    """見積書。既定はHTML（ブラウザで印刷）。?format=pdf でPDFの実体を返す（メール添付用）"""
    q = db.query(QuotationHeader).options(
        joinedload(QuotationHeader.line_items), joinedload(QuotationHeader.labor_details)
    ).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)

    # draft透かし: 承認完了までは印刷可だが「draft」表示（会議2026-07-17）
    html = _build_quotation_html(q, is_draft=((q.approval_status or 'none') != 'approved'))
    if format == "pdf":
        from app.pdf import html_to_pdf
        blob = html_to_pdf(html)
        if blob:
            return StreamingResponse(
                io.BytesIO(blob), media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename={q.quotation_no}.pdf"})
    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")),
        media_type="text/html",
        headers={"Content-Disposition": f"inline; filename={q.quotation_no}.html"}
    )

def _build_quotation_html(q: QuotationHeader, is_draft: bool = False) -> str:
    # 「draft」透かし（position:fixedで印刷全ページに出る。承認後は消える）
    draft_watermark = ('''
<div style="position:fixed;top:38%;left:8%;right:8%;text-align:center;z-index:999;pointer-events:none;
    font-size:110px;font-weight:bold;color:rgba(200,30,30,0.16);transform:rotate(-18deg);letter-spacing:30px">draft</div>
''' if is_draft else '')

    def _amt_cell(item) -> str:
        """金額欄の表示: 文字列指定 > 金額非表示 > 通常"""
        if item.amount_text:
            return item.amount_text
        if item.hide_amount:
            return " "
        return f"¥{int(item.amount or 0):,}"

    def _uprice_cell(item) -> str:
        if item.amount_text or item.hide_amount or not item.unit_price:
            return " "
        return f"¥{int(item.unit_price):,}"

    def _item_row(no: str, item, indent: int = 0) -> str:
        pad = "padding:4px 8px" + (f" 4px {8 + indent * 14}px" if indent else "")
        return f"""
            <tr>
                <td style="text-align:center;border:1px solid #ccc;padding:4px 8px">{no}</td>
                <td style="border:1px solid #ccc;{pad}">{item.item_name}</td>
                <td style="border:1px solid #ccc;padding:4px 8px;font-size:11px;white-space:pre-wrap">{item.spec_detail or ''}</td>
                <td style="text-align:center;border:1px solid #ccc;padding:4px 8px">{int(item.quantity or 1)}</td>
                <td style="text-align:center;border:1px solid #ccc;padding:4px 8px">{item.unit or '式'}</td>
                <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">{_uprice_cell(item)}</td>
                <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">{_amt_cell(item)}</td>
            </tr>"""

    items_html = ""
    sections = {}
    for item in sorted(q.line_items, key=lambda x: x.line_no):
        sec = item.section or ""
        if sec not in sections:
            sections[sec] = []
        sections[sec].append(item)

    for sec_no, (sec, items) in enumerate(sections.items(), 1):
        sec_total = sum(int(i.amount or 0) for i in items)
        # 内訳を持たない大項目（明細1行・中分類なし）は、見出し行と小計行を出さず
        # 大項目番号のまま1行で表示する。原本（ケイテック様 大項目2・5〜10）の様式。
        # これをしないと「見出し＋子行1つ＋小計」で同じ金額が3行並んでしまう。
        if len(items) == 1 and not items[0].sub_section:
            items_html += _item_row(str(sec_no), items[0])
            continue
        # 大分類の見出し行（番号付き）
        items_html += f"""
            <tr style="background:#e8eef5;font-weight:bold">
                <td style="text-align:center;border:1px solid #ccc;padding:4px 8px">{sec_no}</td>
                <td colspan="6" style="border:1px solid #ccc;padding:4px 8px">{sec or '（未分類）'}</td>
            </tr>"""
        # 3階層番号（1-1-1形式・会議2026-07-17決定）:
        # 中分類(sub_section)が連続する複数行 → 見出し行 i-j（金額なし）＋ 子行 i-j-k
        # 単独行 → 従来どおり i-j
        groups = []  # [ [sub_sectionまたはNone, [items...]] ] 連続する同一中分類でまとめる
        for item in items:
            key = item.sub_section or None
            if groups and groups[-1][0] == key and key is not None:
                groups[-1][1].append(item)
            else:
                groups.append([key, [item]])
        item_no = 1  # 大分類ごとに 1〜 で付番
        for key, gitems in groups:
            if key is not None and len(gitems) > 1:
                # 中分類の見出し行（金額なし）
                items_html += f"""
            <tr style="background:#f3f6fa;font-weight:bold">
                <td style="text-align:center;border:1px solid #ccc;padding:4px 8px">{sec_no}-{item_no}</td>
                <td colspan="6" style="border:1px solid #ccc;padding:4px 8px">{key}</td>
            </tr>"""
                for sub_no, item in enumerate(gitems, 1):
                    items_html += _item_row(f"{sec_no}-{item_no}-{sub_no}", item, indent=1)
                item_no += 1
            else:
                for item in gitems:
                    items_html += _item_row(f"{sec_no}-{item_no}", item)
                    item_no += 1
        items_html += f"""
            <tr style="background:#f5f5f5;font-weight:bold">
                <td colspan="6" style="text-align:right;border:1px solid #ccc;padding:4px 8px">【{sec_no}】{sec or '（未分類）'} 小計金額</td>
                <td style="text-align:right;border:1px solid #ccc;padding:4px 8px">¥{sec_total:,}</td>
            </tr>"""

    # 社内工数の内訳は顧客向け見積書には出さない（金額は「その他」として大分類に計上）

    # ===== 頭紙（大分類別の内訳サマリー・番号付き）=====
    section_rows = ""
    for sec_no, (sec, items) in enumerate(sections.items(), 1):
        label = sec or "（未分類）"
        sec_total = sum(int(i.amount or 0) for i in items)
        section_rows += f'''<tr>
            <td style="border:1px solid #ccc;padding:6px 12px;text-align:center">{sec_no}</td>
            <td style="border:1px solid #ccc;padding:6px 12px">{label}</td>
            <td style="border:1px solid #ccc;padding:6px 12px;text-align:right">¥{sec_total:,}</td></tr>'''
    # 工数は大分類の続き番号で「その他」として計上
    if q.labor_total:
        section_rows += f'''<tr>
            <td style="border:1px solid #ccc;padding:6px 12px;text-align:center">{len(sections) + 1}</td>
            <td style="border:1px solid #ccc;padding:6px 12px">その他</td>
            <td style="border:1px solid #ccc;padding:6px 12px;text-align:right">¥{int(q.labor_total):,}</td></tr>'''

    # ===== 税抜/税込 表示 =====
    _tax_excluded = (q.tax_display or "included") == "excluded"
    _discount = int(q.discount_amount or 0)
    _subtotal_all = int((q.subtotal or 0) + (q.labor_total or 0))   # 値引前小計
    _net_total = _subtotal_all - _discount                          # 値引後（税抜）
    grand_total = _net_total if _tax_excluded else int(q.total_amount or 0)
    tax_label = "(税抜)" if _tax_excluded else "(消費税込み)"
    tax_note = ('<div style="margin-top:8px;font-size:11px">※上記金額には消費税は含まれておりません。</div>'
                if _tax_excluded else '')
    # 出精値引行（原本様式: 小計金額 → 出精値引 → 合計金額）
    discount_row = f'''
    <tr>
      <td colspan="2" style="border:1px solid #ccc;padding:6px 12px;text-align:right">出精値引</td>
      <td style="border:1px solid #ccc;padding:6px 12px;text-align:right;color:#c0392b">-¥{_discount:,}</td></tr>''' if _discount else ''
    # 税抜表示のときは消費税行を出さない（合計＝税抜金額）。頭紙と明細でcolspanが異なる
    tax_row = '' if _tax_excluded else f'''
    <tr>
      <td colspan="2" style="border:1px solid #ccc;padding:6px 12px;text-align:right">消費税({int(q.tax_rate or 10)}%)</td>
      <td style="border:1px solid #ccc;padding:6px 12px;text-align:right">¥{int(q.tax_amount or 0):,}</td></tr>'''
    # 工数が無い見積で「その他 ¥0」を出さない（頭紙の内訳と同じ条件）
    labor_row_detail = f'''
  <tr style="font-weight:bold">
    <td colspan="6" style="text-align:right;border:1px solid #ccc;padding:5px 8px">その他</td>
    <td style="text-align:right;border:1px solid #ccc;padding:5px 8px">¥{int(q.labor_total or 0):,}</td>
  </tr>''' if q.labor_total else ''
    discount_row_detail = f'''
  <tr style="font-weight:bold">
    <td colspan="6" style="text-align:right;border:1px solid #ccc;padding:5px 8px">出精値引</td>
    <td style="text-align:right;border:1px solid #ccc;padding:5px 8px;color:#c0392b">-¥{_discount:,}</td>
  </tr>''' if _discount else ''
    tax_row_detail = '' if _tax_excluded else f'''
  <tr style="font-weight:bold">
    <td colspan="6" style="text-align:right;border:1px solid #ccc;padding:5px 8px">消費税({int(q.tax_rate or 10)}%)</td>
    <td style="text-align:right;border:1px solid #ccc;padding:5px 8px">¥{int(q.tax_amount or 0):,}</td>
  </tr>'''
    # 検印・担当・作成の3枠（原本様式。頭紙右上）
    stamp_box = f'''
  <table style="border-collapse:collapse;font-size:11px;margin-left:auto;margin-bottom:6px;text-align:center">
    <tr>
      <td style="border:1px solid #999;padding:2px 14px;background:#f5f5f5">検 印</td>
      <td style="border:1px solid #999;padding:2px 14px;background:#f5f5f5">担 当</td>
      <td style="border:1px solid #999;padding:2px 14px;background:#f5f5f5">作 成</td>
    </tr>
    <tr>
      <td style="border:1px solid #999;padding:6px 8px;min-width:64px">{(q.approver_name or ' ') if (q.approval_status or 'none') == 'approved' else ' '}</td>
      <td style="border:1px solid #999;padding:6px 8px;min-width:64px">{q.sales_person_name or ' '}</td>
      <td style="border:1px solid #999;padding:6px 8px;min-width:64px">{q.created_by_name or ' '}</td>
    </tr>
  </table>'''

    # ===== 御見積除外事項（1行1項目）=====
    _exc = [l.strip() for l in (q.exclusions or "").splitlines() if l.strip()]
    exclusions_html = ''
    if _exc:
        _rows = "".join(f'<div style="padding:1px 0">{l}</div>' for l in _exc)
        exclusions_html = f'''
  <div style="margin-top:16px;font-size:11px">
    <div style="font-weight:bold;margin-bottom:4px">※ 御見積除外事項</div>
    <div style="border:1px solid #ccc;padding:6px 10px;line-height:1.5">{_rows}</div>
  </div>'''

    # 宛名（注文主＋御担当者）・受渡場所・見積有効期限
    addressee = " ".join(x for x in (q.customer_name, q.customer_contact) if x) or " "
    delivery_place = q.delivery_place or q.delivery_name or " "
    valid_until_disp = q.valid_until_text or (q.valid_until or " ")

    cover_html = f'''
<div style="page-break-after:always">
  <div style="text-align:right;font-size:12px">No. {q.quotation_no}</div>
  <div style="text-align:right;font-size:12px;margin-bottom:4px">日付 {q.issue_date or '    '}</div>
  <h1 style="text-align:center;font-size:24px;margin:6px 0 14px;letter-spacing:8px">御 見 積 書</h1>
  {stamp_box}
  <div style="font-size:18px;font-weight:bold;border-bottom:2px solid #000;padding-bottom:4px">{addressee} &nbsp; 殿</div>
  <div style="margin:8px 0 18px;font-size:12px">件名: {q.title or ' '}　／　納入先: {q.delivery_name or ' '}　／　担当: {q.sales_person_name or ' '}</div>
  <table style="width:100%;margin-bottom:18px"><tr>
    <td style="font-size:16px;font-weight:bold">合計金額　￥<span style="font-size:24px;border-bottom:3px double #000;padding:0 6px">{grand_total:,}-</span>　<span style="font-size:11px;color:#888">{tax_label}</span></td>
  </tr></table>
  <h3 style="font-size:14px;margin:10px 0 6px">■ 大分類別 内訳（総括）</h3>
  <table style="width:68%;border-collapse:collapse;font-size:13px">
    <tr style="background:#2c3e50;color:#fff">
      <th style="border:1px solid #ccc;padding:6px 12px;text-align:center;width:50px">No.</th>
      <th style="border:1px solid #ccc;padding:6px 12px;text-align:left">大分類</th>
      <th style="border:1px solid #ccc;padding:6px 12px;text-align:right;width:170px">金額</th>
    </tr>
    {section_rows}
    <tr style="font-weight:bold;background:#f5f5f5">
      <td colspan="2" style="border:1px solid #ccc;padding:6px 12px;text-align:right">小計金額</td>
      <td style="border:1px solid #ccc;padding:6px 12px;text-align:right">¥{_subtotal_all:,}</td></tr>
    {discount_row}
    {tax_row}
    <tr style="font-weight:bold;background:#fff9c4;font-size:15px">
      <td colspan="2" style="border:2px solid #000;padding:8px 12px;text-align:right">合計金額{tax_label}</td>
      <td style="border:2px solid #000;padding:8px 12px;text-align:right">¥{grand_total:,}</td></tr>
  </table>
  {tax_note}
  {exclusions_html}
  <div style="margin-top:14px;font-size:11px;color:#666">※ 内訳明細は次ページ以降をご参照ください。</div>
</div>
'''

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>{q.quotation_no} 御見積書</title>
<style>
  body {{ font-family: 'Hiragino Sans','Yu Gothic',sans-serif; margin:20px; font-size:12px; }}
  @media print {{ .no-print{{ display:none }} body{{margin:10mm}} }}
  .header-table td {{ padding: 4px 8px; }}
</style>
</head><body>
<div class="no-print" style="background:#e0f2fe;padding:10px;margin-bottom:15px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px">🖨️ PDF印刷</button>
  <span style="margin-left:15px;font-size:12px;color:#555">印刷ダイアログで"PDFに保存"を選択してください</span>
</div>

<!-- draft透かし(未承認の場合のみ) -->
{draft_watermark}

<!-- 頭紙: 大分類別 内訳サマリー -->
{cover_html}

<!-- 内訳明細ページ: ヘッダー -->
<div style="text-align:right;margin-bottom:8px">No. {q.quotation_no}</div>
<div style="text-align:right;margin-bottom:4px">日付 {q.issue_date or '    '}</div>

<h1 style="text-align:center;font-size:24px;margin:10px 0;letter-spacing:8px">御 見 積 書</h1>

<table style="width:100%;margin-bottom:15px" cellspacing="0">
  <tr>
    <td style="width:55%;vertical-align:bottom">
      <div style="font-size:18px;font-weight:bold;border-bottom:2px solid #000;padding-bottom:4px">
        {addressee} &nbsp; 殿
      </div>
      <div style="margin-top:6px;font-size:12px">納入先: {q.delivery_name or ' '}</div>
    </td>
    <td style="width:45%;vertical-align:top;padding-left:20px">
      <table cellspacing="0" style="font-size:11px">
        <tr><td colspan="2" style="font-size:18px;font-weight:bold">合計金額 ￥&nbsp;
          <span style="font-size:22px">{grand_total:,}</span>
        </td></tr>
        <tr><td style="color:#888">{tax_label}</td></tr>
        <tr><td colspan="2" style="padding-top:8px">
          <table style="font-size:11px;border-collapse:collapse;width:100%">
            <tr><td style="border:1px solid #ccc;padding:3px 6px;background:#f5f5f5">納入期限</td><td style="border:1px solid #ccc;padding:3px 8px">{q.delivery_terms or ' '}</td></tr>
            <tr><td style="border:1px solid #ccc;padding:3px 6px;background:#f5f5f5">受渡場所</td><td style="border:1px solid #ccc;padding:3px 8px">{delivery_place}</td></tr>
            <tr><td style="border:1px solid #ccc;padding:3px 6px;background:#f5f5f5">見積有効期限</td><td style="border:1px solid #ccc;padding:3px 8px">{valid_until_disp}</td></tr>
            <tr><td style="border:1px solid #ccc;padding:3px 6px;background:#f5f5f5">御支払条件</td><td style="border:1px solid #ccc;padding:3px 8px">{q.payment_terms or ' '}</td></tr>
          </table>
        </td></tr>
      </table>
    </td>
  </tr>
</table>

<table style="width:100%;border-collapse:collapse;margin-bottom:8px;font-size:12px">
  <tr style="border-bottom:1px solid #000">
    <td style="width:50%;padding:4px">件名: {q.title or ' '}</td>
    <td style="width:50%;text-align:right;padding:4px">
      担当: {q.sales_person_name or ' '}
    </td>
  </tr>
</table>

<!-- 金額サマリ(1枚目) -->
<table style="width:100%;border-collapse:collapse;font-size:12px;margin-bottom:20px">
<thead>
  <tr style="background:#2c3e50;color:#fff">
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:center;width:40px">番号</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:left">品名.仕様</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:left;width:200px">詳細</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:center;width:50px">数量</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:center;width:40px">単位</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:right;width:110px">単価</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:right;width:120px">金額</th>
  </tr>
</thead>
<tbody>
{items_html}
</tbody>
<tfoot>
  <tr style="font-weight:bold">
    <td colspan="6" style="text-align:right;border:1px solid #ccc;padding:5px 8px">小計金額</td>
    <td style="text-align:right;border:1px solid #ccc;padding:5px 8px">¥{int(q.subtotal or 0):,}</td>
  </tr>
  {labor_row_detail}
  {discount_row_detail}
  {tax_row_detail}
  <tr style="font-weight:bold;background:#fff9c4;font-size:14px">
    <td colspan="6" style="text-align:right;border:2px solid #000;padding:6px 8px">合計金額{tax_label}</td>
    <td style="text-align:right;border:2px solid #000;padding:6px 8px">¥{grand_total:,}</td>
  </tr>
</tfoot>
</table>
{tax_note}
{exclusions_html}

<!-- 会社情報フッター -->
<div style="margin-top:30px;border:2px solid #000;padding:10px;display:flex;align-items:center">
  <div style="font-size:22px;font-weight:bold;margin-right:20px">井上電設株式会社</div>
  <div style="font-size:11px;color:#333">
    〒460-0022 名古屋市中区金山四丁目3番17号<br>
    TEL (052) 322-5271 FAX (052) 332-5273<br>
    E-mail: tech@inoue-d.co.jp
  </div>
  <div style="margin-left:auto;font-size:11px">
    担当: {q.sales_person_name or '　　　'}<br>
    作成: {q.created_by_name or '　　　'}<br>
    検印: {q.approver_name or '　　　'}
  </div>
</div>
</body></html>"""


# =============================================
# 社内工数試算（社内用。顧客向け見積書には出さない金額の内訳）
# =============================================
# 工数マスタのカテゴリ → 原本（ケイテック様 社内シート）の区分へのまとめ方
LABOR_GROUPS = [
    ("運送交通費", ("運送",)),
    ("取付工事", ("工事作業", "重機", "宿泊")),
    ("試運転調整", ("試運転",)),
    ("その他", ("消耗品", "諸経費")),
]


def _labor_category_map(q: QuotationHeader, db: Session) -> dict:
    """労務明細ID → 工数マスタのカテゴリ"""
    ids = [l.labor_item_id for l in q.labor_details if l.labor_item_id]
    if not ids:
        return {}
    rows = db.query(EstimateLaborItem).filter(EstimateLaborItem.id.in_(ids)).all()
    return {str(r.id): r.category for r in rows}


def _build_labor_html(q: QuotationHeader, db: Session) -> str:
    """社内工数試算のHTML。原本の社内シート（運送交通費／取付工事／試運転調整）様式。"""
    cat_of = _labor_category_map(q, db)

    def _cat(l):
        return cat_of.get(str(l.labor_item_id), "") if l.labor_item_id else ""

    rows_html = ""
    grand = 0
    used = set()
    for group_name, cats in LABOR_GROUPS:
        items = [l for l in sorted(q.labor_details, key=lambda x: x.sort_order or 0)
                 if _cat(l) in cats]
        if not items:
            continue
        used.update(id(l) for l in items)
        sub = sum(int(l.amount or 0) for l in items)
        grand += sub
        rows_html += f'''
        <tr style="background:#e8eef5;font-weight:bold">
          <td colspan="6" style="border:1px solid #999;padding:5px 8px">○ {group_name}</td>
        </tr>'''
        for l in items:
            rows_html += f'''
        <tr>
          <td style="border:1px solid #ccc;padding:4px 8px">{l.item_name}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;font-size:11px">{l.crane_type or ''}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:right">{float(l.quantity or 0):g}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:center">{l.unit or ''}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:right">¥{int(l.unit_price or 0):,}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:right">¥{int(l.amount or 0):,}</td>
        </tr>'''
        rows_html += f'''
        <tr style="background:#f5f5f5;font-weight:bold">
          <td colspan="5" style="border:1px solid #ccc;padding:4px 8px;text-align:right">{group_name} 小計金額</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:right">¥{sub:,}</td>
        </tr>'''

    # どの区分にも入らなかった明細（工数マスタを使わず手入力した行）
    rest = [l for l in sorted(q.labor_details, key=lambda x: x.sort_order or 0) if id(l) not in used]
    if rest:
        sub = sum(int(l.amount or 0) for l in rest)
        grand += sub
        rows_html += '''
        <tr style="background:#e8eef5;font-weight:bold">
          <td colspan="6" style="border:1px solid #999;padding:5px 8px">○ 区分なし</td>
        </tr>'''
        for l in rest:
            rows_html += f'''
        <tr>
          <td style="border:1px solid #ccc;padding:4px 8px">{l.item_name}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;font-size:11px">{l.crane_type or ''}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:right">{float(l.quantity or 0):g}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:center">{l.unit or ''}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:right">¥{int(l.unit_price or 0):,}</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:right">¥{int(l.amount or 0):,}</td>
        </tr>'''
        rows_html += f'''
        <tr style="background:#f5f5f5;font-weight:bold">
          <td colspan="5" style="border:1px solid #ccc;padding:4px 8px;text-align:right">区分なし 小計金額</td>
          <td style="border:1px solid #ccc;padding:4px 8px;text-align:right">¥{sub:,}</td>
        </tr>'''

    if not rows_html:
        rows_html = '''
        <tr><td colspan="6" style="border:1px solid #ccc;padding:20px;text-align:center;color:#888">
          社内工数が登録されていません（見積の「社内工数」タブから入力してください）
        </td></tr>'''

    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>{q.quotation_no} 社内工数試算</title>
<style>
  body {{ font-family:'Hiragino Sans','Yu Gothic',sans-serif; margin:20px; font-size:12px; }}
  @media print {{ .no-print{{display:none}} body{{margin:10mm}} }}
</style>
</head><body>
<div class="no-print" style="background:#fff4e5;padding:10px;margin-bottom:15px;border-radius:6px">
  <button onclick="window.print()" style="background:#d97706;color:#fff;border:none;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px">🖨️ 印刷</button>
  <span style="margin-left:15px;font-size:12px;color:#555">印刷ダイアログで"PDFに保存"を選択してください</span>
</div>

<div style="border:2px solid #c0392b;color:#c0392b;font-weight:bold;padding:6px 10px;margin-bottom:12px;display:inline-block">
  社内資料（顧客提出不可）
</div>
<h1 style="font-size:20px;margin:6px 0 12px">社内工数試算</h1>
<table style="width:100%;font-size:12px;margin-bottom:12px">
  <tr>
    <td>見積No. <b>{q.quotation_no}</b></td>
    <td>件名: {q.title or ' '}</td>
    <td>注文主: {q.customer_name or ' '}</td>
    <td style="text-align:right">日付: {q.issue_date or ' '}</td>
  </tr>
</table>

<table style="width:100%;border-collapse:collapse;font-size:12px">
<thead>
  <tr style="background:#2c3e50;color:#fff">
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:left">作業項目</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:left;width:110px">種別・備考</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:right;width:60px">数量</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:center;width:50px">単位</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:right;width:100px">単価</th>
    <th style="border:1px solid #ccc;padding:5px 8px;text-align:right;width:120px">金額</th>
  </tr>
</thead>
<tbody>{rows_html}</tbody>
<tfoot>
  <tr style="font-weight:bold;background:#fff9c4;font-size:14px">
    <td colspan="5" style="border:2px solid #000;padding:6px 8px;text-align:right">合計金額（税抜）</td>
    <td style="border:2px solid #000;padding:6px 8px;text-align:right">¥{grand:,}</td>
  </tr>
</tfoot>
</table>

<div style="margin-top:14px;font-size:11px;color:#666">
  ※ この金額は社内の原価試算です。顧客向け見積書には内訳を印字していません。<br>
  ※ 人工単価・宿泊費・重機費は案件ごとに変動するため、見積の「社内工数」タブで都度調整してください。
</div>
<div style="margin-top:20px;font-size:11px">井上電設株式会社</div>
</body></html>"""


@router.get("/{quotation_id}/labor-sheet")
def labor_sheet(quotation_id: str, format: str = "html", db: Session = Depends(get_db)):
    """社内工数試算（社内用）。?format=pdf でPDFを返す（生成できない環境ではHTML）。"""
    q = db.query(QuotationHeader).options(
        joinedload(QuotationHeader.labor_details)
    ).filter(pk_or_code(QuotationHeader.id, QuotationHeader.quotation_no, quotation_id)).first()
    if not q:
        raise HTTPException(404)
    html = _build_labor_html(q, db)
    if format == "pdf":
        from app.pdf import html_to_pdf
        from urllib.parse import quote
        blob = html_to_pdf(html)
        if blob:
            # ファイル名に日本語を使う場合はRFC5987形式にする。
            # HTTPヘッダーはlatin-1しか扱えず、そのまま入れると500になる。
            fn = quote(f"{q.quotation_no}_工数試算.pdf")
            return StreamingResponse(
                io.BytesIO(blob), media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename*=UTF-8''{fn}"})
    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename={q.quotation_no}_labor.html"})


# =============================================
# 受注票発行
# =============================================

@router.post("/{quotation_id}/issue-order-ticket")
def issue_order_ticket(quotation_id: str, db: Session = Depends(get_db)):
    q = db.query(QuotationHeader).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)

    # 受注票の金額は税抜
    total = net_amount(q)

    # 工番/単番は案件子IDで登録された区分を引き継ぐ（2026-07-18〜。金額による自動判定は廃止）
    po = None
    if q.project_order_id:
        po = db.query(ProjectOrder).filter(ProjectOrder.id == q.project_order_id).first()
    ticket_type = po.ticket_type if po and po.ticket_type else None
    if ticket_type not in ("koban", "tanban"):
        raise HTTPException(
            400,
            "案件子IDに工番/単番が設定されていません。案件管理で区分を設定してから受注票を発行してください",
        )

    # 子IDに既存のアクティブな受注票があるか確認
    existing_tickets = []
    if q.project_order_id:
        existing_tickets = db.query(OrderTicket).filter(
            OrderTicket.project_order_id == q.project_order_id,
            OrderTicket.is_active == True
        ).all()

    # 既存票を非表示に
    for t in existing_tickets:
        t.is_active = False

    # 常に新規採番
    from sqlalchemy import text as sa_text
    db.execute(sa_text("SELECT pg_advisory_xact_lock(hashtext('order_ticket_no_lock'))"))
    year = datetime.now().year
    prefix = f"OT{year}-"
    last = db.query(OrderTicket).filter(OrderTicket.ticket_no.like(f"{prefix}%")).order_by(desc(OrderTicket.ticket_no)).first()
    seq = int(last.ticket_no.split("-")[-1]) + 1 if last else 1
    ticket_no = f"{prefix}{seq:04d}"
    ticket = OrderTicket(
        ticket_no=ticket_no, ticket_type=ticket_type,
        project_order_id=q.project_order_id, child_no=q.child_no,
        quotation_id=q.id, total_amount=total,
        customer_name=q.customer_name, delivery_name=q.delivery_name,
        sales_person_name=q.sales_person_name, order_date=date.today(),
        is_active=True,
    )
    db.add(ticket)

    # 見積ステータス: この見積を受注済に、同じ子IDの他見積は下書きに戻す
    q.status = "received"
    if q.project_order_id:
        db.query(QuotationHeader).filter(
            QuotationHeader.project_order_id == q.project_order_id,
            QuotationHeader.id != q.id,
        ).update({"status": "draft"}, synchronize_session=False)

    # 子IDにステータス・採用見積を反映
    if q.project_order_id:
        po = db.query(ProjectOrder).filter(ProjectOrder.id == q.project_order_id).first()
        if po:
            po.quotation_no = q.quotation_no
            po.quotation_total = net_amount(q)
            po.quotation_amount = net_amount(q)
            po.quotation_issue_date = q.issue_date
            po.status = "受注"
            db.flush()
            _sync_project_final_amount(po, db)

    db.commit()
    db.refresh(ticket)
    return {"ticket_no": ticket_no, "ticket_type": ticket_type, "id": str(ticket.id), "has_previous": len(existing_tickets) > 0}


@router.get("/order-ticket/{ticket_id}/pdf")
def order_ticket_pdf(ticket_id: str, with_quotation: int = 0, db: Session = Depends(get_db)):
    t = db.query(OrderTicket).options(
        joinedload(OrderTicket.quotation).joinedload(QuotationHeader.line_items),
        joinedload(OrderTicket.project_order),
    ).filter(_ot_filter(ticket_id)).first()
    if not t: raise HTTPException(404)

    q = t.quotation
    is_koban = t.ticket_type == "koban"
    title = "受 注 票【工番】" if is_koban else "受 注 票【単番】"

    # 受注時項目（注文書有無・納期・前受金）を帳票に反映（該当側を太字下線で強調）
    def _yn(v):
        if v is True: return "<b><u>有</u></b> ・ 無"
        if v is False: return "有 ・ <b><u>無</u></b>"
        return "有 ・ 無"
    order_sheet_disp = _yn(t.has_order_sheet)
    drawing_disp = _yn(t.has_drawing)
    contract_disp = _yn(t.has_contract)
    delivery_disp = t.delivery_date.strftime("%Y/%m/%d") if t.delivery_date else "　　　年　　月　　日"

    # 部品手配・在庫マイナス（未・済。該当側を太字下線で強調）
    def _ms(v):
        if v == "済": return "未 ・ <b><u>済</u></b>"
        if v == "未": return "<b><u>未</u></b> ・ 済"
        return "未 ・ 済"
    parts_html = (f'<div>部品入力: {_ms(t.parts_input_status)}</div>'
                  f'<div style="margin-top:3px">注文: {_ms(t.parts_order_status)}</div>'
                  f'<div style="margin-top:3px">在庫マイナス: {_ms(t.stock_minus_status)}</div>')
    _adv = int(t.advance_payment) if t.advance_payment is not None else None
    if _adv and _adv > 0:
        advance_disp = f"<b><u>有</u></b> ・ 無　¥{_adv:,}"
    elif t.advance_payment is not None:
        advance_disp = "有 ・ <b><u>無</u></b>"
    else:
        advance_disp = "有 ・ 無"

    # 前受金 最大3回（分割入金）
    _advs = t.advance_payments or []
    _adv_rows = ""
    for i in range(3):
        a = _advs[i] if i < len(_advs) and isinstance(_advs[i], dict) else {}
        _d = a.get("date") or "　　月　　日"
        _amt = f"¥{int(a.get('amount')):,}" if a.get("amount") else "¥"
        _paid = "入金済" if a.get("amount") else "入金"
        _adv_rows += f'<div>{i+1}.（{_d}）税込/税抜 {_amt}　{_paid}</div>'
    _adv_yn = "<b><u>有</u></b> ・ 無" if _advs else "有 ・ <b><u>無</u></b>"
    advance_block = (f'<div style="border:1px solid #999;padding:8px;margin-top:10px;font-size:10px">'
                     f'<b>前受金</b>: {_adv_yn}<br>{_adv_rows}</div>') if is_koban else ''

    # 出荷方法（選択を■で強調）
    _ship = t.shipping_method or ""
    def _chk(name): return f'<b>■{name}</b>' if _ship == name else f'□{name}'
    ship_html = f'出荷方法: {_chk("トラック出荷")} {_chk("宅配出荷")} {_chk("井上納品")} {_chk("引取")}'

    # 子ID（案件）から出荷予定日・顧客納期・売上計上日を取得
    _po = t.project_order
    exp_ship_disp = _po.expected_shipment_date.strftime("%Y/%m/%d") if _po and _po.expected_shipment_date else "－"
    cust_due_disp = _po.customer_delivery_date.strftime("%Y/%m/%d") if _po and _po.customer_delivery_date else "－"
    sales_date_disp = _po.sales_date.strftime("%Y/%m/%d") if _po and _po.sales_date else "－"

    draft_watermark = ""

    items_html = ""
    if q:
        # 大分類（section）ごとに番号付け。各明細に大分類ID（番号＋名称）を表示
        _sections = {}
        for item in sorted(q.line_items, key=lambda x: x.line_no):
            _sections.setdefault(item.section or "", []).append(item)
        for sec_no, (sec, sitems) in enumerate(_sections.items(), 1):
            for item in sitems:
                items_html += f"""<tr>
                <td style="text-align:center;border:1px solid #999;padding:3px 6px;white-space:nowrap">{sec_no}<div style="font-size:8px;color:#666;line-height:1.1">{sec or ''}</div></td>
                <td style="border:1px solid #999;padding:3px 6px">{item.item_name}</td>
                <td style="border:1px solid #999;padding:3px 6px;font-size:10px">{item.spec_detail or ''}</td>
                <td style="text-align:center;border:1px solid #999;padding:3px 6px">{int(item.quantity or 1)}</td>
                <td style="text-align:center;border:1px solid #999;padding:3px 6px">{item.unit}</td>
                <td style="text-align:right;border:1px solid #999;padding:3px 6px">¥{int(item.unit_price or 0):,}</td>
                <td style="text-align:right;border:1px solid #999;padding:3px 6px">¥{int(item.amount or 0):,}</td>
            </tr>"""

    html = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<title>{t.ticket_no} {title}</title>
<style>
  body{{font-family:'Hiragino Sans','Yu Gothic',sans-serif;font-size:11px;margin:15mm}}
  @media print{{.no-print{{display:none}}}}
  table{{border-collapse:collapse;width:100%}}
  th{{background:#eee;border:1px solid #999;padding:4px 6px}}
</style></head><body>
<div class="no-print" style="background:#e0f2fe;padding:8px;margin-bottom:10px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer">🖨️ PDF印刷</button>
</div>

<div style="text-align:right;margin-bottom:4px">
  <span style="font-size:11px;color:#555;vertical-align:middle">受注番号(COID)</span>
  <span style="font-size:20px;font-weight:bold;border:2px solid #000;padding:2px 12px;margin-left:6px;letter-spacing:1px">{t.child_no or t.ticket_no}</span>
</div>
<h2 style="text-align:center;font-size:18px;border-bottom:2px solid #000;padding-bottom:6px">{title}</h2>

<table style="margin-bottom:12px;font-size:11px" cellspacing="0">
  <tr>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px;width:100px">受注日</td>
    <td style="border:1px solid #999;padding:4px 8px">{t.order_date or ' '}</td>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px;width:100px">見積書No.</td>
    <td style="border:1px solid #999;padding:4px 8px">{q.quotation_no if q else ' '}</td>
  </tr>
  <tr>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">納入先</td>
    <td style="border:1px solid #999;padding:4px 8px">{t.delivery_name or ' '}</td>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">注文主</td>
    <td style="border:1px solid #999;padding:4px 8px">{t.customer_name or ' '}</td>
  </tr>
  <tr>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">担当者</td>
    <td style="border:1px solid #999;padding:4px 8px">{t.sales_person_name or ' '}</td>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">区分</td>
    <td style="border:1px solid #999;padding:4px 8px">{'工番(税抜300万円以上)' if is_koban else '単番(税抜300万円未満)'}</td>
  </tr>
  <tr>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">顧客納期</td>
    <td style="border:1px solid #999;padding:4px 8px">{cust_due_disp}</td>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">出荷予定日</td>
    <td style="border:1px solid #999;padding:4px 8px">{exp_ship_disp}</td>
  </tr>
  <tr>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px">売上計上日</td>
    <td style="border:1px solid #999;padding:4px 8px">{sales_date_disp}</td>
    <td style="background:#eee;border:1px solid #999;padding:4px 8px"></td>
    <td style="border:1px solid #999;padding:4px 8px"></td>
  </tr>
</table>

<table style="margin-bottom:12px;font-size:11px">
  <thead><tr>
    <th style="width:64px">大分類</th>
    <th style="width:200px">品名.仕様</th>
    <th>詳細</th>
    <th style="width:50px">数量</th>
    <th style="width:40px">単位</th>
    <th style="width:100px">単価</th>
    <th style="width:110px">金額</th>
  </tr></thead>
  <tbody>{items_html}</tbody>
  <tfoot>
    <tr style="font-weight:bold;background:#fff9c4">
      <td colspan="6" style="text-align:right;border:1px solid #999;padding:4px 8px">合計金額</td>
      <td style="text-align:right;border:1px solid #999;padding:4px 8px">¥{int(t.total_amount or 0):,}</td>
    </tr>
  </tfoot>
</table>

{advance_block}

<div style="margin-top:20px;border:1px solid #999;padding:8px;font-size:10px">
  <table style="width:100%"><tr>
    <td style="vertical-align:top">
      <div>{ship_html}</div>
      <div style="margin-top:6px">納期: {delivery_disp}</div>
      <div style="margin-top:6px">図面: {drawing_disp}　注文書: {order_sheet_disp}　契約書: {contract_disp}</div>
    </td>
    <td style="width:180px;vertical-align:top;border-left:1px solid #999;padding-left:8px">
      <div style="font-weight:bold;text-align:center;background:#eee;padding:2px;margin-bottom:4px">部品手配・在庫マイナス</div>
      {parts_html}
    </td>
  </tr></table>
</div>

<div style="margin-top:12px;display:flex;align-items:stretch">
  <table style="font-size:9px;border-collapse:collapse;flex:1;table-layout:fixed">
    <tr>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">社長</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">柴田</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">後藤</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">江里口</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">井上(雄)</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">加藤(剛)</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">国立</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">川口</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">今井</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">大西</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">伏屋</th>
      <th style="border:1px solid #999;padding:3px 2px;text-align:center">三輪</th>
    </tr>
    <tr>
      <td style="border:1px solid #999;height:28px"></td><td style="border:1px solid #999"></td>
      <td style="border:1px solid #999"></td><td style="border:1px solid #999"></td>
      <td style="border:1px solid #999"></td><td style="border:1px solid #999"></td>
      <td style="border:1px solid #999"></td><td style="border:1px solid #999"></td>
      <td style="border:1px solid #999"></td><td style="border:1px solid #999"></td>
      <td style="border:1px solid #999"></td><td style="border:1px solid #999"></td>
    </tr>
    <tr>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
      <td style="border:1px solid #999;font-size:8px;text-align:center;padding:2px">月　日</td>
    </tr>
  </table>
  <div style="border:1px solid #999;padding:4px 6px;writing-mode:vertical-rl;font-size:9px;display:flex;align-items:center;justify-content:center;min-width:20px">検印欄</div>
</div>

<div style="margin-top:15px;border:2px solid #000;padding:8px;display:flex;align-items:center">
  <div style="font-size:16px;font-weight:bold">井上電設株式会社</div>
  <div style="margin-left:15px;font-size:10px">〒460-0022 名古屋市中区金山4丁目3-17 TEL(052)322-5271 FAX(052)332-5273</div>
</div>
</body></html>"""

    # 見積書も同時印刷（会議2026-07-17: 二度手間を省く）。?with_quotation=1 で受注票の後ろに見積書を連結
    if with_quotation and q:
        q_html = _build_quotation_html(q, is_draft=((q.approval_status or 'none') != 'approved'))
        # 見積書HTMLのbody部分を抜き出して改ページ付きで連結
        _qs = q_html.find("<body>")
        _qe = q_html.rfind("</body>")
        if _qs != -1 and _qe != -1:
            q_body = q_html[_qs + len("<body>"):_qe]
            html = html.replace("</body></html>",
                                f'<div style="page-break-before:always"></div>{q_body}</body></html>')

    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename={t.ticket_no}.html"}
    )


# =============================================
# 受注票 関連書類（注文書・契約書等のPDFをDBに保管）
# =============================================
MAX_TICKET_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@router.get("/order-ticket/{ticket_id}/files")
def list_order_ticket_files(ticket_id: str, db: Session = Depends(get_db)):
    t = db.query(OrderTicket).filter(_ot_filter(ticket_id)).first()
    if not t: raise HTTPException(404, "受注票が見つかりません")
    files = db.query(OrderTicketFile).filter(
        OrderTicketFile.order_ticket_id == t.id
    ).order_by(OrderTicketFile.uploaded_at).all()
    return [{
        "id": str(f.id), "file_kind": f.file_kind, "filename": f.filename,
        "content_type": f.content_type, "file_size": f.file_size,
        "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
    } for f in files]

@router.post("/order-ticket/{ticket_id}/files", status_code=201)
def upload_order_ticket_file(ticket_id: str, data: dict, db: Session = Depends(get_db)):
    """関連書類のアップロード。{file_kind, filename, content_base64} のJSONで受ける。
    RenderのディスクはデプロイでリセットされるためDBに保管する（1件10MBまで）。"""
    import base64
    t = db.query(OrderTicket).filter(_ot_filter(ticket_id)).first()
    if not t: raise HTTPException(404, "受注票が見つかりません")
    filename = (data or {}).get("filename")
    b64 = (data or {}).get("content_base64")
    if not filename or not b64:
        raise HTTPException(400, "filename と content_base64 は必須です")
    # デコード前に長さで弾く（デコード後に検査すると、その一瞬だけ上限を超えた
    # データがメモリに載る。base64は元データの約4/3の長さになる）
    if len(b64) > MAX_TICKET_FILE_SIZE // 3 * 4 + 1024:
        raise HTTPException(413, "ファイルサイズは10MBまでです")
    try:
        blob = base64.b64decode(b64)
    except Exception:
        raise HTTPException(400, "content_base64 をデコードできません")
    if len(blob) > MAX_TICKET_FILE_SIZE:
        raise HTTPException(413, "ファイルサイズは10MBまでです")
    f = OrderTicketFile(
        order_ticket_id=t.id,
        file_kind=nfkc((data or {}).get("file_kind")) or "その他",
        filename=nfkc(filename),
        content_type=(data or {}).get("content_type") or "application/pdf",
        file_size=len(blob), data=blob,
    )
    db.add(f); db.commit(); db.refresh(f)
    return {"id": str(f.id), "filename": f.filename, "file_size": f.file_size}

@router.get("/order-ticket-file/{file_id}")
def download_order_ticket_file(file_id: str, db: Session = Depends(get_db)):
    f = db.query(OrderTicketFile).filter(OrderTicketFile.id == file_id).first()
    if not f: raise HTTPException(404, "ファイルが見つかりません")
    from urllib.parse import quote
    return StreamingResponse(
        io.BytesIO(f.data), media_type=f.content_type or "application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(f.filename)}"}
    )

@router.delete("/order-ticket-file/{file_id}", status_code=204)
def delete_order_ticket_file(file_id: str, db: Session = Depends(get_db)):
    f = db.query(OrderTicketFile).filter(OrderTicketFile.id == file_id).first()
    if not f: raise HTTPException(404, "ファイルが見つかりません")
    db.delete(f); db.commit()


# =============================================
# 指示書PDF出力
# =============================================

@router.get("/{quotation_id}/fan-instruction-pdf")
def fan_instruction_pdf(quotation_id: str, db: Session = Depends(get_db)):
    """ファン作業指示書PDF"""
    q = db.query(QuotationHeader).options(
        joinedload(QuotationHeader.line_items)
    ).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)

    # 見積明細からBFR/ファン情報を取得
    bfr_item = next((i for i in q.line_items if i.product_type == 'BFR' and 'バグフィルター' in (i.item_name or '')), None)
    fan_item = next((i for i in q.line_items if 'ターボファン' in (i.item_name or '') or 'ファン' in (i.item_name or '')), None)

    model = bfr_item.spec_json.get('model', '') if bfr_item and bfr_item.spec_json else ''
    fan_model = fan_item.spec_json.get('fan_model', '') if fan_item and fan_item.spec_json else ''
    fan_kw = ''
    if fan_item and fan_item.item_name:
        import re
        kw_match = re.search(r'(\d+\.?\d*)\s*kw', fan_item.item_name, re.IGNORECASE)
        if kw_match:
            fan_kw = kw_match.group(1)

    html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>ファン作業指示書</title>
<style>
  body {{ font-family: 'Hiragino Sans','Yu Gothic',sans-serif; font-size:11px; margin:15mm; }}
  @media print {{ .no-print {{ display:none }} }}
  table {{ border-collapse:collapse; width:100%; }}
  th, td {{ border:1px solid #999; padding:4px 6px; }}
  th {{ background:#f0f0f0; font-weight:bold; }}
  .title {{ font-size:20px; font-weight:bold; text-align:center; letter-spacing:4px; margin:10px 0; }}
  .header-right {{ position:absolute; top:15mm; right:15mm; text-align:center; }}
</style></head><body>

<div class="no-print" style="background:#e0f2fe;padding:8px;margin-bottom:10px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer">🖨️ PDF印刷</button>
</div>

<div style="position:relative">
  <div style="float:right;text-align:right;font-size:10px;margin-bottom:5px">
    発行日: {'      '}<br>
    <table style="font-size:10px;margin-top:4px">
      <tr><td style="background:#f0f0f0">営業担当</td><td style="min-width:80px">{q.sales_person_name or ' '}</td></tr>
      <tr><td style="background:#f0f0f0">作成</td><td></td></tr>
    </table>
  </div>
  <div class="title">ファン 作 業 指 示 書</div>
  <div style="clear:both"></div>
</div>

<table style="margin-bottom:8px">
  <tr>
    <td style="background:#f0f0f0;width:80px">型式</td>
    <td style="background:#ffeb3b;font-weight:bold;width:200px">{model}</td>
    <td style="background:#f0f0f0;width:80px">製造番号</td>
    <td style="width:200px">  F001〜 ユニークな番号</td>
  </tr>
  <tr>
    <td style="background:#f0f0f0">注文主</td>
    <td><strong>{q.customer_name or ' '}</strong> 殿</td>
    <td style="background:#f0f0f0">受注番号</td>
    <td><strong>{q.child_no or q.quotation_no}</strong></td>
  </tr>
  <tr>
    <td style="background:#f0f0f0">納入先</td>
    <td>{q.delivery_name or ' '} 殿</td>
    <td style="background:#f0f0f0">用途.仕様</td>
    <td>{model}</td>
  </tr>
  <tr>
    <td style="background:#f0f0f0">出荷日</td>
    <td>   年  月  日</td>
    <td style="background:#f0f0f0">出荷方法</td>
    <td>□トラック出荷 □宅配出荷 □井上納品 □引取</td>
  </tr>
</table>

<table style="margin-bottom:8px">
  <tr>
    <th rowspan="2" style="width:60px">モータ</th>
    <td style="width:50px">{fan_kw}</td><td style="width:20px">kw</td>
    <td style="width:20px">P</td><td style="width:30px"> </td>
    <td style="width:20px">Hz</td><td style="width:30px"> </td>
    <td style="width:20px">V</td><td style="width:40px"> </td>
    <td style="width:40px">屋内/屋外</td>
    <td style="width:40px">フランジ</td>
    <td style="width:40px"> </td>
  </tr>
  <tr><td colspan="10">備考: IE3</td></tr>
</table>

<table style="margin-bottom:8px">
  <tr>
    <th style="width:80px">軸受</th>
    <td>羽根側</td><td style="min-width:150px"> </td>
    <td>プーリー側</td><td style="min-width:150px"> </td>
  </tr>
  <tr>
    <th>モータ側プーリ</th>
    <td colspan="2"> </td>
    <td style="color:red">Vベルト</td><td>  本</td>
  </tr>
  <tr>
    <th>ファン側プーリ</th>
    <td colspan="2"> </td>
    <td style="color:red">回転数</td><td>  rpm</td>
  </tr>
</table>

<table style="margin-bottom:8px">
  <tr><th style="width:80px">カバー</th><td> </td><th>吸口テーパ</th><td>φ  ×t</td></tr>
  <tr><th>点検口</th><td> </td><th>フランジ</th><td>Fφ  ×t</td></tr>
  <tr><th>架台</th><td> </td><th>出口角丸</th><td>φ  H ×t</td></tr>
  <tr><th>塗装色</th><td> </td><th>フランジ</th><td>Fφ  ×t</td></tr>
</table>

<table style="margin-bottom:8px">
  <tr><th style="width:80px">備考</th><td style="height:60px"></td><th style="width:40px">図面情報</th><td style="width:120px"></td></tr>
</table>

<!-- 出荷時チェックリスト -->
<table style="margin-bottom:8px;font-size:10px">
  <tr>
    <td colspan="8" style="background:#f0f0f0;font-weight:bold">出荷時チェックリスト</td>
  </tr>
  <tr>
    <th>検査者</th><td style="min-width:80px"> </td>
    <th>日付</th><td> </td>
    <th>判定</th><td> </td>
    <td colspan="2"></td>
  </tr>
  <tr>
    <th>電流値</th><td> </td>
    <th>外観</th><td> </td>
    <th>回転方向</th><td> </td>
    <th>異音</th><td> </td>
  </tr>
  <tr>
    <th>測定点</th><td>軸受A</td><td>軸受B</td><td>X方向</td><td>Y方向</td><td>Z方向</td><td>予備点</td><td>予備点</td>
  </tr>
  <tr><th>振動値</th><td> </td><td> </td><td> </td><td> </td><td> </td><td> </td><td> </td></tr>
</table>

<table style="font-size:10px">
  <tr>
    <td>屋外＝全閉外扇屋外型</td>
    <th colspan="2">想定性能</th>
    <th colspan="2">ベルトたわみ量</th>
    <td>mm</td>
  </tr>
  <tr><td>屋内＝全閉外扇屋内型</td><th>圧力</th><td> mmaq</td><th>たわみ荷重最小値</th><td colspan="2"> N</td></tr>
  <tr><td>グリス＝グリス給油</td><th>風量</th><td> m³/min</td><th>たわみ荷重最大値(新規)</th><td colspan="2"> N</td></tr>
  <tr><td>高効率＝高効率モータ</td><th>電流</th><td> A</td><th>たわみ荷重最大値(張りなおし)</th><td colspan="2"> N</td></tr>
</table>

<div style="margin-top:15px;border:2px solid #000;padding:8px;display:flex;align-items:center">
  <div style="font-size:16px;font-weight:bold;margin-right:15px">井上電設株式会社</div>
  <div style="font-size:10px">〒460-0022 名古屋市中区金山四丁目3番17号 TEL(052)322-5271 FAX(052)332-5273</div>
</div>
</body></html>"""

    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename=fan_instruction_{q.quotation_no}.html"}
    )


@router.get("/{quotation_id}/fan-inspection-pdf")
def fan_inspection_pdf(quotation_id: str, db: Session = Depends(get_db)):
    """ファン検査記録書PDF"""
    q = db.query(QuotationHeader).options(
        joinedload(QuotationHeader.line_items)
    ).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)

    bfr_item = next((i for i in q.line_items if i.product_type == 'BFR' and 'バグフィルター' in (i.item_name or '')), None)
    model = bfr_item.spec_json.get('model', '') if bfr_item and bfr_item.spec_json else ''

    inspection_items = [
        ('切削', '羽根車ボス外形寸法'), ('切削', '羽根車ボス穴寸法'),
        ('切削', 'シャフト羽根車側寸法'), ('切削', 'シャフトプーリ側寸法'),
        ('切削', 'シャフト長さ'), ('切削', 'モータプーリ穴寸法'), ('切削', 'ファンプーリ穴寸法'),
        ('製缶', '溶接及び歪外観'),
        ('塗装', '塗装及びコーキング外観'),
        ('組立', '羽根車穴仕上げ'), ('組立', '羽根車バランス'), ('組立', '軸受グリス封入'),
        ('組立', '軸受ノックピン'), ('組立', 'プーリ芯出し'), ('組立', 'ベルト張力.振動.電流'),
        ('組立', 'カバーその他付属品取付'), ('組立', 'PLシール貼付'),
    ]

    # B007修正: rowspanはカテゴリごとの項目数に設定（"X"リテラルだとラベルが1行しか結合されない）
    from collections import Counter
    cat_counts = Counter(cat for cat, _ in inspection_items)

    rows = ''
    prev_category = ''
    for cat, item in inspection_items:
        cat_cell = f'<td rowspan="{cat_counts[cat]}" style="background:#f0f0f0;font-weight:bold;text-align:center;vertical-align:middle">{cat}</td>' if cat != prev_category else ''
        rows += f"""<tr>
            {cat_cell}
            <td style="border:1px solid #ccc;padding:3px 6px;background:#fff9c4;font-weight:bold">{item}</td>
            <td style="border:1px solid #ccc;padding:3px 6px;width:60px"></td>
            <td style="border:1px solid #ccc;padding:3px 6px;width:60px"></td>
            <td style="border:1px solid #ccc;padding:3px 6px;width:60px"></td>
            <td style="border:1px solid #ccc;padding:3px 6px;width:60px"></td>
            <td style="border:1px solid #ccc;padding:3px 6px;width:60px"></td>
            <td style="border:1px solid #ccc;padding:3px 6px;width:40px"></td>
        </tr>"""
        prev_category = cat

    html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>ファン検査記録書</title>
<style>
  body {{ font-family: 'Hiragino Sans','Yu Gothic',sans-serif; font-size:11px; margin:15mm; }}
  @media print {{ .no-print {{ display:none }} }}
  table {{ border-collapse:collapse; width:100%; }}
</style></head><body>
<div class="no-print" style="background:#e0f2fe;padding:8px;margin-bottom:10px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer">🖨️ PDF印刷</button>
</div>

<div style="float:right;font-size:10px">
  発行日:      
  <table style="margin-top:4px"><tr><td style="background:#f0f0f0">営業担当</td><td style="min-width:60px">{q.sales_person_name or ' '}</td></tr>
  <tr><td style="background:#f0f0f0">作成</td><td></td></tr></table>
</div>
<h2 style="font-size:18px;font-weight:bold;letter-spacing:4px">ファン 検 査 記 録 書</h2>
<div style="clear:both"></div>

<table style="margin-bottom:8px">
  <tr>
    <td style="background:#f0f0f0;width:60px">型式</td>
    <td style="background:#ffeb3b;font-weight:bold;width:180px">{model}</td>
    <td style="background:#f0f0f0;width:60px">製造番号</td><td></td>
  </tr>
  <tr>
    <td style="background:#f0f0f0">注文主</td>
    <td><strong>{q.customer_name or ' '}</strong> 殿</td>
    <td style="background:#f0f0f0">受注番号</td>
    <td><strong>{q.child_no or q.quotation_no}</strong></td>
  </tr>
  <tr>
    <td style="background:#f0f0f0">納入先</td>
    <td>{q.delivery_name or ' '} 殿</td>
    <td style="background:#f0f0f0">用途.仕様</td>
    <td>{model}</td>
  </tr>
  <tr>
    <td style="background:#f0f0f0">出荷日</td>
    <td>  年  月  日</td>
    <td style="background:#f0f0f0">出荷方法</td>
    <td>□トラック出荷 □宅配出荷 □井上納品 □引取</td>
  </tr>
</table>

<table>
  <thead>
    <tr style="background:#2c3e50;color:#fff">
      <th style="padding:5px;width:60px">検査工程</th>
      <th style="padding:5px">検査項目</th>
      <th style="padding:5px;width:60px">加工納期</th>
      <th style="padding:5px;width:60px">加工者</th>
      <th style="padding:5px;width:60px">加工日</th>
      <th style="padding:5px;width:60px">検査者</th>
      <th style="padding:5px;width:60px">検査日</th>
      <th style="padding:5px;width:40px">良/不良</th>
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>

<div style="margin-top:15px;border:2px solid #000;padding:8px;display:flex;align-items:center">
  <div style="font-size:16px;font-weight:bold;margin-right:15px">井上電設株式会社</div>
  <div style="font-size:10px">〒460-0022 名古屋市中区金山四丁目3番17号 TEL(052)322-5271 FAX(052)332-5273</div>
</div>
</body></html>"""

    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename=fan_inspection_{q.quotation_no}.html"}
    )


@router.get("/{quotation_id}/control-panel-pdf")
def control_panel_pdf(quotation_id: str, db: Session = Depends(get_db)):
    """制御盤作業指示書PDF"""
    q = db.query(QuotationHeader).options(
        joinedload(QuotationHeader.line_items)
    ).filter(QuotationHeader.id == quotation_id).first()
    if not q: raise HTTPException(404)

    # 制御盤情報を見積明細から取得
    fan_item = next((i for i in q.line_items if 'ファン' in (i.item_name or '') or 'BFR' in (i.item_name or '')), None)
    kw = ''
    if fan_item and fan_item.spec_json:
        kw = fan_item.spec_json.get('kw', '')

    motors = []
    for i in q.line_items:
        if i.spec_json and 'kw' in i.spec_json:
            motors.append({'name': i.item_name or '', 'kw': i.spec_json.get('kw', ''), 'count': int(i.quantity or 1)})

    motor_rows = ''
    for idx, m in enumerate(motors[:15], 1):
        motor_rows += f"<tr><td style='border:1px solid #ccc;padding:3px;text-align:center'>{idx}</td><td style='border:1px solid #ccc;padding:3px'>{m['name']}</td><td style='border:1px solid #ccc;padding:3px;text-align:center'>{m['kw']}</td><td style='border:1px solid #ccc;padding:3px;text-align:center'>{m['count']}</td><td style='border:1px solid #ccc;padding:3px'></td></tr>"
    for idx in range(len(motors) + 1, 16):
        motor_rows += f"<tr><td style='border:1px solid #ccc;padding:3px;text-align:center;color:#ccc'>{idx}</td><td style='border:1px solid #ccc'></td><td style='border:1px solid #ccc'></td><td style='border:1px solid #ccc'></td><td style='border:1px solid #ccc'></td></tr>"

    html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>制御盤作業指示書</title>
<style>
  body {{ font-family: 'Hiragino Sans','Yu Gothic',sans-serif; font-size:11px; margin:15mm; }}
  @media print {{ .no-print {{ display:none }} }}
  table {{ border-collapse:collapse; }}
  th {{ background:#f0f0f0; }}
</style></head><body>
<div class="no-print" style="background:#e0f2fe;padding:8px;margin-bottom:10px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer">🖨️ PDF印刷</button>
</div>

<div style="float:right;text-align:right">
  受No. <span style="background:#ff4444;color:#fff;padding:2px 8px;font-weight:bold">{q.child_no or q.quotation_no}</span>
</div>
<div style="clear:both;margin-bottom:8px"></div>

<table style="width:100%;margin-bottom:8px">
  <tr>
    <td style="border:1px solid #ccc;padding:4px;width:60px;background:#f0f0f0">納入先</td>
    <td style="border:1px solid #ccc;padding:4px" colspan="3">{q.delivery_name or ' '}</td>
    <td style="border:1px solid #ccc;padding:4px;width:40px;background:#f0f0f0">工場</td>
    <td style="border:1px solid #ccc;padding:4px;width:60px;background:#f0f0f0">注文主</td>
    <td style="border:1px solid #ccc;padding:4px">{q.customer_name or ' '}</td>
  </tr>
</table>

<table style="width:100%;margin-bottom:8px">
  <tr>
    <td style="border:1px solid #ccc;padding:4px;width:40px;background:#f0f0f0">名称</td>
    <td style="border:1px solid #ccc;padding:4px;width:200px"></td>
    <td style="border:1px solid #ccc;padding:4px;width:40px;background:#f0f0f0">形式</td>
    <td style="border:1px solid #ccc;padding:4px"></td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0">概要</td>
    <td style="border:1px solid #ccc;padding:4px" colspan="2"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0">電子図番</td>
    <td style="border:1px solid #ccc;padding:4px"></td>
  </tr>
</table>

<table style="width:100%;margin-bottom:8px">
  <tr>
    <th rowspan="5" style="border:1px solid #ccc;padding:4px;width:50px;vertical-align:middle">盤仕様</th>
    <td style="border:1px solid #ccc;padding:4px;width:80px;background:#f0f0f0">仕様</td>
    <td style="border:1px solid #ccc;padding:4px;width:80px"></td>
    <td style="border:1px solid #ccc;padding:4px;width:60px;background:#f0f0f0">指定色</td>
    <td style="border:1px solid #ccc;padding:4px;width:80px"></td>
    <td style="border:1px solid #ccc;padding:4px;width:80px;background:#f0f0f0">架台.タイプ</td>
    <td style="border:1px solid #ccc;padding:4px"></td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0">周波数(Hz)</td>
    <td style="border:1px solid #ccc;padding:4px"></td>
    <td colspan="2"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0">サイズ:W×L×H</td>
    <td style="border:1px solid #ccc;padding:4px"></td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0">動力(V)</td>
    <td style="border:1px solid #ccc;padding:4px" colspan="5">□AC200V □AC380V □AC400V □AC415V □AC440V</td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0">操作回路(V)</td>
    <td style="border:1px solid #ccc;padding:4px" colspan="5">□AC100V □AC200V □DC24V</td>
  </tr>
  <tr>
    <th rowspan="3" style="border:1px solid #ccc;padding:4px;background:#f0f0f0;vertical-align:middle">その他</th>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0">パトライト</td><td style="border:1px solid #ccc;padding:4px"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0">操作SW</td><td style="border:1px solid #ccc;padding:4px"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0">火花探知器</td><td style="border:1px solid #ccc;padding:4px"></td>
  </tr>
</table>

<table style="width:100%;margin-bottom:8px;font-size:10px">
  <thead>
    <tr style="background:#f0f0f0">
      <th style="border:1px solid #ccc;padding:3px;width:30px"></th>
      <th style="border:1px solid #ccc;padding:3px">名称</th>
      <th style="border:1px solid #ccc;padding:3px;width:70px">容量(kw)</th>
      <th style="border:1px solid #ccc;padding:3px;width:50px">台数</th>
      <th style="border:1px solid #ccc;padding:3px">備考</th>
    </tr>
  </thead>
  <tbody>{motor_rows}</tbody>
</table>

<table style="width:100%;margin-bottom:8px;font-size:10px">
  <tr>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0;width:40px">電子見積</td>
    <td style="border:1px solid #ccc;padding:4px;width:80px"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0;width:40px">電子仕入</td>
    <td style="border:1px solid #ccc;padding:4px;width:80px"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0;width:50px">見積金額</td>
    <td style="border:1px solid #ccc;padding:4px;width:100px"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0;width:50px">受注金額</td>
    <td style="border:1px solid #ccc;padding:4px"></td>
  </tr>
</table>

<table style="width:100%;font-size:10px">
  <tr>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0;width:30px">担当</td>
    <td style="border:1px solid #ccc;padding:4px;width:80px">{q.sales_person_name or ' '}</td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0;width:30px">確認</td>
    <td style="border:1px solid #ccc;padding:4px;width:80px"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0;width:30px">打合</td>
    <td style="border:1px solid #ccc;padding:4px;width:80px"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0;width:30px">立会</td>
    <td style="border:1px solid #ccc;padding:4px;width:80px"></td>
    <td style="border:1px solid #ccc;padding:4px;background:#f0f0f0;width:30px">出荷</td>
    <td style="border:1px solid #ccc;padding:4px"></td>
  </tr>
</table>

<div style="margin-top:15px;border:2px solid #000;padding:8px;display:flex;align-items:center">
  <div style="font-size:20px;font-weight:bold;margin-right:10px">INOUE 井上電設株式会社</div>
  <div style="font-size:10px">〒460-0022 名古屋市中区金山4丁目3-17 TEL(052)322-5271 FAX(052)332-5273</div>
</div>
</body></html>"""

    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename=control_panel_{q.quotation_no}.html"}
    )


# =============================================
# 手配書PDF(クレーン.作業車依頼書)
# =============================================
@router.get("/project-order/{order_id}/crane-pdf")
def crane_pdf(order_id: str, db: Session = Depends(get_db)):
    """クレーン.作業車等依頼書PDF"""
    from app.db.models import ProjectOrder
    po = db.query(ProjectOrder).filter(
        pk_or_code(ProjectOrder.id, ProjectOrder.child_no, order_id)
    ).first()
    if not po: raise HTTPException(404)

    crane_one = (
        '<table style="margin-bottom:8px">'
        '<tr><td style="background:#f0f0f0;width:60px">機械名</td>'
        '<td style="min-width:150px"> </td>'
        '<td style="background:#f0f0f0;width:60px">使用期間</td>'
        '<td>  月  日( )  時 ~  月  日( )  時</td></tr>'
        '<tr><td style="background:#f0f0f0"> </td><td> </td>'
        '<td style="background:#f0f0f0"> </td><td> </td></tr>'
        '<tr><td style="background:#f0f0f0">納品方法</td><td> </td>'
        '<td style="background:#f0f0f0">備考</td><td rowspan="2"> </td></tr>'
        '<tr><td style="background:#f0f0f0">返却方法</td><td> </td><td></td></tr>'
        '</table>'
    )
    crane_tables = crane_one * 3

    html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>クレーン.作業車等依頼書</title>
<style>
  body {{ font-family: 'Hiragino Sans','Yu Gothic',sans-serif; font-size:11px; margin:15mm; }}
  @media print {{ .no-print {{ display:none }} }}
  table {{ border-collapse:collapse; width:100%; }}
  td,th {{ border:1px solid #999; padding:4px 6px; }}
  .title {{ font-size:16px; font-weight:bold; letter-spacing:2px; }}
</style></head><body>
<div class="no-print" style="background:#e0f2fe;padding:8px;margin-bottom:10px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer">🖨️ PDF印刷</button>
</div>

<div class="title">クレーン.作業車等 依頼書</div>

<table style="margin:10px 0">
  <tr>
    <td style="background:#f0f0f0;width:60px">現場名</td>
    <td colspan="3">{po.customer_name or ' '}</td>
    <td style="background:#f0f0f0;width:40px">注番</td>
    <td style="color:red;font-weight:bold">{po.child_no or '要確認'}</td>
  </tr>
  <tr>
    <td style="background:#f0f0f0">住所</td>
    <td colspan="5"> </td>
  </tr>
  <tr>
    <td style="background:#f0f0f0">TEL</td>
    <td colspan="2"> </td>
    <td style="background:#f0f0f0">ご担当者</td>
    <td colspan="2"> </td>
  </tr>
</table>

<table style="margin-bottom:10px">
  <tr>
    <td rowspan="2" style="background:#f0f0f0;width:60px">依頼業者</td>
    <td colspan="3"> </td>
    <td colspan="2" style="text-align:right">御中</td>
  </tr>
  <tr>
    <td style="background:#f0f0f0;width:60px">ご担当者</td>
    <td> </td>
    <td style="background:#f0f0f0;width:30px">TEL</td>
    <td> </td>
    <td style="background:#f0f0f0;width:30px">FAX</td>
  </tr>
</table>

<p style="font-size:10px">下記、手配お願い致します。※請求書には右上の注番を記入してください。</p>

{crane_tables}

<div style="margin-top:15px;border:2px solid #000;padding:8px;display:flex;align-items:center">
  <div style="font-size:14px;font-weight:bold;margin-right:15px">井上電設株式会社</div>
  <div style="font-size:10px">〒460-0022 名古屋市中区金山四丁目3番17号 TEL(052)322-5271 FAX(052)332-5273</div>
  <div style="margin-left:auto;font-size:10px">担当: {po.sales_person_name or ' '}  作成:     </div>
</div>
</body></html>"""

    return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename=crane_{po.child_no}.html"})


# =============================================
# 送り状PDF
# =============================================
@router.get("/project-order/{order_id}/shipping-pdf")
def shipping_pdf(order_id: str, db: Session = Depends(get_db)):
    """送り状PDF"""
    from app.db.models import ProjectOrder
    po = db.query(ProjectOrder).filter(
        pk_or_code(ProjectOrder.id, ProjectOrder.child_no, order_id)
    ).first()
    if not po: raise HTTPException(404)

    ship_one = (
        '<table style="margin-bottom:8px">'
        '<tr><td style="background:#f0f0f0;width:60px">車種</td>'
        '<td style="background:#ff4444;color:#fff;min-width:120px"> </td>'
        '<td style="background:#f0f0f0;width:40px">積込</td>'
        '<td style="min-width:100px"> </td>'
        '<td style="background:#f0f0f0;width:40px">到着</td>'
        '<td style="min-width:100px"> </td></tr>'
        '<tr><td style="background:#f0f0f0">積込1.</td><td> </td><td colspan="4"> </td></tr>'
        '<tr><td style="background:#f0f0f0">積込2.</td><td> </td><td colspan="4"> </td></tr>'
        '<tr><td style="background:#f0f0f0">積込3.</td><td> </td><td colspan="4"> </td></tr>'
        '</table>'
    )
    shipping_tables = ship_one * 3

    html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>送り状</title>
<style>
  body {{ font-family: 'Hiragino Sans','Yu Gothic',sans-serif; font-size:11px; margin:15mm; }}
  @media print {{ .no-print {{ display:none }} }}
  table {{ border-collapse:collapse; width:100%; }}
  td,th {{ border:1px solid #999; padding:4px 6px; }}
</style></head><body>
<div class="no-print" style="background:#e0f2fe;padding:8px;margin-bottom:10px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer">🖨️ PDF印刷</button>
</div>

<h2 style="font-size:18px;font-weight:bold;margin-bottom:10px">送 り 状</h2>

<table style="margin-bottom:10px">
  <tr>
    <td style="background:#ff4444;color:#fff;font-weight:bold;width:60px">送り先</td>
    <td style="font-weight:bold">{po.customer_name or ' '}</td>
  </tr>
  <tr><td style="background:#f0f0f0">住所</td><td> </td></tr>
  <tr>
    <td style="background:#f0f0f0">TEL</td><td style="width:200px"> </td>
  </tr>
</table>

<table style="margin-bottom:10px">
  <tr>
    <td style="background:#f0f0f0;width:60px">運送業者</td>
    <td style="width:150px"> </td>
    <td style="background:#f0f0f0;width:60px">ご担当者</td>
    <td> </td>
    <td style="background:#f0f0f0;width:30px">TEL</td>
    <td> </td>
  </tr>
  <tr>
    <td style="background:#f0f0f0">備考</td>
    <td colspan="5"> </td>
  </tr>
</table>

{shipping_tables}

<div style="margin-top:15px;border:2px solid #000;padding:8px;display:flex;align-items:center">
  <div style="font-size:14px;font-weight:bold;margin-right:15px">井上電設株式会社</div>
  <div style="font-size:10px">〒460-0022 名古屋市中区金山四丁目3番17号 TEL(052)322-5271 FAX(052)332-5273</div>
  <div style="margin-left:auto;font-size:10px">担当: {po.sales_person_name or ' '}  作成:     </div>
</div>
</body></html>"""

    return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename=shipping_{po.child_no}.html"})


# =============================================
# 宿泊予約票PDF
# =============================================
@router.get("/project-order/{order_id}/hotel-pdf")
def hotel_pdf(order_id: str, db: Session = Depends(get_db)):
    """宿泊予約票PDF"""
    from app.db.models import ProjectOrder
    po = db.query(ProjectOrder).filter(
        pk_or_code(ProjectOrder.id, ProjectOrder.child_no, order_id)
    ).first()
    if not po: raise HTTPException(404)

    hotel_one = '<tr>' + '<td style="height:25px"></td>' + '<td></td>' * 11 + '</tr>'
    hotel_rows = hotel_one * 5

    html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8">
<title>宿泊予約票</title>
<style>
  body {{ font-family: 'Hiragino Sans','Yu Gothic',sans-serif; font-size:11px; margin:15mm; }}
  @media print {{ .no-print {{ display:none }} }}
  table {{ border-collapse:collapse; width:100%; }}
  td,th {{ border:1px solid #999; padding:4px 6px; }}
  th {{ background:#f0f0f0; }}
</style></head><body>
<div class="no-print" style="background:#e0f2fe;padding:8px;margin-bottom:10px;border-radius:6px">
  <button onclick="window.print()" style="background:#2563eb;color:#fff;border:none;padding:6px 16px;border-radius:5px;cursor:pointer">🖨️ PDF印刷</button>
</div>

<h2 style="font-size:16px;font-weight:bold;margin-bottom:4px">宿泊予約票</h2>
<p style="font-size:9px;color:#666;margin-bottom:10px">
  ※基本は朝食なしで!変更.キャンセルは必ず宿へ連絡!予約したら旅費の領収書を書くことを忘れずに!
</p>

<table style="margin-bottom:8px">
  <tr>
    <th style="width:60px">受注番号</th>
    <td style="font-weight:bold">{po.child_no or ' '}</td>
    <th style="width:60px">現場</th>
    <td>{po.customer_name or ' '}</td>
  </tr>
  <tr>
    <th>担当者</th>
    <td>{po.sales_person_name or ' '}</td>
    <th>出荷予定日</th>
    <td>{po.expected_shipment_date or ' '}</td>
  </tr>
</table>

<table>
  <thead>
    <tr>
      <th style="width:120px">ホテル名</th>
      <th style="width:80px">TEL</th>
      <th style="width:80px">FAX</th>
      <th style="width:50px">IN</th>
      <th style="width:50px">OUT</th>
      <th style="width:30px">泊</th>
      <th style="width:30px">人数</th>
      <th style="width:50px">値段/泊</th>
      <th>宿泊者</th>
      <th style="width:40px">カード</th>
      <th>備考</th>
      <th style="width:40px">駐車場</th>
    </tr>
  </thead>
  <tbody>
    {hotel_rows}
  </tbody>
</table>

<div style="margin-top:15px;border:2px solid #000;padding:8px;display:flex;align-items:center">
  <div style="font-size:14px;font-weight:bold;margin-right:15px">井上電設株式会社</div>
  <div style="font-size:10px">〒460-0022 名古屋市中区金山四丁目3番17号 TEL(052)322-5271 FAX(052)332-5273</div>
</div>
</body></html>"""

    return StreamingResponse(io.BytesIO(html.encode("utf-8")), media_type="text/html",
        headers={"Content-Disposition": f"inline; filename=hotel_{po.child_no}.html"})
