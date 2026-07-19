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


def html_to_pdf(html: str) -> Optional[bytes]:
    """HTML文字列をPDFのbytesにして返す。生成できない環境では None（HTML添付にフォールバック）。"""
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

    if "<head>" in html:
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
        return data if data.startswith(b"%PDF") else None
    except Exception as e:
        log.warning("PDF変換に失敗しました: %s", e)
        return None
