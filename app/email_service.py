"""
Email sending via Gmail SMTP.
Requires a Gmail App Password (NOT your normal password).
Steps to create one:
  1. Go to https://myaccount.google.com/security
  2. Enable 2-Step Verification (if not already)
  3. Go to "App passwords" (search in Google Account settings)
  4. Generate one for "Mail" / "Other"
  5. Copy the 16-char password into .env as EMAIL_PASSWORD
"""
import os
import smtplib
import secrets
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


def _is_configured() -> bool:
    return bool(EMAIL_ADDRESS and EMAIL_PASSWORD)


def generate_code(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def send_verification_code(to_email: str, code: str, username: str) -> bool:
    if not _is_configured():
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{FROM_NAME} <{EMAIL_ADDRESS}>"
        msg["To"] = to_email
        msg["Subject"] = "Verify your SiteWatch account"

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

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except Exception:
        return False


def send_password_reset_code(to_email: str, code: str, username: str) -> bool:
    if not _is_configured():
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{FROM_NAME} <{EMAIL_ADDRESS}>"
        msg["To"] = to_email
        msg["Subject"] = "Reset your SiteWatch password"

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

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except Exception:
        return False
