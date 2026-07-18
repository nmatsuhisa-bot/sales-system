# -*- coding: utf-8 -*-
"""機能権限の定義（User.function_roles）

基本権限（User.role = admin/staff）がシステム管理者かどうかを表すのに対し、
機能権限は「どの業務機能の担当か」を表す。1ユーザーが複数持てる。

■ 機能権限を追加する手順
  1. 下の FUNCTION_ROLES に1件追加する（key は英小文字・スネークケース）
  2. その権限を使う側で `has_role(user, "<key>")` または
     `users_with_role(db, "<key>")` を呼ぶ
  ※ DBのマイグレーションは不要（JSON配列のため）。画面のチェックボックスも
     FUNCTION_ROLES から自動生成されるため、追加作業は上記2点のみ。
"""

FUNCTION_ROLES = [
    {
        "key": "approver",
        "label": "検印承認者",
        "description": "見積の承認依頼を受け取り、検印（承認）できる。見積書の検印欄に表示される",
    },
    # 例）今後の追加はここへ:
    # {"key": "estimate_creator", "label": "見積作成者", "description": "..."},
    # {"key": "purchaser",        "label": "発注担当",   "description": "..."},
]

FUNCTION_ROLE_KEYS = {r["key"] for r in FUNCTION_ROLES}


def normalize_roles(values) -> list:
    """入力された機能権限リストを検証し、定義済みのキーだけを重複なく返す"""
    if not values:
        return []
    if isinstance(values, str):
        values = [values]
    seen, out = set(), []
    for v in values:
        v = (v or "").strip()
        if v in FUNCTION_ROLE_KEYS and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def has_role(user, key: str) -> bool:
    """ユーザーが指定の機能権限を持つか"""
    return key in (getattr(user, "function_roles", None) or [])


def users_with_role(db, key: str):
    """指定の機能権限を持つ有効なユーザーを名前順で返す。

    JSON配列への問い合わせはDB方言に依存するため、ここではPython側で絞り込む
    （ユーザー数は多くても数十件のため実用上問題ない）。
    """
    from app.db.models import User
    users = db.query(User).filter(User.is_active == True).order_by(User.full_name).all()
    return [u for u in users if has_role(u, key)]
