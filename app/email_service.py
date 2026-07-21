"""
Email sending via SMTP (local) or Resend API (Render/cloud).
Falls back to auto-verify if email is not configured.
"""
import os
import smtplib
import secrets
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path


def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    os.environ.setdefault(key, value)


_load_env()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
FROM_NAME = os.getenv("FROM_NAME", "SiteWatch")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")


def _is_configured() -> bool:
    return bool(EMAIL_ADDRESS and EMAIL_PASSWORD) or bool(RESEND_API_KEY)


def generate_code(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _send_via_resend(to_email: str, subject: str, html: str, text: str) -> bool:
    if not RESEND_API_KEY:
        return False
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={
                "from": f"{FROM_NAME} <onboarding@resend.dev>",
                "to": [to_email],
                "subject": subject,
                "html": html,
                "text": text,
            },
            timeout=15,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _send_via_smtp(to_email: str, subject: str, html: str, text: str) -> bool:
    if not (EMAIL_ADDRESS and EMAIL_PASSWORD):
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{FROM_NAME} <{EMAIL_ADDRESS}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except Exception:
        return False


def _send_email(to_email: str, subject: str, html: str, text: str) -> bool:
    if _send_via_resend(to_email, subject, html, text):
        return True
    if _send_via_smtp(to_email, subject, html, text):
        return True
    return False


def send_verification_code(to_email: str, code: str, username: str) -> bool:
    if not _is_configured():
        return False
    subject = "Verify your SiteWatch account"
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0f172a; padding: 40px; border-radius: 16px;">
        <h1 style="color: #3b82f6; text-align: center; margin: 0;">SiteWatch</h1>
        <p style="color: #94a3b8; text-align: center;">Email Verification</p>
        <div style="background: #1e293b; border-radius: 12px; padding: 30px; text-align: center; margin: 20px 0;">
            <p style="color: #e2e8f0; font-size: 16px;">Hello {username},</p>
            <p style="color: #e2e8f0;">Use this code to verify your email:</p>
            <div style="background: #2563eb; color: white; font-size: 36px; font-weight: bold; letter-spacing: 8px; padding: 16px 32px; border-radius: 8px; margin: 20px 0; display: inline-block;">{code}</div>
            <p style="color: #64748b; font-size: 13px;">This code expires in 15 minutes.</p>
        </div>
        <p style="color: #475569; font-size: 12px; text-align: center;">If you did not create this account, ignore this email.</p>
    </div>
    """
    text = f"Your SiteWatch verification code is: {code}\nThis code expires in 15 minutes."
    return _send_email(to_email, subject, html, text)


def send_password_reset_code(to_email: str, code: str, username: str) -> bool:
    if not _is_configured():
        return False
    subject = "Reset your SiteWatch password"
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0f172a; padding: 40px; border-radius: 16px;">
        <h1 style="color: #3b82f6; text-align: center; margin: 0;">SiteWatch</h1>
        <p style="color: #94a3b8; text-align: center;">Password Reset</p>
        <div style="background: #1e293b; border-radius: 12px; padding: 30px; text-align: center; margin: 20px 0;">
            <p style="color: #e2e8f0; font-size: 16px;">Hello {username},</p>
            <p style="color: #e2e8f0;">Use this code to reset your password:</p>
            <div style="background: #ef4444; color: white; font-size: 36px; font-weight: bold; letter-spacing: 8px; padding: 16px 32px; border-radius: 8px; margin: 20px 0; display: inline-block;">{code}</div>
            <p style="color: #64748b; font-size: 13px;">This code expires in 15 minutes.</p>
        </div>
        <p style="color: #475569; font-size: 12px; text-align: center;">If you did not request this, ignore this email.</p>
    </div>
    """
    text = f"Your SiteWatch password reset code is: {code}\nThis code expires in 15 minutes."
    return _send_email(to_email, subject, html, text)
