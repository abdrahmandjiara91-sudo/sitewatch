import os
import asyncio
import httpx
import json

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


async def send_slack(webhook_url: str, text: str):
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json={"text": text})
    except Exception:
        pass


async def send_discord(webhook_url: str, content: str):
    if not webhook_url:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(webhook_url, json={"content": content})
    except Exception:
        pass


async def send_custom_webhooks(urls: list[str], payload: dict):
    if not urls:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        for url in urls:
            url = url.strip()
            if not url:
                continue
            try:
                await client.post(url, json=payload)
            except Exception:
                pass


def _send_email_sync(email, subject, html, plain=""):
    return _send_email(email, subject, html, plain)


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


def _send_slow_email_sync(email, site_name, site_url, response_ms, threshold):
    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 480px; margin: 0 auto; background: #0f172a; padding: 40px; border-radius: 16px;">
        <h1 style="color: #facc15; text-align: center; margin: 0;">SiteWatch</h1>
        <p style="color: #94a3b8; text-align: center;">Slow Response Alert</p>
        <div style="background: #1e293b; border-radius: 12px; padding: 30px; text-align: center; margin: 20px 0;">
            <div style="font-size: 3rem; margin-bottom: 1rem;">&#128553;</div>
            <p style="color: #facc15; font-size: 18px; font-weight: bold;">{site_name} is slow!</p>
            <p style="color: #e2e8f0;">URL: {site_url}</p>
            <p style="color: #facc15; font-size: 24px; font-weight: bold;">{response_ms}ms</p>
            <p style="color: #64748b; font-size: 13px;">Threshold: {threshold}ms</p>
        </div>
        <p style="color: #475569; font-size: 12px; text-align: center;">SiteWatch Monitor</p>
    </div>
    """
    return _send_email(email, f"SiteWatch: {site_name} is slow ({response_ms}ms)", html, f"{site_name} is slow! Response: {response_ms}ms")


def _send_monthly_report_email_sync(email, username, stats):
    sites_html = ""
    for s in stats["sites"]:
        color = "#22c55e" if s["uptime"] >= 99 else ("#eab308" if s["uptime"] >= 95 else "#ef4444")
        sites_html += f"""
        <tr>
            <td style="padding:8px; border-bottom:1px solid #334155; color:#e2e8f0;">{s['name']}</td>
            <td style="padding:8px; border-bottom:1px solid #334155; color:{color}; font-weight:600;">{s['uptime']}%</td>
            <td style="padding:8px; border-bottom:1px solid #334155; color:#94a3b8;">{s['avg_response']}ms</td>
            <td style="padding:8px; border-bottom:1px solid #334155; color:#94a3b8;">{s['total_checks']}</td>
        </tr>"""

    html = f"""
    <div style="font-family: 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; background: #0f172a; padding: 40px; border-radius: 16px;">
        <h1 style="color: #38bdf8; text-align: center; margin: 0;">SiteWatch</h1>
        <p style="color: #94a3b8; text-align: center;">Monthly Uptime Report - {stats['month']}</p>
        <div style="background: #1e293b; border-radius: 12px; padding: 20px; margin: 20px 0;">
            <div style="display: flex; justify-content: space-around; text-align: center; margin-bottom: 20px;">
                <div><div style="font-size: 2rem; font-weight: 700; color: #38bdf8;">{stats['total_sites']}</div><div style="font-size: 0.8rem; color: #64748b;">Sites</div></div>
                <div><div style="font-size: 2rem; font-weight: 700; color: #22c55e;">{stats['overall_uptime']}%</div><div style="font-size: 0.8rem; color: #64748b;">Uptime</div></div>
                <div><div style="font-size: 2rem; font-weight: 700; color: #facc15;">{stats['total_checks']}</div><div style="font-size: 0.8rem; color: #64748b;">Checks</div></div>
            </div>
            <table style="width:100%; border-collapse:collapse; font-size:0.85rem;">
                <tr style="border-bottom:2px solid #334155;">
                    <th style="padding:8px; text-align:left; color:#64748b;">Site</th>
                    <th style="padding:8px; text-align:left; color:#64748b;">Uptime</th>
                    <th style="padding:8px; text-align:left; color:#64748b;">Avg Response</th>
                    <th style="padding:8px; text-align:left; color:#64748b;">Checks</th>
                </tr>
                {sites_html}
            </table>
        </div>
        <p style="color: #475569; font-size: 12px; text-align: center;">SiteWatch Monitor</p>
    </div>
    """
    return _send_email(email, f"SiteWatch Monthly Report - {stats['month']}", html, f"Monthly report: {stats['total_sites']} sites, {stats['overall_uptime']}% uptime")


async def _notify_all_channels(user, site, message, plain_msg, event_type="custom"):
    if user.notify_telegram and user.telegram_chat_id:
        chat_id = decrypt_value(user.telegram_chat_id)
        if chat_id:
            await send_telegram(chat_id, message)

    if user.notify_email and user.email:
        try:
            await asyncio.to_thread(_send_email_sync, user.email, f"SiteWatch: {site.name} - {event_type}", f"<p>{plain_msg}</p>", plain_msg)
        except Exception:
            pass

    user_slack = user.notify_slack and user.slack_webhook_url
    site_slack = site.notify_slack and site.slack_webhook_url
    if user_slack or site_slack:
        urls = []
        if user_slack:
            urls.append(user.slack_webhook_url)
        if site_slack:
            urls.append(site.slack_webhook_url)
        for url in urls:
            await send_slack(url, plain_msg)

    user_discord = user.notify_discord and user.discord_webhook_url
    site_discord = site.notify_discord and site.discord_webhook_url
    if user_discord or site_discord:
        urls = []
        if user_discord:
            urls.append(user.discord_webhook_url)
        if site_discord:
            urls.append(site.discord_webhook_url)
        for url in urls:
            await send_discord(url, plain_msg)

    all_webhooks = []
    if user.custom_webhooks:
        all_webhooks.extend([u.strip() for u in user.custom_webhooks.strip().splitlines() if u.strip()])
    if site.custom_webhooks:
        all_webhooks.extend([u.strip() for u in site.custom_webhooks.strip().splitlines() if u.strip()])
    if all_webhooks:
        payload = {"event": event_type, "site": site.name, "url": site.url}
        await send_custom_webhooks(all_webhooks, payload)


async def notify_down(user, site, last_check):
    checked_at = last_check.checked_at.strftime("%Y-%m-%d %H:%M:%S") if last_check else "N/A"
    message = (
        f"Site is DOWN!\n\n"
        f"<b>{site.name}</b>\n"
        f"URL: {site.url}\n"
        f"Check at: {checked_at}"
    )
    plain_msg = f"Site is DOWN!\n{site.name}\nURL: {site.url}\nCheck at: {checked_at}"

    await _notify_all_channels(user, site, message, plain_msg, "down")

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
    plain_msg = f"Site is back UP!\n{site.name}\nURL: {site.url}"

    await _notify_all_channels(user, site, message, plain_msg, "up")

    if user.notify_email and user.email:
        try:
            await asyncio.to_thread(_send_up_email_sync, user.email, site.name, site.url)
        except Exception:
            pass


async def notify_slow(user, site, response_ms):
    message = (
        f"Slow response detected!\n\n"
        f"<b>{site.name}</b>\n"
        f"URL: {site.url}\n"
        f"Response: {response_ms}ms\n"
        f"Threshold: {user.slow_threshold_ms}ms"
    )
    plain_msg = f"Slow response!\n{site.name}\nURL: {site.url}\nResponse: {response_ms}ms (threshold: {user.slow_threshold_ms}ms)"

    await _notify_all_channels(user, site, message, plain_msg, "slow")

    if user.notify_email and user.email:
        try:
            await asyncio.to_thread(_send_slow_email_sync, user.email, site.name, site.url, response_ms, user.slow_threshold_ms)
        except Exception:
            pass


async def send_monthly_report(user, stats):
    if not user.notify_email or not user.email:
        return
    try:
        await asyncio.to_thread(_send_monthly_report_email_sync, user.email, user.username, stats)
    except Exception:
        pass
