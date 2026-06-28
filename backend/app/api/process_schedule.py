"""工程管理 API — 工程テンプレート・工程表管理"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from app.db.models import (
    get_db, ProcessTemplate, ProcessTemplateStep,
    WorkSchedule, WorkScheduleItem, ProjectOrder
)
from datetime import date, timedelta
import io, calendar

router = APIRouter()

# =============================================
# 工程テンプレート
# =============================================

@router.get("/templates")
def list_templates(product_type: str = Query(None), db: Session = Depends(get_db)):
    q = db.query(ProcessTemplate).options(joinedload(ProcessTemplate.steps)).filter(ProcessTemplate.is_active == True)
    if product_type:
        q = q.filter(ProcessTemplate.product_type == product_type)
    return [_tmpl_dict(t) for t in q.order_by(ProcessTemplate.product_type, ProcessTemplate.template_name).all()]

@router.post("/templates")
def create_template(data: dict, db: Session = Depends(get_db)):
    t = ProcessTemplate(
        product_type=data.get("product_type"),
        template_name=data["template_name"],
        notes=data.get("notes"),
    )
    db.add(t); db.commit(); db.refresh(t)
    return _tmpl_dict(t)

@router.put("/templates/{template_id}")
def update_template(template_id: str, data: dict, db: Session = Depends(get_db)):
    t = db.query(ProcessTemplate).filter(ProcessTemplate.id == template_id).first()
    if not t: raise HTTPException(404)
    for k in ["product_type", "template_name", "notes"]:
        if k in data: setattr(t, k, data[k])
    if "steps" in data:
        for s in t.steps: db.delete(s)
        db.flush()
        for i, sd in enumerate(data["steps"]):
            db.add(ProcessTemplateStep(
                template_id=t.id, step_no=sd.get("step_no", i+1),
                step_name=sd["step_name"],
                offset_start_days=sd.get("offset_start_days", -7),
                duration_days=sd.get("duration_days", 1),
                equipment=sd.get("equipment"),
                color=sd.get("color", "#3b82f6"),
                notes=sd.get("notes"),
            ))
    db.commit(); db.refresh(t)
    return _tmpl_dict(t)

@router.delete("/templates/{template_id}")
def delete_template(template_id: str, db: Session = Depends(get_db)):
    t = db.query(ProcessTemplate).filter(ProcessTemplate.id == template_id).first()
    if not t: raise HTTPException(404)
    t.is_active = False; db.commit()
    return {"ok": True}

def _tmpl_dict(t: ProcessTemplate):
    return {
        "id": str(t.id), "product_type": t.product_type, "template_name": t.template_name,
        "notes": t.notes,
        "steps": [_step_dict(s) for s in t.steps],
    }

def _step_dict(s: ProcessTemplateStep):
    return {
        "id": str(s.id), "step_no": s.step_no, "step_name": s.step_name,
        "offset_start_days": s.offset_start_days, "duration_days": s.duration_days,
        "equipment": s.equipment, "color": s.color, "notes": s.notes,
    }

# =============================================
# 工程表
# =============================================

@router.get("/schedules")
def list_schedules(year: int = Query(None), month: int = Query(None), span: int = Query(None),
                   order_id: str = Query(None), db: Session = Depends(get_db)):
    """span（1/3/6/12ヶ月）指定時は year/month を起点に複数月を表示。未指定時は従来通り。"""
    q = db.query(WorkSchedule).options(joinedload(WorkSchedule.project_order))
    if order_id:
        q = q.filter(WorkSchedule.project_order_id == order_id)
    elif span and year and month:
        start_ord = year * 12 + (month - 1)
        end_ord = start_ord + span - 1
        ordinal = WorkSchedule.work_year * 12 + WorkSchedule.work_month - 1
        q = q.filter(ordinal >= start_ord, ordinal <= end_ord)
    else:
        if year: q = q.filter(WorkSchedule.work_year == year)
        if month: q = q.filter(WorkSchedule.work_month == month)
    return [_sched_dict(s, include_items=False) for s in q.order_by(WorkSchedule.work_year, WorkSchedule.work_month, WorkSchedule.work_no).all()]

@router.post("/schedules")
def create_schedule(data: dict, db: Session = Depends(get_db)):
    s = WorkSchedule(
        project_order_id=data.get("project_order_id"),
        customer_name=data.get("customer_name"),
        delivery_name=data.get("delivery_name"),
        work_name=data.get("work_name"),
        work_no=data.get("work_no"),
        responsible_person=data.get("responsible_person"),
        work_year=data.get("work_year"),
        work_month=data.get("work_month"),
        delivery_date=data.get("delivery_date"),
        created_date=data.get("created_date", date.today().isoformat()),
        notes=data.get("notes"),
        status=data.get("status", "作成中"),
    )
    db.add(s); db.flush()
    for i, item in enumerate(data.get("items", [])):
        db.add(WorkScheduleItem(
            schedule_id=s.id, step_no=item.get("step_no", i+1),
            row_type=item.get("row_type", "task"),
            step_name=item["step_name"],
            start_day=item.get("start_day"),
            end_day=item.get("end_day"),
            equipment=item.get("equipment"),
            color=item.get("color", "#3b82f6"),
            notes=item.get("notes"),
        ))
    db.commit(); db.refresh(s)
    return _sched_dict(s)

@router.get("/schedules/{schedule_id}")
def get_schedule(schedule_id: str, db: Session = Depends(get_db)):
    s = db.query(WorkSchedule).options(
        joinedload(WorkSchedule.items), joinedload(WorkSchedule.project_order)
    ).filter(WorkSchedule.id == schedule_id).first()
    if not s: raise HTTPException(404)
    return _sched_dict(s)

@router.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: str, data: dict, db: Session = Depends(get_db)):
    s = db.query(WorkSchedule).options(joinedload(WorkSchedule.items)).filter(WorkSchedule.id == schedule_id).first()
    if not s: raise HTTPException(404)
    for k in ["customer_name","delivery_name","work_name","work_no","responsible_person",
              "work_year","work_month","delivery_date","created_date","notes","status"]:
        if k in data: setattr(s, k, data[k])
    if "items" in data:
        for item in s.items: db.delete(item)
        db.flush()
        for i, item in enumerate(data["items"]):
            db.add(WorkScheduleItem(
                schedule_id=s.id, step_no=item.get("step_no", i+1),
                row_type=item.get("row_type", "task"),
                step_name=item["step_name"],
                start_day=item.get("start_day"),
                end_day=item.get("end_day"),
                equipment=item.get("equipment"),
                color=item.get("color", "#3b82f6"),
                notes=item.get("notes"),
            ))
    db.commit(); db.refresh(s)
    return _sched_dict(s)

@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    s = db.query(WorkSchedule).filter(WorkSchedule.id == schedule_id).first()
    if not s: raise HTTPException(404)
    db.delete(s); db.commit()

@router.post("/schedules/generate")
def generate_from_template(data: dict, db: Session = Depends(get_db)):
    """テンプレートと納期から工程表をプレビュー生成（DBには保存しない。保存は別途）"""
    template_id = data.get("template_id")
    delivery = date.fromisoformat(data["delivery_date"])
    t = db.query(ProcessTemplate).options(joinedload(ProcessTemplate.steps)).filter(
        ProcessTemplate.id == template_id
    ).first()
    if not t: raise HTTPException(404, "テンプレートが見つかりません")

    # 工程月は納期の月
    year = delivery.year; month = delivery.month

    # 受注情報を補完
    po = None
    if data.get("project_order_id"):
        po = db.query(ProjectOrder).filter(ProjectOrder.id == data["project_order_id"]).first()

    items = []
    for step in t.steps:
        start_date = delivery + timedelta(days=step.offset_start_days)
        end_date = start_date + timedelta(days=step.duration_days - 1)
        # 同月内にクランプ
        start_day = max(1, start_date.day) if start_date.month == month else (1 if start_date < delivery else None)
        end_day = min(end_date.day, calendar.monthrange(year, month)[1]) if end_date.month == month else (calendar.monthrange(year, month)[1] if end_date > delivery else None)
        items.append({
            "step_no": step.step_no, "row_type": "task", "step_name": step.step_name,
            "start_day": start_day, "end_day": end_day,
            "equipment": step.equipment, "color": step.color or "#3b82f6", "notes": None,
        })

    return {
        "project_order_id": data.get("project_order_id"),
        "customer_name": data.get("customer_name") or (po.customer_name if po else None),
        "delivery_name": data.get("delivery_name"),
        "work_name": data.get("work_name") or (po.project_name if po else None),
        "work_no": data.get("work_no") or (po.child_no if po else None),
        "responsible_person": data.get("responsible_person") or (po.sales_person_name if po else None),
        "work_year": year, "work_month": month,
        "delivery_date": str(delivery), "status": "作成中",
        "items": items,
    }

def _sched_dict(s: WorkSchedule, include_items: bool = True):
    d = {
        "id": str(s.id),
        "project_order_id": str(s.project_order_id) if s.project_order_id else None,
        "child_no": s.project_order.child_no if s.project_order else None,
        "customer_name": s.customer_name, "delivery_name": s.delivery_name,
        "work_name": s.work_name, "work_no": s.work_no,
        "responsible_person": s.responsible_person,
        "work_year": s.work_year, "work_month": s.work_month,
        "delivery_date": str(s.delivery_date) if s.delivery_date else None,
        "created_date": str(s.created_date) if s.created_date else None,
        "notes": s.notes, "status": s.status,
    }
    if include_items:
        d["items"] = [_item_dict(i) for i in s.items]
    return d

def _item_dict(i: WorkScheduleItem):
    return {
        "id": str(i.id), "step_no": i.step_no, "row_type": i.row_type,
        "step_name": i.step_name, "start_day": i.start_day, "end_day": i.end_day,
        "equipment": i.equipment, "color": i.color, "notes": i.notes,
    }

# =============================================
# 工程表 HTML/PDF 出力
# =============================================

@router.get("/schedules/{schedule_id}/pdf")
def export_schedule_pdf(schedule_id: str, db: Session = Depends(get_db)):
    s = db.query(WorkSchedule).options(joinedload(WorkSchedule.items)).filter(WorkSchedule.id == schedule_id).first()
    if not s: raise HTTPException(404)
    html = _build_schedule_html(s)
    from urllib.parse import quote
    fname = quote(f"工程表_{s.work_no or schedule_id}.html")
    return StreamingResponse(
        io.BytesIO(html.encode("utf-8")),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{fname}"}
    )

def _build_schedule_html(s: WorkSchedule) -> str:
    import calendar as cal
    year = s.work_year or date.today().year
    month = s.work_month or date.today().month
    days_in_month = cal.monthrange(year, month)[1]
    days = list(range(1, days_in_month + 1))
    WEEKDAYS_JP = ['月','火','水','木','金','土','日']

    def dow(d: int) -> str:
        wd = cal.weekday(year, month, d)
        return WEEKDAYS_JP[wd]

    def dow_color(d: int) -> str:
        wd = cal.weekday(year, month, d)
        if wd == 5: return '#bfdbfe'   # 土: 水色
        if wd == 6: return '#fecaca'   # 日: 赤
        return 'white'

    # ヘッダー行のday columns
    day_header = ''.join(
        f'<td style="width:20px;text-align:center;background:{dow_color(d)};border:1px solid #999;font-size:9px;padding:1px 0">{d}</td>'
        for d in days
    )
    dow_row = ''.join(
        f'<td style="width:20px;text-align:center;background:{dow_color(d)};border:1px solid #999;font-size:8px;padding:1px 0;color:{"#1d4ed8" if cal.weekday(year,month,d)==5 else "#dc2626" if cal.weekday(year,month,d)==6 else "#444"}">{dow(d)}</td>'
        for d in days
    )

    def gantt_cells(item) -> str:
        cells = []
        for d in days:
            in_range = (item.start_day is not None and item.end_day is not None
                       and item.start_day <= d <= item.end_day)
            color = item.color or '#3b82f6'
            if in_range:
                cells.append(f'<td style="background:{color};border:1px solid #999;padding:0"></td>')
            else:
                cells.append(f'<td style="border:1px solid #ccc;padding:0"></td>')
        return ''.join(cells)

    # 工程表明細行
    item_rows = ''
    for item in s.items:
        if item.row_type == 'blank':
            item_rows += f'<tr style="height:14px"><td colspan="{2+len(days)}" style="border:1px solid #ddd"></td></tr>'
            continue
        item_rows += f'''<tr style="height:18px">
            <td style="border:1px solid #999;padding:1px 4px;font-size:9px;white-space:nowrap;max-width:200px;overflow:hidden">{item.step_name}</td>
            <td style="border:1px solid #999;padding:1px 4px;font-size:8px;white-space:nowrap;color:#555">{item.equipment or ""}</td>
            {gantt_cells(item)}
        </tr>'''

    # 注記行（※マーク付き）
    note_rows = ''
    if s.notes:
        for note in s.notes.split('\n'):
            if note.strip():
                note_rows += f'<tr style="height:16px"><td colspan="{2+len(days)}" style="border:1px solid #ddd;padding:1px 4px;font-size:9px">※ {note}</td></tr>'

    created = str(s.created_date or '') if s.created_date else ''

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<style>
@page {{ size: A3 landscape; margin: 8mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: "MS Gothic","Meiryo",sans-serif; font-size:10px; margin:0; padding:0; }}
table {{ border-collapse: collapse; }}
@media print {{ body {{ margin:0; }} }}
</style>
</head>
<body>
<div style="text-align:right;font-size:10px;margin-bottom:2px">作成日 {created}</div>
<div style="text-align:center;font-size:18px;font-weight:bold;margin-bottom:4px">工 程 表</div>

<!-- ヘッダー情報 -->
<table style="width:100%;margin-bottom:4px;border-collapse:collapse">
<tr>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px;width:60px;font-weight:bold">納入先</td>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px" colspan="3">{s.customer_name or "　"} 殿</td>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px;width:60px;font-weight:bold">御担当者</td>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px">{s.delivery_name or "　"}</td>
</tr>
<tr>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px;font-weight:bold">工事名</td>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px">{s.work_name or "　"}</td>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px;width:50px;font-weight:bold">工番</td>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px;width:80px">{s.work_no or "　"}</td>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px;font-weight:bold">担当者</td>
  <td style="border:1px solid #999;padding:3px 6px;font-size:10px">{s.responsible_person or "　"}</td>
</tr>
</table>

<!-- ガントチャート -->
<table style="width:100%;table-layout:fixed">
<colgroup>
  <col style="width:180px">
  <col style="width:80px">
  {''.join(f'<col style="width:20px">' for _ in days)}
</colgroup>
<thead>
  <tr style="background:#f0f0f0">
    <th style="border:1px solid #999;padding:2px 4px;font-size:10px;text-align:left">{year}年 {month}月</th>
    <th style="border:1px solid #999;padding:2px 4px;font-size:9px;text-align:center">機材</th>
    {day_header}
  </tr>
  <tr>
    <td style="border:1px solid #999;padding:1px 4px;font-size:9px">工事名称</td>
    <td style="border:1px solid #999"></td>
    {dow_row}
  </tr>
</thead>
<tbody>
{item_rows}
{note_rows}
<!-- 空白行 -->
<tr style="height:14px"><td colspan="{2+len(days)}" style="border:1px solid #ddd"></td></tr>
<tr style="height:14px"><td colspan="{2+len(days)}" style="border:1px solid #ddd"></td></tr>
</tbody>
</table>

<!-- 検印欄 -->
<table style="margin-top:6px;border-collapse:collapse">
<tr>
  <td style="border:1px solid #999;padding:2px 8px;font-size:9px;text-align:center;font-weight:bold">営業</td>
  <td style="border:1px solid #999;padding:2px 8px;font-size:9px;text-align:center;font-weight:bold">技術</td>
  <td style="border:1px solid #999;padding:2px 8px;font-size:9px;text-align:center;font-weight:bold">製造</td>
  <td style="border:1px solid #999;padding:2px 8px;font-size:9px;text-align:center;font-weight:bold">施工</td>
  <td style="border:1px solid #999;padding:2px 8px;font-size:9px;text-align:center;font-weight:bold">作成</td>
</tr>
<tr>
  <td style="border:1px solid #999;height:32px;width:64px"></td>
  <td style="border:1px solid #999;height:32px;width:64px"></td>
  <td style="border:1px solid #999;height:32px;width:64px"></td>
  <td style="border:1px solid #999;height:32px;width:64px"></td>
  <td style="border:1px solid #999;height:32px;width:64px"></td>
</tr>
</table>

<script>window.onload=function(){{window.print();}}</script>
</body>
</html>'''
    return html
