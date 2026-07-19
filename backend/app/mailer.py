# -*- coding: utf-8 -*-
"""メール送信（Gmail SMTP）

■ 設定方法（Renderの Environment に登録する。値はシステム側では扱わない）
    MAIL_FROM          送信元アドレス（例: xxx@gmail.com）
    MAIL_APP_PASSWORD  Googleアカウントの「アプリパスワード」16桁
    MAIL_FROM_NAME     差出人の表示名（省略可。既定「井上電設 販売管理システム」）
    APP_BASE_URL       画面のURL（例: https://sales-frontend-ybzn.onrender.com）

■ アプリパスワードの取り方
    Googleアカウント → セキュリティ → 2段階認証を有効化 → アプリパスワード を発行。
    通常のGmailログインパスワードでは送信できない（Googleが拒否する）。

■ 未設定のとき
    送信は行わず「未設定」を返す。承認依頼そのものは成立し、画面の
    「承認待ち」バナーで通知される（メールは補助的な通知手段）。
"""
import os
import smtplib
import logging
from email.message import EmailMessage
from email.utils import formataddr

log = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def mail_configured() -> bool:
    return bool(os.getenv("MAIL_FROM") and os.getenv("MAIL_APP_PASSWORD"))


def app_base_url() -> str:
    return (os.getenv("APP_BASE_URL") or "https://sales-frontend-ybzn.onrender.com").rstrip("/")


def send_mail(to: str, subject: str, body: str, attachments=None) -> dict:
    """メールを送信する。attachments は [(ファイル名, bytes, MIMEサブタイプ)]。

    戻り値: {"sent": bool, "reason": str}
    例外は投げない（メールが送れなくても承認依頼自体は成立させるため）。
    """
    if not mail_configured():
        return {"sent": False, "reason": "メール未設定（MAIL_FROM / MAIL_APP_PASSWORD が未登録）"}
    if not to:
        return {"sent": False, "reason": "宛先メールアドレスが未登録"}

    sender = os.getenv("MAIL_FROM")
    name = os.getenv("MAIL_FROM_NAME") or "井上電設 販売管理システム"
    msg = EmailMessage()
    msg["From"] = formataddr((name, sender))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    for filename, blob, subtype in (attachments or []):
        if not blob:
            continue
        maintype = "application" if subtype in ("pdf", "octet-stream") else "text"
        msg.add_attachment(blob, maintype=maintype, subtype=subtype, filename=filename)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
            s.starttls()
            s.login(sender, os.getenv("MAIL_APP_PASSWORD"))
            s.send_message(msg)
        return {"sent": True, "reason": ""}
    except Exception as e:
        log.warning("メール送信に失敗: %s", e)
        return {"sent": False, "reason": f"送信失敗: {type(e).__name__}: {e}"}
