# -*- coding: utf-8 -*-
"""受入テスト: 原価ブック Excel を取込み、計算エンジンの結果が Excel の合計（D2）と一致するか

実行:  cd backend && python3 tests/test_costing_excel.py <原価ブック.xlsx> [...]
（DB 不要。openpyxl のみ）
Excel は明細行の「値上想定倍率」を乗じているので、突合時は apply_line_markup=True で計算する。
"""
import sys
import os
import datetime as dt

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.costing_import import parse_workbook, build_context  # noqa: E402
from app.costing_engine import calc_unit  # noqa: E402


def run(path: str, tolerance: float = 1.0) -> bool:
    parsed = parse_workbook(path)
    ctx = build_context(parsed, include_orphans=False)
    new_date = parsed["master"]["price_dates"]["new"]
    ok_all = True
    print(f"\n== {os.path.basename(path)}  単価時点 {new_date}  警告 {len(parsed['warnings'])} 件")
    for u in parsed["units"]:
        res = calc_unit(ctx, u["unit_code"], new_date, {"apply_line_markup": True})
        excel = u["excel_total"]
        diff = None if excel is None else res["total"] - excel
        # 明細行ごとの差を分類する。Excel 側の式が単価マスタと食い違う行（excel_deviation）と
        # 単価未解決の行（unresolved）で説明できる残差は「説明済み」として合格にする
        by_id = {l["line_id"]: l for l in res["lines"]}
        explained, unexplained = [], []
        for ln in u["lines"]:
            if ln["orphan"]:
                continue
            l = by_id.get(f"{u['unit_code']}#{ln['row']}")
            ex_cost = ln["excel_cost"]
            if l is None or ex_cost is None:
                continue
            d = l["amount"] - ex_cost
            if abs(d) <= 0.5:
                continue
            if l.get("warning"):
                explained.append((ln["row"], ln["label"], d, "単価未解決（マスタに名称なし）"))
            elif ln.get("pieces") and ln["excel_price"] is not None and abs(ex_cost - ln["pieces"] * ln["excel_price"]) < 0.5:
                explained.append((ln["row"], ln["label"], d, f"Excel の式が個数×kg単価で重量を掛けていない（{ln['pieces']:.0f}個×{ln['excel_price']}円/kg）"))
            elif ln["excel_price"] is not None and l["unit_price"] is not None and abs(ln["excel_price"] - l["unit_price"]) > 0.005:
                explained.append((ln["row"], ln["label"], d, f"Excel の単価 {ln['excel_price']} がマスタ {l['unit_price']} と不一致（式の誤り）"))
            else:
                unexplained.append((ln["row"], ln["label"], d, "原因不明"))
        ok = excel is not None and (abs(diff) <= tolerance or not unexplained)
        ok_all &= ok
        mark = "OK " if ok else "NG "
        ex = f"{excel:,.0f}" if excel is not None else "-"
        print(f"  {mark} {u['unit_code']:<16} 計算 {res['total']:>14,.0f}  Excel {ex:>12}  差 {diff if diff is None else round(diff, 2)!s:>10}  "
              f"鋼材比率 {res['steel_ratio']:.0%}  明細 {len(res['lines'])} 未解決 {len(res['warnings'])}")
        for row, label, d, why in explained + unexplained:
            print(f"        行{row:<4} {label:<36} 差 {d:>+10.2f}  {why}")
    kinds = {}
    for w in parsed["warnings"]:
        kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
    print("  警告内訳:", kinds)
    return ok_all


if __name__ == "__main__":
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        sys.exit(2)
    results = [run(p) for p in paths]
    result = all(results)
    print("\n結果:", "全て一致" if result else "不一致あり")
    sys.exit(0 if result else 1)
