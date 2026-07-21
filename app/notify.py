import os
import httpx

from app.crypto import decrypt_value

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


async def notify_down(user, site):
    message = (
        f"Site is DOWN!\n\n"
        f"<b>{site.name}</b>\n"
        f"URL: {site.url}\n"
        f"Check at: {site.checks[-1].checked_at if site.checks else 'N/A'}"
    )

    if user.notify_telegram and user.telegram_chat_id:
        chat_id = decrypt_value(user.telegram_chat_id)
        if chat_id:
            await send_telegram(chat_id, message)

    if user.notify_email:
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
