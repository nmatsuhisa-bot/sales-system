# -*- coding: utf-8 -*-
"""HTML帳票をPDFに変換する（メール添付用）

画面の「PDF出力」はHTMLを表示してブラウザで印刷する方式のため、
サーバ側でPDFの実体が必要になるのはメール添付のときだけ。

■ なぜ xhtml2pdf(reportlab) なのか
  当初 WeasyPrint を使ったが、pango/cairo 等のシステムライブラリが必要で、
  Renderのネイティブビルド（pip install のみ、apt不可）では動かなかった。
  xhtml2pdf は **純Python** で追加のシステムライブラリが要らない。

■ 日本語フォント
  reportlab 同梱の CID フォント（HeiseiKakuGo-W5）を使うため、
  **フォントファイルをリポジトリに置く必要がない**。
  これが無いと日本語が全て豆腐（□）になる。

■ 制約
  CSSの対応範囲が狭い（flexbox不可、position:fixed不可）。帳票は表組み中心の
  ためほぼ問題ないが、レイアウトを変えたときはPDFの見た目も確認すること。
"""
import io
import logging
from typing import Optional

log = logging.getLogger(__name__)

_JP_FONT = "HeiseiKakuGo-W5"   # reportlab同梱の日本語CIDフォント
_font_ready = False
_unavailable_reason = None

# 帳票HTMLへ差し込むPDF用のCSS。
# xhtml2pdfはfont-familyを継承しない箇所があるため要素ごとに指定する。
_PDF_CSS = f"""
<style>
  @page {{ size: A4 portrait; margin: 12mm; }}
  /* 帳票の body{{margin:20px}} を打ち消す。余白が残ると本文幅が縮み、
     表の列幅指定が収まらず自動再計算されて列が崩れる */
  body {{ margin: 0; padding: 0; }}
  body, div, p, span, td, th, h1, h2, h3, li, table {{
      font-family: "{_JP_FONT}";
  }}
  .no-print {{ display: none; }}
</style>
"""


def _ensure_font() -> bool:
    """日本語CIDフォントを登録する（初回のみ）"""
    global _font_ready, _unavailable_reason
    if _font_ready:
        return True
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont(_JP_FONT))
        _font_ready = True
        return True
    except Exception as e:
        _unavailable_reason = f"日本語フォント登録に失敗: {type(e).__name__}: {e}"
        log.warning(_unavailable_reason)
        return False


def pdf_available() -> bool:
    """PDF生成が使えるか"""
    return html_to_pdf("<p>テスト</p>") is not None


def html_to_pdf(html: str, watermark: Optional[str] = None,
                stamps: Optional[dict] = None) -> Optional[bytes]:
    """HTML文字列をPDFのbytesにして返す。生成できない環境では None（HTML添付にフォールバック）。

    watermark を指定すると、全ページの中央に斜めの透かしを重ねる
    （xhtml2pdf は transform/position:fixed が使えないため後処理で描く）。
    """
    global _unavailable_reason
    if _unavailable_reason:
        return None
    if not _ensure_font():
        return None
    try:
        from xhtml2pdf import pisa
    except Exception as e:
        _unavailable_reason = f"{type(e).__name__}: {e}"
        log.warning("PDF生成が使えません（HTMLで代替します）: %s", _unavailable_reason)
        return None

    if "</head>" in html:
        html = html.replace("</head>", _PDF_CSS + "</head>", 1)
    elif "<head>" in html:
        html = html.replace("<head>", "<head>" + _PDF_CSS, 1)
    else:
        html = _PDF_CSS + html
    try:
        out = io.BytesIO()
        result = pisa.CreatePDF(io.StringIO(html), dest=out, encoding="utf-8")
        if result.err:
            log.warning("PDF変換でエラー: %s", result.err)
            return None
        data = out.getvalue()
        if not data.startswith(b"%PDF"):
            return None
        if stamps:
            data = _draw_stamps(data, stamps) or data
        if watermark:
            data = _overlay_watermark(data, watermark) or data
        return data
    except Exception as e:
        log.warning("PDF変換に失敗しました: %s", e)
        return None


def _overlay_watermark(pdf_bytes: bytes, text: str) -> Optional[bytes]:
    """全ページの中央に斜めの透かしを重ねる。

    xhtml2pdf は CSS の transform / position:fixed を解釈しないため、
    HTML側では斜めの透かしを描けない。生成後のPDFに reportlab で作った
    透かしページを重ねることで実現する。
    """
    try:
        from reportlab.pdfgen import canvas
        from pypdf import PdfReader, PdfWriter
    except Exception as e:
        log.warning("透かしを重ねられません: %s", e)
        return None
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for page in reader.pages:
            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(w, h))
            c.saveState()
            c.translate(w / 2, h / 2)
            c.rotate(35)
            # 用紙幅に対して大きすぎないよう字数から文字サイズを決める
            size = max(40, min(110, int(w * 0.9 / max(len(text), 1) * 1.6)))
            c.setFont("Helvetica-Bold", size)
            c.setFillColorRGB(0.78, 0.12, 0.12, alpha=0.15)
            c.drawCentredString(0, 0, text)
            c.restoreState()
            c.save()
            mark = PdfReader(io.BytesIO(buf.getvalue())).pages[0]
            page.merge_page(mark)
            writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception as e:
        log.warning("透かしの重ね合わせに失敗: %s", e)
        return None


def merge_pdfs(blobs) -> Optional[bytes]:
    """複数のPDFを1つに結合する（見積書＋社内工数試算を1ファイルで送るため）"""
    blobs = [b for b in blobs if b]
    if not blobs:
        return None
    if len(blobs) == 1:
        return blobs[0]
    try:
        from pypdf import PdfReader, PdfWriter
        writer = PdfWriter()
        for b in blobs:
            for page in PdfReader(io.BytesIO(b)).pages:
                writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception as e:
        log.warning("PDFの結合に失敗: %s", e)
        return None


# 押印（丸印）の描画
# xhtml2pdf は border-radius を解釈しないため丸が描けない。そこでHTML側には
# 位置決め用の見えない目印（ASCII）だけを置き、生成後のPDFに reportlab で
# 朱色の丸と苗字を描く。目印は白文字なので印刷にも出ない。
STAMP_MARKER_PREFIX = "STMP"
# 押印セルの幅(21mm)。目印はセル左端にあるため、この幅の半分だけ右へ寄せて中央に置く
STAMP_CELL_WIDTH = 59.5
# 押印セルの高さ(約33pt)。目印はセル上端にあるため半分下げて中央に置く
STAMP_CELL_HEIGHT = 33.0


def _draw_stamps(pdf_bytes: bytes, stamps: dict) -> Optional[bytes]:
    """{目印キー: 表示名} を受け取り、目印の位置に朱色の丸印を描く。

    例: {"STMPAPV": "井上", "STMPSLS": "柴田", "STMPCRT": "後藤"}
    表示名が空のキーは描画しない（未承認の検印欄など）。
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from pypdf import PdfReader, PdfWriter
    except Exception as e:
        log.warning("押印を描画できません: %s", e)
        return None
    if not _ensure_font():
        return None
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        for page in reader.pages:
            found = {}

            def visit(text, cm, tm, font_dict, font_size, _f=found):
                t = (text or "").strip()
                if t.startswith(STAMP_MARKER_PREFIX) and t in stamps:
                    # 位置 = 現在の変換行列 × テキスト行列
                    _f[t] = (cm[4] + tm[4], cm[5] + tm[5])

            try:
                page.extract_text(visitor_text=visit)
            except Exception:
                pass
            targets = {k: v for k, v in found.items() if (stamps.get(k) or "").strip()}
            if not targets:
                writer.add_page(page)
                continue

            w = float(page.mediabox.width)
            h = float(page.mediabox.height)
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(w, h))
            for key, (x, y) in targets.items():
                name = stamps[key].strip()
                r = 13                              # 丸の半径
                # 目印はセル左上にある。セル幅(21mm)の中央へ寄せ、
                # 縦はセル高(約33pt)の中程へ下ろす。
                # 目印はセル左上（padding 2px）に左寄せで置いてある。
                # そこからセルの中心へ寄せる。
                cx = x + STAMP_CELL_WIDTH / 2 - 3.0
                cy = y + 7.2 - STAMP_CELL_HEIGHT / 2
                c.setStrokeColorRGB(0.80, 0.10, 0.10)
                c.setLineWidth(1.2)
                c.circle(cx, cy, r, stroke=1, fill=0)
                # 苗字は2文字までを想定。文字数で大きさを調整する
                size = 11 if len(name) <= 2 else 8
                c.setFont(_JP_FONT, size)
                c.setFillColorRGB(0.80, 0.10, 0.10)
                c.drawCentredString(cx, cy - size * 0.36, name)
            c.save()
            mark = PdfReader(io.BytesIO(buf.getvalue())).pages[0]
            page.merge_page(mark)
            writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except Exception as e:
        log.warning("押印の描画に失敗: %s", e)
        return None
