"""テキスト正規化（半角/全角統一）

社内標準: NFKC正規化（全角英数記号→半角、半角カナ→全角）。
案件名・顧客名等の保存時に適用し、表記ゆれによる検索漏れ・重複を防ぐ。
"""
import unicodedata


def nfkc(v):
    """文字列をNFKC正規化。文字列以外（日付・数値・None等）はそのまま返す。"""
    return unicodedata.normalize("NFKC", v) if isinstance(v, str) else v


def nfkc_fields(d: dict, exclude=frozenset()) -> dict:
    """dict内の文字列値をNFKC正規化（excludeキーは除外）。"""
    return {k: (v if k in exclude else nfkc(v)) for k, v in d.items()}
