#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工場機械一覧表（PDF）→ 取込用 CSV（UTF-8 BOM 付き、列名は一覧表のまま）

  python3 tools/equipment_machine_list_pdf2csv.py <一覧表.pdf> [-o 出力.csv]

出力した CSV は 画面「工場機械管理 → 取込・設定 → 機械一覧表の取込」で読み込む。
pdfplumber が必要（ローカル作業用。サーバ側では使わない）。
セル内の改行は空白に置き換える。ヘッダー行（先頭が『工場』）は複数ページにあるので毎回読み飛ばす。
"""
import argparse
import csv
import sys

import pdfplumber


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", default="_work/equipment/machine_list.csv")
    args = ap.parse_args()
    hdr, rows = None, []
    with pdfplumber.open(args.pdf) as pdf:
        for p in pdf.pages:
            for t in p.extract_tables():
                for row in t:
                    if row and row[0] == "工場":
                        hdr = [(c or "").replace("\n", "") for c in row]
                        continue
                    if not row or all(c in (None, "") for c in row) or hdr is None:
                        continue
                    r = [(c or "").replace("\n", " ").strip() for c in row]
                    r += [""] * (len(hdr) - len(r))
                    rows.append(dict(zip(hdr, r[: len(hdr)])))
    if hdr is None:
        print("ヘッダー行（先頭セルが『工場』）が見つかりません", file=sys.stderr)
        return 1
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=hdr)
        w.writeheader()
        w.writerows(rows)
    codes = [r.get("管理番号", "").strip() for r in rows]
    print(f"{len(rows)} 行を書き出しました → {args.out}（管理番号あり {sum(1 for c in codes if c)} / 空欄 {sum(1 for c in codes if not c)}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
