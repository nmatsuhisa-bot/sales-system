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


def html_to_pdf(html: str, watermark: Optional[str] = None) -> Optional[bytes]:
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
