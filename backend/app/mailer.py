# -*- coding: utf-8 -*-
"""メール送信（Gmail SMTP）

■ 設定方法（Renderの Environment に登録する。値はシステム側では扱わない）
    MAIL_FROM          送信元アドレス（例: xxx@gmail.com）
    MAIL_APP_PASSWORD  Googleアカウントの「アプリパスワード」16桁
    MAIL_FROM_NAME     差出人の表示名（省略可。既定「井上電設 販売管理システム」）
    APP_BASE_URL       画面のURL（省略可。例: https://sales-frontend-ybzn.onrender.com）
    API_BASE_URL       APIのURL（省略可。承認リンクに使う）

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

# Google Workspace / Gmail とも smtp.gmail.com:587（STARTTLS）で送信できる。
# 他のメールサービスに変える場合は環境変数で上書きする。
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


def smtp_user() -> str:
    """SMTPのログインID。

    サービスによって「送信元アドレス」とは別の固定IDを使う:
      Google Workspace / Gmail : 送信元アドレスと同じ（SMTP_USER 不要）
      SendGrid                 : apikey
      Resend                   : resend
      Brevo                    : 登録メールアドレス
      Amazon SES               : SMTP認証情報のユーザー名
    未指定なら MAIL_FROM を使う。
    """
    return os.getenv("SMTP_USER") or os.getenv("MAIL_FROM") or ""


def mail_configured() -> bool:
    return bool(os.getenv("MAIL_FROM") and os.getenv("MAIL_APP_PASSWORD"))


def app_base_url() -> str:
    """画面（フロントエンド）のURL"""
    return (os.getenv("APP_BASE_URL") or "https://sales-frontend-ybzn.onrender.com").rstrip("/")


def api_base_url() -> str:
    """APIのURL（承認リンクに使う）。

    ★フロントのURLから機械的に置換して求めてはいけない。
      sales-frontend-ybzn → sales-backend-ybzn となるが、実際の
      バックエンドは sales-backend-7nzg でホスト名が異なる。
    """
    return (os.getenv("API_BASE_URL") or "https://sales-backend-7nzg.onrender.com").rstrip("/") + "/api"


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
            s.login(smtp_user(), os.getenv("MAIL_APP_PASSWORD"))
            s.send_message(msg)
        return {"sent": True, "reason": ""}
    except Exception as e:
        log.warning("メール送信に失敗: %s", e)
        return {"sent": False, "reason": f"送信失敗: {type(e).__name__}: {e}"}
