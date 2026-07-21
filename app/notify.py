import os
import asyncio
import httpx

from app.crypto import decrypt_value
from app.email_service import _send_email

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


async def send_telegram(chat_id: str, message: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                TELEGRAM_API.format(token=token),
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            )
    except Exception:
        pass


def _send_down_email_sync(email, site_name, site_url, checked_at):
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0f172a; padding: 40px; border-radius: 16px;">
        <h1 style="color: #ef4444; text-align: center; margin: 0;">SiteWatch</h1>
        <p style="color: #94a3b8; text-align: center;">Site Down Alert</p>
        <div style="background: #1e293b; border-radius: 12px; padding: 30px; text-align: center; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">&#128680;</div>
            <p style="color: #ef4444; font-size: 18px; font-weight: bold;">{site_name} is DOWN</p>
            <p style="color: #e2e8f0;">URL: {site_url}</p>
            <p style="color: #64748b; font-size: 13px;">Detected at: {checked_at}</p>
        </div>
        <p style="color: #475569; font-size: 12px; text-align: center;">SiteWatch Monitor</p>
    </div>
    """
    return _send_email(email, "SiteWatch Alert: Site is DOWN", html, f"{site_name} is DOWN! URL: {site_url}")


def _send_up_email_sync(email, site_name, site_url):
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0f172a; padding: 40px; border-radius: 16px;">
        <h1 style="color: #22c55e; text-align: center; margin: 0;">SiteWatch</h1>
        <p style="color: #94a3b8; text-align: center;">Site Back Online</p>
        <div style="background: #1e293b; border-radius: 12px; padding: 30px; text-align: center; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">&#9989;</div>
            <p style="color: #22c55e; font-size: 18px; font-weight: bold;">{site_name} is back UP</p>
            <p style="color: #e2e8f0;">URL: {site_url}</p>
        </div>
        <p style="color: #475569; font-size: 12px; text-align: center;">SiteWatch Monitor</p>
    </div>
    """
    return _send_email(email, "SiteWatch: Site is back UP", html, f"{site_name} is back UP! URL: {site_url}")


async def notify_down(user, site, last_check):
    checked_at = last_check.checked_at.strftime("%Y-%m-%d %H:%M:%S") if last_check else "N/A"
    message = (
        f"Site is DOWN!\n\n"
        f"<b>{site.name}</b>\n"
        f"URL: {site.url}\n"
        f"Check at: {checked_at}"
    )

    if user.notify_telegram and user.telegram_chat_id:
        chat_id = decrypt_value(user.telegram_chat_id)
        if chat_id:
            await send_telegram(chat_id, message)

    if user.notify_email and user.email:
        try:
            await asyncio.to_thread(_send_down_email_sync, user.email, site.name, site.url, checked_at)
        except Exception:
            pass


async def notify_up(user, site):
    message = (
        f"Site is back UP!\n\n"
        f"<b>{site.name}</b>\n"
        f"URL: {site.url}"
    )

    if user.notify_telegram and user.telegram_chat_id:
        chat_id = decrypt_value(user.telegram_chat_id)
        if chat_id:
            await send_telegram(chat_id, message)

    if user.notify_email and user.email:
        try:
            await asyncio.to_thread(_send_up_email_sync, user.email, site.name, site.url)
        except Exception:
            pass
