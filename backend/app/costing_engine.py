# -*- coding: utf-8 -*-
"""製品原価の計算エンジン（純粋関数。DB に依存しない）

入力コンテキスト ctx の形:
  ctx["materials"][mid]   = {id, code, name, category, price_unit, preferred_supplier_id, price_policy}
  ctx["prices"][mid]      = [{supplier_id, effective_date(date), price}, ...]
  ctx["adjustments"][mid] = [{party_type, party_id, adjust_type('amount'|'percent'), value,
                              effective_from(date|None), effective_to(date|None)}, ...]
  ctx["units"][uid]       = {id, code, name, lines:[{id, section, label, line_type, material_id,
                              sub_unit_id, qty, qty_expr, markup_factor, note}]}

line_type: weight(kg) / measure(m, m2) / count / subcontract / paint / subassembly

シナリオ scenario（すべて任意）:
  steel_pct            鋼材（鋼板/面積材/形鋼/パイプ）の単価を一律 +x%
  category_factors     {種別: 倍率}    例 {"購入品": 1.15}
  material_overrides   {material_id: 単価}
  supplier_overrides   {material_id: supplier_id}
  party_id             値引き調整を適用する取引先（仕入先）の id
  apply_line_markup    True のとき明細行の markup_factor（Excel の値上想定倍率）を乗じる（Excel 再現用）
  labor_rate, overhead_rate, target_margin_rate   製品レベルの加工費・経費・目標粗利
"""
from __future__ import annotations
import datetime as dt

STEEL_CATEGORIES = {"鋼板", "面積材", "形鋼", "パイプ"}
MEASURED_LINE_TYPES = {"weight", "measure"}


class CostError(Exception):
    pass


def _to_date(d):
    if d is None:
        return None
    if isinstance(d, dt.datetime):
        return d.date()
    if isinstance(d, dt.date):
        return d
    return dt.date.fromisoformat(str(d)[:10])


def resolve_price(ctx: dict, material_id: str, price_date: dt.date, scenario: dict | None = None) -> dict:
    """資材の単価を 1 本に決める。
    戻り値 {price, supplier_id, effective_date, source, candidates:[...], adjustment}
    price は None のとき未解決。"""
    scenario = scenario or {}
    mat = ctx["materials"].get(material_id)
    if mat is None:
        return {"price": None, "supplier_id": None, "effective_date": None, "source": "missing_material",
                "candidates": [], "adjustment": None}
    if material_id in (scenario.get("material_overrides") or {}):
        p = float(scenario["material_overrides"][material_id])
        return {"price": p, "supplier_id": None, "effective_date": None, "source": "override",
                "candidates": [], "adjustment": None}

    # 仕入先ごとに、指定日以前で最新の単価を拾う
    latest_by_supplier = {}
    for row in ctx["prices"].get(material_id, []):
        d = _to_date(row.get("effective_date"))
        if d is None or d > price_date:
            continue
        sid = row.get("supplier_id")
        cur = latest_by_supplier.get(sid)
        if cur is None or d > cur["effective_date"] or (d == cur["effective_date"] and row.get("price", 0) < cur["price"]):
            latest_by_supplier[sid] = {"supplier_id": sid, "effective_date": d, "price": float(row["price"])}
    candidates = sorted(latest_by_supplier.values(), key=lambda x: (x["price"], str(x["supplier_id"])))
    if not candidates:
        return {"price": None, "supplier_id": None, "effective_date": None, "source": "no_price",
                "candidates": [], "adjustment": None}

    chosen = None
    forced = (scenario.get("supplier_overrides") or {}).get(material_id)
    policy = mat.get("price_policy") or "preferred"
    preferred = mat.get("preferred_supplier_id")
    if forced is not None:
        chosen = next((c for c in candidates if str(c["supplier_id"]) == str(forced)), None)
    if chosen is None and policy == "preferred" and preferred is not None:
        chosen = next((c for c in candidates if str(c["supplier_id"]) == str(preferred)), None)
    if chosen is None and policy == "cheapest":
        chosen = candidates[0]
    if chosen is None:
        # 採用仕入先の単価が無いときは、最新日付を優先し同日なら安い方
        chosen = sorted(candidates, key=lambda x: (x["effective_date"], -x["price"]), reverse=True)[0]

    price = chosen["price"]
    adj_applied = None
    party = scenario.get("party_id")
    for adj in ctx.get("adjustments", {}).get(material_id, []):
        pid = adj.get("party_id")
        if pid is not None and party is not None and str(pid) != str(party):
            continue
        if pid is not None and party is None and str(pid) != str(chosen["supplier_id"]):
            continue
        f, t = _to_date(adj.get("effective_from")), _to_date(adj.get("effective_to"))
        if (f and price_date < f) or (t and price_date > t):
            continue
        v = float(adj.get("value") or 0)
        if adj.get("adjust_type") == "percent":
            price = price * (1 + v / 100.0)
        else:
            price = price + v
        adj_applied = adj
        break

    # シナリオ: 鋼材一律 % と種別倍率
    cat = mat.get("category")
    if scenario.get("steel_pct") and cat in STEEL_CATEGORIES:
        price = price * (1 + float(scenario["steel_pct"]) / 100.0)
    cf = (scenario.get("category_factors") or {}).get(cat)
    if cf:
        price = price * float(cf)
    return {"price": price, "supplier_id": chosen["supplier_id"], "effective_date": chosen["effective_date"],
            "source": "adjusted" if adj_applied else "master", "candidates": candidates, "adjustment": adj_applied}


def calc_unit(ctx: dict, unit_id: str, price_date, scenario: dict | None = None, _stack: tuple = ()) -> dict:
    """ユニット（型式／サブアセンブリ）1 台分の材料費を計算する。"""
    scenario = scenario or {}
    price_date = _to_date(price_date) or dt.date.today()
    unit = ctx["units"].get(unit_id)
    if unit is None:
        raise CostError(f"ユニットが見つかりません: {unit_id}")
    if unit_id in _stack:
        raise CostError("サブアセンブリ参照が循環しています: " + " > ".join(str(s) for s in _stack + (unit_id,)))

    lines_out, warnings = [], []
    sections = {}
    steel_total = purchased_total = 0.0
    for ln in unit.get("lines", []):
        sec = ln.get("section") or "（部位なし）"
        s = sections.setdefault(sec, {"section": sec, "steel": 0.0, "purchased": 0.0, "total": 0.0})
        qty = float(ln.get("qty") or 0)
        out = {
            "line_id": ln.get("id"), "section": sec, "label": ln.get("label"), "line_type": ln.get("line_type"),
            "qty": qty, "qty_expr": ln.get("qty_expr"), "unit_price": None, "amount": 0.0,
            "price_unit": None, "material_id": ln.get("material_id"), "material_name": None,
            "material_code": None, "category": None, "supplier_id": None, "price_date": None,
            "source": None, "note": ln.get("note"), "warning": None,
        }
        if ln.get("line_type") == "subassembly":
            sub = calc_unit(ctx, ln["sub_unit_id"], price_date, scenario, _stack + (unit_id,))
            out.update({"unit_price": sub["total"], "amount": sub["total"] * qty, "price_unit": "台",
                        "material_name": sub["unit_name"], "source": "subassembly",
                        "sub_unit_id": ln["sub_unit_id"], "sub_result": sub})
            s["steel"] += sub["steel_total"] * qty
            s["purchased"] += sub["purchased_total"] * qty
            steel_total += sub["steel_total"] * qty
            purchased_total += sub["purchased_total"] * qty
            warnings.extend({**w, "via": unit["code"]} for w in sub["warnings"])
        else:
            mid = ln.get("material_id")
            mat = ctx["materials"].get(mid) if mid else None
            rp = resolve_price(ctx, mid, price_date, scenario) if mid else {"price": None, "source": "no_material"}
            price = rp["price"]
            if mat:
                out.update({"material_name": mat.get("name"), "material_code": mat.get("code"),
                            "category": mat.get("category"), "price_unit": mat.get("price_unit")})
            out.update({"supplier_id": rp.get("supplier_id"), "price_date": rp.get("effective_date"),
                        "source": rp.get("source")})
            if price is None:
                out["warning"] = "単価未解決"
                warnings.append({"kind": "unresolved_price", "unit": unit["code"], "line_id": ln.get("id"),
                                 "label": ln.get("label"), "section": sec, "material_id": mid,
                                 "message": "単価が解決できない（資材未登録または指定日以前の単価なし）"})
            else:
                factor = float(ln.get("markup_factor") or 1.0) if scenario.get("apply_line_markup") else 1.0
                out["unit_price"] = price * factor
                out["amount"] = qty * price * factor
                if (mat and mat.get("category") in STEEL_CATEGORIES) or ln.get("line_type") in MEASURED_LINE_TYPES:
                    s["steel"] += out["amount"]
                    steel_total += out["amount"]
                else:
                    s["purchased"] += out["amount"]
                    purchased_total += out["amount"]
        s["total"] = s["steel"] + s["purchased"]
        lines_out.append(out)

    total = steel_total + purchased_total
    return {
        "unit_id": unit_id, "unit_code": unit["code"], "unit_name": unit.get("name"),
        "price_date": price_date.isoformat(), "total": total,
        "steel_total": steel_total, "purchased_total": purchased_total,
        "steel_ratio": (steel_total / total) if total else 0.0,
        "sections": list(sections.values()), "lines": lines_out, "warnings": warnings,
    }


def calc_product(ctx: dict, unit_id: str, price_date, scenario: dict | None = None,
                 standard_hours: float | None = None, standard_price: float | None = None,
                 settings: dict | None = None) -> dict:
    """製品（型式）としての製造原価と売価の対比。
    settings: {labor_rate_per_hour, overhead_rate, target_margin_rate}（シナリオが優先）"""
    scenario = scenario or {}
    settings = settings or {}
    mat = calc_unit(ctx, unit_id, price_date, scenario)
    labor_rate = scenario.get("labor_rate", settings.get("labor_rate_per_hour"))
    overhead_rate = scenario.get("overhead_rate", settings.get("overhead_rate"))
    target_margin = scenario.get("target_margin_rate", settings.get("target_margin_rate"))
    hours = float(standard_hours) if standard_hours is not None else None
    labor_cost = (hours * float(labor_rate)) if (hours is not None and labor_rate is not None) else None
    base = mat["total"] + (labor_cost or 0.0)
    overhead = base * float(overhead_rate) / 100.0 if overhead_rate not in (None, "") else None
    manufacturing_cost = base + (overhead or 0.0)
    out = {
        "material": mat, "material_cost": mat["total"], "standard_hours": hours,
        "labor_rate": float(labor_rate) if labor_rate is not None else None, "labor_cost": labor_cost,
        "overhead_rate": float(overhead_rate) if overhead_rate not in (None, "") else None, "overhead_cost": overhead,
        "manufacturing_cost": manufacturing_cost,
        "standard_price": float(standard_price) if standard_price is not None else None,
        "gross_margin": None, "gross_margin_rate": None,
        "target_margin_rate": float(target_margin) if target_margin not in (None, "") else None,
        "required_price": None,
    }
    if out["standard_price"]:
        out["gross_margin"] = out["standard_price"] - manufacturing_cost
        out["gross_margin_rate"] = out["gross_margin"] / out["standard_price"]
    if out["target_margin_rate"] is not None and out["target_margin_rate"] < 100:
        out["required_price"] = manufacturing_cost / (1 - out["target_margin_rate"] / 100.0)
    return out


def diff_results(base: dict, other: dict) -> dict:
    """2 つの calc_unit 結果を明細行単位で比較し、差額を単価要因と数量要因に分ける。"""
    def key(l):
        return l.get("line_id") or (l.get("section"), l.get("label"))
    b = {key(l): l for l in base["lines"]}
    o = {key(l): l for l in other["lines"]}
    rows = []
    for k in list(b.keys()) + [k for k in o if k not in b]:
        lb, lo = b.get(k), o.get(k)
        pb = (lb or {}).get("unit_price") or 0.0
        po = (lo or {}).get("unit_price") or 0.0
        qb = (lb or {}).get("qty") or 0.0
        qo = (lo or {}).get("qty") or 0.0
        ab = (lb or {}).get("amount") or 0.0
        ao = (lo or {}).get("amount") or 0.0
        if abs(ao - ab) < 0.005:
            continue
        rows.append({
            "section": (lo or lb).get("section"), "label": (lo or lb).get("label"),
            "line_type": (lo or lb).get("line_type"),
            "base_price": pb, "other_price": po, "base_qty": qb, "other_qty": qo,
            "base_amount": ab, "other_amount": ao, "diff": ao - ab,
            "price_effect": (po - pb) * qb, "qty_effect": (qo - qb) * po,
        })
    rows.sort(key=lambda r: -abs(r["diff"]))
    return {"base_total": base["total"], "other_total": other["total"],
            "diff": other["total"] - base["total"],
            "diff_rate": ((other["total"] - base["total"]) / base["total"]) if base["total"] else None,
            "rows": rows}
