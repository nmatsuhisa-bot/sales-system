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
    r"|ES\d+[NP]?"                    # ES450 / ES550N / ES280P（火の粉遮断弁）
    r"|WL\d+"                         # WL8 / WL13（ｳｯﾄﾞｸﾞﾗｲﾝﾀﾞｰ・破砕機）
    r")",
    re.IGNORECASE,
)

# 系列 → (大項目番号, 見積上の品名)。番号は原本見積（新栄合板 26-02-78A・釧路 26-01-01B 他）の並び
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
    # 破砕機は原本見積（釧路 加工棟）で独立した大項目のため、定量排出装置とは分ける
    "WL":  (4, "破砕機(ｳｯﾄﾞｸﾞﾗｲﾝﾀﾞｰ)"),
    "SD":  (5, "火花探知器"),
    "ADC": (5, "ｵｰﾄﾀﾞﾝﾊﾟ/火の粉遮断弁"),
    "ES":  (5, "火の粉遮断弁"),
}
SECTION_NAMES = {
    1: "集塵装置",
    2: "空気輸送装置",
    3: "定量排出装置",
    4: "破砕機",
    5: "安全装置:火花探知器 並 火の粉遮断弁",
    6: "制御盤",
    7: "ﾀﾞｸﾄ部品",
    8: "★要確認（図面から読み取れたが未登録の型式）",
}
SECTION_PANEL = 6      # 制御盤
SECTION_DUCT = 7       # ﾀﾞｸﾄ部品
SECTION_UNKNOWN = 8    # 要確認

# ------------------------------------------------------------------
# 未知の型式の検出（欠落を防ぐための「要確認」行）
# ------------------------------------------------------------------
# 既知の14系列だけを決め打ちで探すと、未登録の製品（例: 火の粉遮断弁ES系列、
# 破砕機WL系列）が無言で見積から欠落する。実案件で実際に発生していたため、
# 「型式らしいがマスタに無いもの」を検出して要確認行として見積に載せる。
UNKNOWN_MODEL_RE = re.compile(r"\b([A-Z]{2,5}-?\d+[A-Z0-9.\-]*)", re.IGNORECASE)
# CADが自動生成する名前・図面管理用の名前は型式ではないので除外する
UNKNOWN_DENY_RE = re.compile(
    r"^(BLOCK|DSC|IMG|DWG|LAYER|LEVEL|SHEET|VIEW|GROUP|XREF|A\$|_)", re.IGNORECASE
)

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


def _scan_dxf(path: str):
    """ASCII DXFを1行ずつ走査して、ENTITIES区の
    INSERTのブロック名（group code 2）と TEXT/MTEXT の文字（group code 1/3）を拾う。

    ezdxf.readfile は図面全体をメモリに構築するため、大きな図面（実例で59MB）では
    サーバのメモリ・実行時間の上限に掛かる。必要なのはブロック名と文字だけなので
    ストリーミングで読む。DXFは「グループコード行 → 値行」の繰り返し。
    """
    # バイナリDXFはこの方式では読めない。CAD側でASCII保存してもらう
    with open(path, "rb") as bf:
        if bf.read(22).startswith(b"AutoCAD Binary DXF"):
            raise ValueError(
                "バイナリDXFには対応していません。AutoCADで「AutoCAD 2018 DXF」"
                "（ASCII形式）として保存し直してください"
            )

    block_names = []
    texts = []
    insunits = None
    acadver = None
    in_entities = False
    section_next = False        # 直前が (0, SECTION) で、次の (2, 名前) が区名
    entity = None               # 現在のエンティティ種別
    pending_header_var = None   # 直前に読んだ (9, $VARNAME)

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        while True:
            code_line = f.readline()
            if not code_line:
                break
            value_line = f.readline()
            if not value_line:
                break
            code = code_line.strip()
            value = value_line.rstrip("\r\n")

            if code == "0":
                v = value.strip()
                if v == "SECTION":
                    section_next = True
                    entity = None
                    continue
                if v == "ENDSEC":
                    in_entities = False
                    entity = None
                    continue
                entity = v
                continue

            if section_next and code == "2":
                in_entities = (value.strip() == "ENTITIES")
                section_next = False
                continue

            # HEADER の $INSUNITS / $ACADVER
            if code == "9":
                pending_header_var = value.strip()
                continue
            if pending_header_var == "$INSUNITS" and code == "70":
                insunits = value.strip()
                pending_header_var = None
                continue
            if pending_header_var == "$ACADVER" and code == "1":
                acadver = value.strip()
                pending_header_var = None
                continue

            if not in_entities:
                continue
            if entity == "INSERT" and code == "2":
                block_names.append(value.strip())
            elif entity in ("TEXT", "MTEXT", "ATTRIB") and code in ("1", "3"):
                texts.append(value)

    return block_names, texts, insunits, acadver


def extract_from_dxf(path: str) -> dict:
    """DXF(ASCII)ファイルを解析して型式・仕様・ダクト径を返す。外部ライブラリ不要。"""
    block_names, raw_texts, insunits, acadver = _scan_dxf(path)
    return analyze(block_names, raw_texts, insunits, acadver)


def _unknown_models_in(raw_name: str, norm_name: str, matched) -> list:
    """ブロック名から「型式らしいが未登録の系列」を拾う。

    機器ブロックは `ES450_平面` `WL13_側面` `ACD450_heimen` のように
    「型式＋区切り＋ビュー名」で命名されている。この形をしていて、かつ
    既知の系列でないものを未登録の型式候補とする。
    CADが自動生成する `BLOCK123` 等は除外する。
    """
    # 機器ブロックの命名規則（区切り記号かビュー語を伴う）でなければ対象外
    looks_like_part = ("_" in raw_name) or any(w in raw_name for w in VIEW_WORDS) \
        or re.search(r"heimen|平面|正面|側面", raw_name, re.IGNORECASE)
    if not looks_like_part:
        return []

    # 既知の型式を含むブロックは、その機器の組立ブロック（付属部品を連結した名前）と
    # みなし、残りのトークンは拾わない。誤検出でノイズになるのを避けるため。
    if matched:
        return []

    # 区切りで分割してから判定する。`_` は正規表現の \b が効かないため、
    # 単純に \b を使うと2番目以降のトークンを取りこぼす。
    out = []
    for chunk in re.split(r"[_\s]+", norm_name):
        m = UNKNOWN_MODEL_RE.match(chunk)
        if not m:
            continue
        t = m.group(1).upper().rstrip("-.")
        if UNKNOWN_DENY_RE.match(t) or family_of(t):
            continue
        out.append(t)
    return out


def analyze(block_names, raw_texts, insunits=None, acadver=None) -> dict:
    """走査済みのブロック名・テキストから見積要素を組み立てる。

    大きな図面はブラウザ側で走査して結果だけ送る（アップロード量を数KBに抑える）ため、
    ファイル読み取りと分析を分離している。
    """
    models = collections.Counter()      # 型式 → 出現数（ブロック＋テキスト）
    unknown = collections.Counter()     # 型式らしいが未登録 → 要確認行にする
    panel_blocks = 0
    for name in block_names:
        # 「SCA30制御盤」等、制御盤ブロックに機器型式が含まれる場合は制御盤として数える
        if "制御盤" in name:
            panel_blocks += 1
            continue
        norm = _normalize_block_name(name)
        found = MODEL_RE.findall(norm)
        for m in found:
            models[_canon(m)] += 1
        for tok in _unknown_models_in(name, norm, found):
            unknown[tok] += 1

    texts = []
    for raw in raw_texts:
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

    # 既知の型式に統合されたもの（BFQ10→BFQ10V 等）は未確認から外す
    known_up = {m.upper() for m in models}
    unknown = {k: v for k, v in unknown.items()
               if not any(k in m or m in k for m in known_up)}

    return {
        "models": dict(models),
        "unknown_models": dict(sorted(unknown.items(), key=lambda x: -x[1])[:20]),
        "panel_blocks": panel_blocks,
        "panel_texts": [t.replace("\n", " ") for t in texts if "制御盤" in t][:5],
        "kw": sorted({float(x) for x in KW_RE.findall(body)}),
        "flow_m3min": sorted({int(x.replace(",", "")) for x in FLOW_RE.findall(body)}),
        "dia": dict(dia),
        "has_existing_note": bool(EXISTING_RE.search(body)),
        "dxf_version": acadver,
        "insunits": insunits,
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
