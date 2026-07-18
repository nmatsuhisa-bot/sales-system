#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cad2estimate.py — CAD図面(DXF)から見積明細の骨格を自動生成するプロトタイプ

会議(2026-07-17) 3.2「図面からの見積もり自動化」STEP 2 の実装。
図面内のブロック名・テキストから自社製品の型式と仕様を抽出し、
大項目1〜5(集塵装置/空気輸送装置/定量排出装置/安全装置/制御盤)の
見積骨格を 1-1-1 形式の3階層番号で出力する。

使い方:
    python3 tools/cad2estimate.py <file.dxf> [<file2.dxf> ...] [--json]
    # DWGしか無い場合は事前に dwg2dxf (LibreDWG) で変換する:
    #   dwg2dxf -o out.dxf input.dwg

前提: pip3 install ezdxf
"""
import sys
import re
import json
import collections

try:
    import ezdxf
except ImportError:
    sys.exit("ezdxf が必要です: pip3 install ezdxf")

# ---------------------------------------------------------------- 抽出定義

# ブロック名から取り除く修飾語(ビュー名・状態語)。型式の正規化に使う
VIEW_WORDS = (
    "平面", "正面", "側面", "裏面", "左側面", "右側面", "立面", "天井",
    "基礎", "上", "下", "中断ｽﾃｰｼﾞ", "中段", "踊り場", "本体略図",
    "ｼｭｰﾄ", "ﾌﾗﾝｼﾞ", "ﾓｰﾀｰｶﾊﾞｰ付", "モーターカバー付", "受",
)
PREFIX_WORDS = ("単色", "消火配管_", "消火配管")

# 型式パターン: 系列記号 + 数字(サイズ)。図面・見積の両方で使われる表記
MODEL_RE = re.compile(
    r"(BFR\s?\d+[WX×]?\s?\d*L?"     # BFR3X5 / BFR5W6L / BFR3×6
    r"|BFQ\d+[VW]?"                  # BFQ7 / BFQ10V
    r"|SCA\d+"                       # SCA675 / SCA844
    r"|SCD\d+"                       # SCD5
    r"|ADC\d+N?"                     # ADC550 / ADC600N
    r"|RV\d+[X×]\d+"                # RV25X60 / RV30×80
    r"|CY[PT]?\d+[ES]?"             # CY600 / CYP600 / CYT750 / CY950
    r"|PLD[\d.]+"                    # PLD2.2 / PLD7.5
    r"|PL\d+"                        # PL200 / PL4000
    r"|FS\d+"                        # FS25
    r"|ASM\d+"                       # ASM300
    r"|SD-?\d+E?"                    # SD-4E / SD-2E
    r")",
    re.IGNORECASE,
)

# 系列 → (大項目, 表示名)。大項目番号は原本見積(新栄合板 26-02-78A ほか)の並び
FAMILY = {
    "BFR": (1, "ﾊﾞｸﾞﾌｨﾙﾀｰ集塵機"),
    "BFQ": (1, "小型ﾊﾞｸﾞﾌｨﾙﾀｰ集塵機"),
    "PL":  (2, "排風機"),
    "PLD": (2, "排風機(直結型)"),
    "CY":  (2, "ｻｲｸﾛﾝ"),
    "CYP": (2, "ｻｲｸﾛﾝ"),
    "CYT": (2, "投入ｻｲｸﾛﾝ"),
    "SCA": (3, "定量排出装置"),
    "SCD": (3, "定量排出装置(小型)"),
    "FS":  (3, "粉砕機/篩"),
    "ASM": (3, "ﾏｸﾞﾈｯﾄｾﾊﾟﾚｰﾀ"),
    "RV":  (3, "ﾛｰﾀﾘｰﾊﾞﾙﾌﾞ"),
    "SD":  (4, "火花探知器"),
    "ADC": (4, "ｵｰﾄﾀﾞﾝﾊﾟ/火の粉遮断弁"),
}
SECTIONS = {
    1: "集塵装置",
    2: "空気輸送装置",
    3: "定量排出装置",
    4: "安全装置:火花探知器 並 火の粉遮断弁",
    5: "制御盤",
    6: "ﾀﾞｸﾄ部品",
}

KW_RE = re.compile(r"([\d.]+)\s?[kK][wW]")
FLOW_RE = re.compile(r"([\d,]+)\s?(?:m3|㎥)/min")
VOL_RE = re.compile(r"([\d,]+)\s?(?:m3|㎥)(?!/)")
DIA_RE = re.compile(r"(?:%%[Cc]|φ|Φ)(\d{2,4})")


def family_of(model):
    m = re.match(r"[A-Z]+", model.upper())
    if not m:
        return None
    head = m.group(0)
    # 長い系列記号を優先(PLD > PL, CYT/CYP > CY, SCA/SCD > SC)
    for k in sorted(FAMILY, key=len, reverse=True):
        if head.startswith(k):
            return k
    return None


def normalize(name):
    """ブロック名から工番プレフィックスとビュー語を除いて型式抽出に備える"""
    s = name
    s = re.sub(r"^\d{6}[A-Z]?[-_]?", "", s)        # 240001A- 等の工番
    for w in PREFIX_WORDS:
        s = s.replace(w, "")
    for w in VIEW_WORDS:
        s = s.replace(w, "")
    return s


def mtext_plain(t):
    """MTEXTの書式コードを除去"""
    t = re.sub(r"\\[A-Za-z][^;]*;", "", t)
    t = t.replace("\\P", "\n").replace("{", "").replace("}", "")
    return t


def extract(path):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    models = collections.Counter()          # 正規化済み型式 → ブロック出現数
    raw_names = collections.Counter()
    texts = []

    panel_blocks = 0
    for e in msp.query("INSERT"):
        raw_names[e.dxf.name] += 1
        # 「SCA30制御盤」等、制御盤ブロックに機器型式が含まれるケースは
        # 機器ではなく制御盤として数える(西北ﾌﾟﾗｲｳｯﾄﾞで実例)
        if "制御盤" in e.dxf.name:
            panel_blocks += 1
            continue
        for m in MODEL_RE.findall(normalize(e.dxf.name)):
            models[m.upper().replace(" ", "").replace("×", "X")] += 1

    for e in msp.query("TEXT MTEXT"):
        t = e.text if e.dxftype() == "MTEXT" else e.dxf.text
        t = mtext_plain(t).strip()
        if t:
            texts.append(t)

    body = "\n".join(texts)
    text_models = collections.Counter(
        m.upper().replace(" ", "").replace("×", "X") for m in MODEL_RE.findall(body)
    )

    specs = {
        "kw": sorted({float(x) for x in KW_RE.findall(body)}),
        "flow_m3min": sorted({int(x.replace(",", "")) for x in FLOW_RE.findall(body)}),
        "dia": collections.Counter(int(x) for x in DIA_RE.findall(body)),
        "panel_texts": [t.replace("\n", " ") for t in texts if "制御盤" in t],
        "panel_blocks": panel_blocks,
    }
    return models, text_models, specs, raw_names


def dedupe(models, text_models):
    """ブロック由来とテキスト由来を統合。同型式の表記揺れ(X/×)は正規化済み"""
    merged = collections.Counter()
    for src in (models, text_models):
        for k in src:
            merged[k] += src[k]
    # BFQ10(ﾌﾞﾛｯｸ名 BFQ10-60 由来)と BFQ10V(ﾃｷｽﾄ由来)のような
    # 「片方がもう片方の前方一致」は長い方(=詳細な型式)へ統合する
    for short in sorted(merged, key=len):
        for long_ in merged:
            if long_ != short and long_.startswith(short) \
                    and family_of(long_) == family_of(short):
                merged[long_] += merged.pop(short)
                break
    # BFR5W6L と BFR5X6 のような別表記は束ねず列挙し、人が確認する
    return merged


def build_skeleton(merged, specs):
    """大項目 → 明細行(3階層 1-1-1 形式)の骨格を組み立てる"""
    sections = collections.defaultdict(list)
    for model, cnt in sorted(merged.items()):
        fam = family_of(model)
        if not fam:
            continue
        sec, label = FAMILY[fam]
        sections[sec].append({"model": model, "label": label, "hits": cnt})

    # 制御盤はテキストまたは制御盤ブロックから
    if specs["panel_texts"] or specs.get("panel_blocks"):
        sections[5].append({
            "model": "", "label": "制御盤",
            "hits": len(specs["panel_texts"]) + specs.get("panel_blocks", 0),
            "note": " / ".join(specs["panel_texts"][:3]),
        })

    # ダクト部品: 径の実績から1行起こす
    if specs["dia"]:
        dia_txt = ",".join(
            f"φ{d}" for d, _ in sorted(specs["dia"].items(), key=lambda x: -x[1])[:6]
        )
        sections[6].append({
            "model": "", "label": "ﾀﾞｸﾄ部品", "hits": sum(specs["dia"].values()),
            "note": f"図面記載径: {dia_txt} (長さは図面から自動算出不可・要手入力)",
        })

    lines = []
    for i, sec in enumerate(sorted(sections), start=1):
        lines.append({"no": str(i), "name": SECTIONS[sec], "level": 1})
        for j, item in enumerate(sections[sec], start=1):
            row = {
                "no": f"{i}-{j}",
                "name": f"{item['label']} 型式:{item['model']}" if item["model"] else item["label"],
                "level": 2,
                "blocks": item["hits"],
            }
            if item.get("note"):
                row["note"] = item["note"]
            lines.append(row)
    return lines


def render_md(path, merged, specs, lines):
    out = [f"# 見積骨格(自動生成ﾄﾞﾗﾌﾄ): {path}", ""]
    out.append("| 番号 | 品名・仕様 | 図面内出現 | 備考 |")
    out.append("|---|---|---|---|")
    for r in lines:
        name = ("**" + r["name"] + "**") if r["level"] == 1 else r["name"]
        out.append(f"| {r['no']} | {name} | {r.get('blocks','')} | {r.get('note','')} |")
    out.append("")
    if specs["kw"]:
        out.append(f"- 図面記載ﾓｰﾀ容量: {', '.join(str(k) for k in specs['kw'])} kW")
    if specs["flow_m3min"]:
        out.append(f"- 図面記載処理風量: {', '.join(str(f) for f in specs['flow_m3min'])} m3/min")
    out.append("- ※単価・数量・ﾀﾞｸﾄ長は自動判定不可。ﾊﾟﾀｰﾝﾏｽﾀ照合と手入力で確定すること")
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        sys.exit(__doc__)
    for path in args:
        models, text_models, specs, raw = extract(path)
        merged = dedupe(models, text_models)
        lines = build_skeleton(merged, specs)
        if as_json:
            print(json.dumps({
                "file": path,
                "models": dict(merged),
                "specs": {k: (dict(v) if isinstance(v, collections.Counter) else v)
                          for k, v in specs.items()},
                "skeleton": lines,
            }, ensure_ascii=False, indent=1))
        else:
            print(render_md(path, merged, specs, lines))
            print()


if __name__ == "__main__":
    main()
