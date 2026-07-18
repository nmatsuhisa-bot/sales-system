# -*- coding: utf-8 -*-
"""CAD図面(DXF)から見積要素を抽出する（会議2026-07-17「図面からの見積自動化」STEP2）

図面のブロック名・テキストに自社製品の型式が入っていることを、実案件6図面
（本多木工所/西北プライウッド/川井林業/新栄合板/釧路ウッドプロダクツA・B）の
解析で確認済み。ここではその抽出ルールを実装する。

取得できるもの: 型式・台数・モータ容量・処理風量・ダクト径
取得できないもの: ダクト長（輪郭2本の平行線で描かれ建屋の線と区別できないため）
                 → ダクトは概算とし、下記 DUCT_* の係数で見積る
"""
import re
import collections

# ------------------------------------------------------------------
# ダクト概算のパラメータ（★仮値・要 井上電設確認）
# ------------------------------------------------------------------
# 図面からダクトの実長は取得できないため、径ごとに「単価/m × 想定延長」で概算する。
# 想定延長は「図面上の径注記1件あたりの標準的な配管長」。
# 作図標準（ダクトを専用レイヤーに中心線1本で作図）が導入されれば実長に置換できる。
DUCT_RATE_PER_MM_M = 20      # 単価 = 径(mm) × この係数 (円/m)。φ375なら7,500円/m
DUCT_DEFAULT_RUN_M = 6       # 径注記1件あたりの想定延長(m)
DUCT_MIN_DIA = 75            # これ未満の径はダクトとみなさない（機器の穴径等を除外）
DUCT_MAX_DIA = 1500          # これを超える径はダクトとみなさない

# ------------------------------------------------------------------
# 型式の抽出定義
# ------------------------------------------------------------------
# ブロック名から取り除く修飾語（ビュー名・状態語）
VIEW_WORDS = (
    "平面", "正面", "側面L", "側面R", "側面", "裏面", "左側面", "右側面", "立面",
    "天井", "基礎", "上", "下", "中断ｽﾃｰｼﾞ", "中段", "踊り場", "本体略図", "略図",
    "ｼｭｰﾄ", "ﾌﾗﾝｼﾞ", "ﾓｰﾀｰｶﾊﾞｰ付", "モーターカバー付", "受",
)
PREFIX_WORDS = ("単色", "消火配管_", "消火配管")

MODEL_RE = re.compile(
    r"(BFR\s?\d+[WX×]?\s?\d*L?"      # BFR3X5 / BFR5W6L / BFR3×6
    r"|BFQ\d+[VW]?"                   # BFQ7 / BFQ10V
    r"|SCA\d+"                        # SCA675 / SCA844
    r"|SCD\d+"                        # SCD5
    r"|ADC\d+N?"                      # ADC550 / ADC600N
    r"|RV\d+[X×]\d+"                 # RV25X60 / RV30×80
    r"|CY[PT]?\d+[ES]?"              # CY600 / CYP600 / CYT750 / CY950
    r"|PLD[\d.]+"                     # PLD2.2 / PLD7.5
    r"|PL\d+"                         # PL200 / PL4000
    r"|FS\d+"                         # FS25
    r"|ASM\d+"                        # ASM300
    r"|SD-?\d+E?"                     # SD-4E / SD-2E
    r")",
    re.IGNORECASE,
)

# 系列 → (大項目番号, 見積上の品名)。番号は原本見積（新栄合板 26-02-78A 他）の並び
FAMILY = {
    "BFR": (1, "ﾊﾞｸﾞﾌｨﾙﾀｰ集塵機"),
    "BFQ": (1, "小型ﾊﾞｸﾞﾌｨﾙﾀｰ集塵機"),
    "PLD": (2, "排風機(直結型)"),
    "PL":  (2, "排風機"),
    "CYT": (2, "投入ｻｲｸﾛﾝ"),
    "CYP": (2, "ｻｲｸﾛﾝ"),
    "CY":  (2, "ｻｲｸﾛﾝ"),
    "SCA": (3, "定量排出装置"),
    "SCD": (3, "定量排出装置(小型)"),
    "FS":  (3, "粉砕機"),
    "ASM": (3, "ﾏｸﾞﾈｯﾄｾﾊﾟﾚｰﾀ"),
    "RV":  (3, "ﾛｰﾀﾘｰﾊﾞﾙﾌﾞ"),
    "SD":  (4, "火花探知器"),
    "ADC": (4, "ｵｰﾄﾀﾞﾝﾊﾟ/火の粉遮断弁"),
}
SECTION_NAMES = {
    1: "集塵装置",
    2: "空気輸送装置",
    3: "定量排出装置",
    4: "安全装置:火花探知器 並 火の粉遮断弁",
    5: "制御盤",
    6: "ﾀﾞｸﾄ部品",
}

KW_RE = re.compile(r"([\d.]+)\s?[kK][wW]")
FLOW_RE = re.compile(r"([\d,]+)\s?(?:m3|㎥)/min")
DIA_RE = re.compile(r"(?:%%[Cc]|φ|Φ)(\d{2,4})")
EXISTING_RE = re.compile(r"既設")


def family_of(model: str):
    """型式の系列記号を返す（PLD>PL, CYT/CYP>CY, SCA/SCD>SC のように長い方を優先）"""
    m = re.match(r"[A-Z]+", model.upper())
    if not m:
        return None
    head = m.group(0)
    for k in sorted(FAMILY, key=len, reverse=True):
        if head.startswith(k):
            return k
    return None


def _normalize_block_name(name: str) -> str:
    """ブロック名から工番プレフィックス・ビュー語を除いて型式抽出に備える"""
    s = re.sub(r"^\d{6}[A-Z]?[-_]?", "", name)   # 240001A- 等の工番
    for w in PREFIX_WORDS:
        s = s.replace(w, "")
    for w in VIEW_WORDS:
        s = s.replace(w, "")
    return s


def _mtext_plain(t: str) -> str:
    """MTEXTの書式コードを除去"""
    t = re.sub(r"\\[A-Za-z][^;]*;", "", t)
    return t.replace("\\P", "\n").replace("{", "").replace("}", "")


def _canon(model: str) -> str:
    return model.upper().replace(" ", "").replace("×", "X")


def extract_from_dxf(path: str) -> dict:
    """DXFを解析して型式・仕様・ダクト径を返す。ezdxf が必要。"""
    import ezdxf
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()

    models = collections.Counter()      # 型式 → 出現数（ブロック＋テキスト）
    panel_blocks = 0
    texts = []

    for e in msp.query("INSERT"):
        name = e.dxf.name
        # 「SCA30制御盤」等、制御盤ブロックに機器型式が含まれる場合は制御盤として数える
        if "制御盤" in name:
            panel_blocks += 1
            continue
        for m in MODEL_RE.findall(_normalize_block_name(name)):
            models[_canon(m)] += 1

    for e in msp.query("TEXT MTEXT"):
        raw = e.text if e.dxftype() == "MTEXT" else e.dxf.text
        t = _mtext_plain(raw).strip()
        if t:
            texts.append(t)

    body = "\n".join(texts)
    for m in MODEL_RE.findall(body):
        models[_canon(m)] += 1

    # 「BFQ10（ブロック名 BFQ10-60 由来）」と「BFQ10V（テキスト由来）」のように
    # 片方が前方一致する場合は、詳細な方（長い方）へ統合する
    for short in sorted(list(models), key=len):
        if short not in models:
            continue
        for long_ in list(models):
            if long_ != short and long_.startswith(short) and family_of(long_) == family_of(short):
                models[long_] += models.pop(short)
                break

    # ダクト径（φ表記）。機器の穴径等を除くため範囲で絞る
    dia = collections.Counter()
    for a, b, c in re.findall(r"%%[Cc](\d{2,4})|φ(\d{2,4})|Φ(\d{2,4})", body):
        v = int(a or b or c)
        if DUCT_MIN_DIA <= v <= DUCT_MAX_DIA:
            dia[v] += 1

    return {
        "models": dict(models),
        "panel_blocks": panel_blocks,
        "panel_texts": [t.replace("\n", " ") for t in texts if "制御盤" in t][:5],
        "kw": sorted({float(x) for x in KW_RE.findall(body)}),
        "flow_m3min": sorted({int(x.replace(",", "")) for x in FLOW_RE.findall(body)}),
        "dia": dict(dia),
        "has_existing_note": bool(EXISTING_RE.search(body)),
        "dxf_version": doc.dxfversion,
        "insunits": doc.header.get("$INSUNITS"),
    }


def duct_estimate(dia: dict) -> dict:
    """ダクトの概算。図面から実長が取れないため
    「径 × 係数 × 想定延長 × 注記数」で算出する（★仮値）。"""
    lines = []
    total = 0
    for d, cnt in sorted(dia.items(), key=lambda x: -x[0]):
        run_m = cnt * DUCT_DEFAULT_RUN_M
        rate = d * DUCT_RATE_PER_MM_M
        amt = rate * run_m
        total += amt
        lines.append({"dia": d, "count": cnt, "run_m": run_m, "rate_per_m": rate, "amount": amt})
    # 概算は千円単位で丸める
    total = int(round(total, -3))
    return {"lines": lines, "total": total}
