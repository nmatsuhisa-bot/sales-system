#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""固定資産台帳 CSV と機械一覧表 CSV から、初期の紐付け CSV（画面「紐付けCSVの取込」用）を作る。

  python3 tools/equipment_initial_links.py <台帳.csv> <機械一覧.csv> [-o 出力.csv]

自動紐付け（画面の「自動紐付け」ボタン＝資産名先頭の番号一致）では拾えない、
2026-09-15 の突合作業で人が判断した対応だけをここに書いてある。
すべて confidence=candidate（要確認）で出すので、画面で内容を見て「確定」にすること。
asset_key の作り方は backend/app/api/equipment.py の import_assets と同じ
（管理番号があればそれ、無ければ 'N' + sha1(資産名|取得日|取得価額)[:10]、同一キーは -2, -3 …）。
"""
import argparse
import csv
import hashlib
import sys

# (台帳の資産名に含まれる語, 台帳の取得価額 or None, 機械の管理ID, 種別, メモ)
RULES = [
    ("ｷｰｼｰﾀｰ", "15500000", "SK-36", "本体", "価格15,500,000・2026年・ｷｰ溝機KS5-M と一致"),
    ("MTT-1300", "12900000", "SK-37", "本体", "型式MTT-1300 ｸﾗﾝﾌﾟｼｰﾏ② と一致"),
    ("01-SK ｱﾏﾀﾞﾊｲﾌﾞﾘｯﾄﾞ", None, "SK-25", "本体", "圧縮後716万・2023.1・ﾊｲﾌﾞﾘｯﾄﾞﾍﾞﾝﾀﾞｰHG1303。台帳名『01-SK』は一覧の番号体系と不一致"),
    ("01-K ホイストクレーン", None, "K-39", "本体", "2023.1・走行ｸﾚｰﾝ2号機。価格 台帳1,015,000 vs 一覧570,000+無線化265,000 で不一致"),
    ("機械SK-34", None, "SK-34", "本体", "摘要に『機械SK-34』。価格 台帳452,600 vs 一覧392,600"),
    ("機械SK-35", None, "B-32", "本体", "摘要は『機械SK-35』だが一覧に SK-35 は無い。価格300,000・2026年・ｽﾄﾘｰﾑｼﾞｪﾝﾄﾙ は B-32 と一致。番号を要確認"),
    ("亀倉精機", "243000", "K-40", "本体", "価格243,000・2023.11・ﾊﾟﾝﾁｬｰRFA3(亀倉精機) と一致"),
    ("2次元ファイバレーザー加工機", None, "H-13", "リース", "リース資産。一覧では『無し』扱い。価格 台帳62,545,728 vs 一覧77,000,000"),
    ("KK-20 日立 2.8t天井クレーン", None, "K-24", "本体", "台帳名『3，4号機』= K-24 と K-25 の2台分"),
    ("KK-20 日立 2.8t天井クレーン", None, "K-25", "本体", "台帳名『3，4号機』= K-24 と K-25 の2台分"),
    ("KK-06 ｱｲｾﾙ3本ﾛｰﾙ", None, "B-05", "本体", "台帳は型式BU-SK1300・2002年。一覧 K-06 は1967年、B-05(桜田南) が BU-SK1300・2002年。どちらか要確認（K-06 側は自動紐付けで候補になる）"),
    ("SK-26 自動ハンドソーマシン", None, "SK-27", "本体", "台帳SK-26(4,900,000・2023.6) は一覧の SK-27 ﾊﾞﾝﾄﾞｿｰ LTAⅡ2630(4,900,000・2023.7)。一覧の SK-26 は溶接機。台帳の番号誤りの可能性"),
    ("FF-38 福江工場 2tクレーン無線化工事", None, "F", "本体", "一覧の管理番号『Ｆ』（無線化工事 2,227,500・2017.2）"),
    ("長浜製作所 制御盤等", None, "F-14", "付帯工事", "管理番号 0000000867-01 = SKF-14 ﾊﾞﾗﾝｼﾝｸﾞﾏｼﾝ(0000000867) の枝番。制御盤更新"),
    ("SK-20 ダイヘン溶接ロボット", None, "SK-21", "親資産に含む", "一覧の価格欄『上記金額に含む』（SK-20 に含む）"),
    ("SK-20 ダイヘン溶接ロボット", None, "SK-22", "親資産に含む", "一覧の価格欄『上記金額に含む』（SK-20 に含む）"),
    ("MTT-1300", "12900000", "SK-38", "親資産に含む", "一覧の価格欄『ｸﾗﾝﾌﾟｼｰﾏ総額内に含まれている』（SK-37 に含む）"),
]
# 同名の一括償却資産が複数あるものは、出てきた順に機械へ割り当てる
SEQ_RULES = [
    ("ヒルティ　ハンマードリル", ["施-07", "施-08"], "本体", "139,000×2・2024.4 と一致（2台どちらがどちらかは不明）"),
    ("ダイヘン供給装置延長10ｍセット", ["SK-30", "SK-31"], "付帯工事", "2024.11 一括×4。一覧の SK-30〜33(DM-350Ⅲ 2024.10) の付属品の可能性。価格180,000 は一覧に無い"),
    ("ダイヘン供給装置延長15ｍセット", ["SK-32", "SK-33"], "付帯工事", "同上"),
]


def read_csv(path):
    for enc in ("utf-8-sig", "cp932"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"文字コードを判定できません: {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ledger"); ap.add_argument("machines")
    ap.add_argument("-o", "--out", default="_work/equipment/links_initial.csv")
    args = ap.parse_args()
    ledger = read_csv(args.ledger)
    codes = {(r.get("管理番号") or "").strip().replace("Ｆ", "F") for r in read_csv(args.machines)}
    keys_seen, out, seq_state = {}, [], {}
    for r in ledger:
        name = (r.get("固定資産名") or "").strip()
        no = (r.get("管理番号") or "").strip()
        key = no or ("N" + hashlib.sha1(f"{name}|{(r.get('取得日') or '').strip()}|{(r.get('取得価額') or '').strip()}".encode("utf-8")).hexdigest()[:10])
        n = keys_seen.get(key, 0) + 1
        keys_seen[key] = n
        if n > 1:
            key = f"{key}-{n}"
        price = (r.get("取得価額") or "").strip()
        for word, p, code, lt, note in RULES:
            if word in name and (p is None or p == price):
                if code not in codes:
                    print(f"警告: 機械 {code} が一覧に無い（{name}）", file=sys.stderr)
                out.append({"machine_code": code, "asset_key": key, "link_type": lt, "confidence": "candidate", "note": note})
        for word, cands, lt, note in SEQ_RULES:
            if word in name:
                i = seq_state.get(word, 0)
                if i < len(cands):
                    out.append({"machine_code": cands[i], "asset_key": key, "link_type": lt, "confidence": "candidate", "note": note})
                    seq_state[word] = i + 1
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["machine_code", "asset_key", "link_type", "confidence", "note"])
        w.writeheader(); w.writerows(out)
    print(f"{len(out)} 件 → {args.out}")


if __name__ == "__main__":
    main()
