# -*- coding: utf-8 -*-
"""HTML帳票をPDFに変換する（メール添付用）

画面の「PDF出力」はHTMLを表示してブラウザで印刷する方式のため、
サーバ側でPDFの実体が必要になるのはメール添付のときだけ。

★WeasyPrintは pango / cairo 等のシステムライブラリを必要とする。
  Renderがネイティブビルド（pip install のみ）の場合は導入されない可能性があるため、
  **import は関数内で遅延実行**し、失敗してもAPI全体が落ちないようにしている。
  使えない場合は html_to_pdf() が None を返すので、呼び出し側でHTML添付などに
  フォールバックすること。
"""
import io
import logging

log = logging.getLogger(__name__)

# 日本語が豆腐（□）にならないよう、帳票HTMLへ差し込むフォント指定。
# Renderのイメージに入っている日本語フォントを優先順に並べる。
_PDF_FONT_CSS = """
<style>
  @page { size: A4; margin: 12mm; }
  body { font-family: "Noto Sans CJK JP","Noto Sans JP","IPAGothic","VL Gothic",
                      "Hiragino Sans","Yu Gothic",sans-serif; }
  .no-print { display: none !important; }
</style>
"""

_unavailable_reason = None   # 一度失敗したら理由を覚えておく（毎回importを試さない）


def pdf_available() -> bool:
    """PDF生成が使えるか（環境にライブラリが揃っているか）"""
    return html_to_pdf("<p>test</p>") is not None


def html_to_pdf(html: str) -> bytes | None:
    """HTML文字列をPDFのbytesにして返す。生成できない環境では None。"""
    global _unavailable_reason
    if _unavailable_reason:
        return None
    try:
        from weasyprint import HTML  # 遅延import（システムライブラリ不足で落ちうる）
    except Exception as e:            # ImportError / OSError(libpango見つからず) 等
        _unavailable_reason = f"{type(e).__name__}: {e}"
        log.warning("PDF生成が使えません（HTMLで代替します）: %s", _unavailable_reason)
        return None

    # <head>があればその中へ、無ければ先頭にフォント指定を差し込む
    if "<head>" in html:
        html = html.replace("<head>", "<head>" + _PDF_FONT_CSS, 1)
    else:
        html = _PDF_FONT_CSS + html
    try:
        buf = io.BytesIO()
        HTML(string=html).write_pdf(buf)
        return buf.getvalue()
    except Exception as e:
        log.warning("PDF変換に失敗しました: %s", e)
        return None
