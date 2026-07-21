import datetime
import ssl
import socket
import httpx
from urllib.parse import urlparse
from ipaddress import ip_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import async_session
from app.models import Site, Check, User


def _is_private_host(hostname: str) -> bool:
    try:
        ip = ip_address(hostname)
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local or ip.is_multicast
    except ValueError:
        pass
    private_suffixes = (
        "localhost", "local", "internal", "intranet", "private",
        "corp", "home", "test", "example", "invalid",
    )
    hostname_lower = hostname.lower()
    for suffix in private_suffixes:
        if hostname_lower == suffix or hostname_lower.endswith("." + suffix):
            return True
    return False


async def check_ssl_expiry(hostname: str, port: int = 443) -> tuple[bool, int | None]:
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=hostname) as s:
            s.settimeout(10)
            s.connect((hostname, port))
            cert = s.getpeercert()
            exp = datetime.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            days_left = (exp - datetime.datetime.utcnow()).days
            return True, days_left
    except Exception:
        return False, None


async def check_site(site: Site, db: AsyncSession) -> Check:
    is_up = False
    status_code = None
    response_ms = None
    ssl_valid = None
    ssl_days = None
    error = None

    was_up_before = None
    last_check_q = (
        select(Check)
        .where(Check.site_id == site.id)
        .order_by(Check.checked_at.desc())
        .limit(1)
    )
    last = (await db.execute(last_check_q)).scalar_one_or_none()
    if last:
        was_up_before = last.is_up

    try:
        parsed = urlparse(site.url)
        hostname = parsed.hostname or ""
        if _is_private_host(hostname):
            error = "Blocked: URL points to a private/internal host"
            check = Check(site_id=site.id, status_code=None, response_ms=None, is_up=False, error_message=error)
            db.add(check)
            await db.commit()
            return check

        async with httpx.AsyncClient(verify=False, timeout=15) as client:
            start = datetime.datetime.utcnow()
            resp = await client.get(site.url, follow_redirects=True)
            elapsed = (datetime.datetime.utcnow() - start).total_seconds() * 1000

            status_code = resp.status_code
            response_ms = round(elapsed, 2)
            is_up = status_code == site.expected_status

            if site.keyword:
                is_up = is_up and site.keyword in resp.text

    except Exception as e:
        error = str(e)[:1000]

    if site.check_ssl:
        try:
            from urllib.parse import urlparse
            hostname = urlparse(site.url).hostname
            ssl_valid, ssl_days = await check_ssl_expiry(hostname)
        except Exception:
            ssl_valid = False

    check = Check(
        site_id=site.id,
        status_code=status_code,
        response_ms=response_ms,
        is_up=is_up,
        ssl_valid=ssl_valid,
        ssl_days_left=ssl_days,
        error_message=error,
    )
    db.add(check)
    await db.commit()

    if was_up_before is not None and was_up_before != is_up:
        try:
            from app.notify import notify_down, notify_up
            user_q = select(User).where(User.id == site.user_id)
            user = (await db.execute(user_q)).scalar_one_or_none()
            if user:
                if is_up:
                    await notify_up(user, site)
                else:
                    await notify_down(user, site)
        except Exception:
            pass

    return check


async def run_checks():
    async with async_session() as db:
        result = await db.execute(select(Site).where(Site.enabled == True))
        sites = result.scalars().all()
        now = datetime.datetime.utcnow()
        for site in sites:
            last_check_q = (
                select(Check)
                .where(Check.site_id == site.id)
                .order_by(Check.checked_at.desc())
                .limit(1)
            )
            last = (await db.execute(last_check_q)).scalar_one_or_none()
            if last:
                elapsed = (now - last.checked_at.replace(tzinfo=None)).total_seconds()
                if elapsed < site.interval_sec:
                    continue
            await check_site(site, db)
