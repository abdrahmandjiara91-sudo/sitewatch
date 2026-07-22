from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Form, Request, Header
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc, delete, update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.staticfiles import StaticFiles
import csv
import io
import os
import re
import secrets
import hashlib
import hmac
import asyncio
import datetime

from app.database import init_db, async_session, engine, DATABASE_URL
from app.models import User, Site, Check, PLANS, ApiKey, VerificationToken, PasswordResetToken, RevokedToken, Review, BlogPost
from app.auth import hash_password, verify_password, create_token, get_current_user, require_auth
from app.monitor import run_checks, check_site, _is_private_host
from app.csrf import get_or_create_csrf_session_id, set_csrf_cookie_if_new, generate_csrf_token, verify_csrf
from app.crypto import encrypt_value, decrypt_value
from app.email_service import send_verification_code, send_password_reset_code, generate_code, _is_configured
from app.translations import get_translations

_utcnow = lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

limiter = Limiter(key_func=_get_client_ip)

scheduler = AsyncIOScheduler()


async def _cleanup_revoked_tokens():
    async with async_session() as db:
        cutoff = _utcnow() - datetime.timedelta(days=31)
        await db.execute(delete(RevokedToken).where(RevokedToken.revoked_at < cutoff))
        await db.commit()


async def _reset_daily_api_counters():
    async with async_session() as db:
        await db.execute(update(ApiKey).values(requests_today=0))
        await db.commit()


async def _monthly_uptime_report():
    try:
        from app.notify import send_monthly_report
        now = _utcnow()
        month_str = now.strftime("%B %Y")
        async with async_session() as db:
            users = (await db.execute(select(User).where(User.notify_email == True, User.is_verified == True))).scalars().all()
            for user in users:
                sites = (await db.execute(select(Site).where(Site.user_id == user.id))).scalars().all()
                site_stats = []
                total_checks = 0
                all_up_count = 0
                total_response = 0.0
                response_count = 0
                for site in sites:
                    site_total = (await db.execute(select(func.count(Check.id)).where(Check.site_id == site.id))).scalar() or 0
                    site_up = (await db.execute(select(func.count(Check.id)).where(Check.site_id == site.id, Check.is_up == True))).scalar() or 0
                    uptime = round((site_up / site_total * 100) if site_total > 0 else 0, 1)
                    avg_resp_q = select(func.avg(Check.response_ms)).where(Check.site_id == site.id, Check.is_up == True)
                    avg_resp = (await db.execute(avg_resp_q)).scalar()
                    avg_resp = round(avg_resp, 1) if avg_resp else 0
                    total_checks += site_total
                    all_up_count += site_up
                    if avg_resp > 0:
                        total_response += avg_resp
                        response_count += 1
                    site_stats.append({"name": site.name, "uptime": uptime, "avg_response": avg_resp, "total_checks": site_total})
                overall_uptime = round(all_up_count / total_checks * 100, 1) if total_checks > 0 else 0
                stats = {
                    "month": month_str,
                    "total_sites": len(sites),
                    "overall_uptime": overall_uptime,
                    "total_checks": total_checks,
                    "sites": site_stats,
                }
                await send_monthly_report(user, stats)
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.add_job(run_checks, "interval", seconds=60, id="monitor")
    scheduler.add_job(_cleanup_revoked_tokens, "interval", days=1, id="cleanup_tokens")
    scheduler.add_job(_reset_daily_api_counters, "cron", hour=0, minute=0, id="reset_api_counters")
    scheduler.add_job(_monthly_uptime_report, "cron", day=1, hour=8, minute=0, id="monthly_report")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Website Monitor", lifespan=lifespan)
app.state.limiter = limiter
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}



@app.get("/status/{username}", response_class=HTMLResponse)
async def public_status_page(request: Request, username: str):
    from fastapi.responses import HTMLResponse as HTMLResp
    async with async_session() as db:
        user_result = await db.execute(select(User).where(User.username == username))
        display_user = user_result.scalar_one_or_none()
        if not display_user:
            return HTMLResponse("<h1>User not found</h1>", status_code=404)

        result = await db.execute(
            select(Site).where(Site.user_id == display_user.id, Site.enabled == True).order_by(Site.id)
        )
        sites = result.scalars().all()

        site_data = []
        all_up = True
        for site in sites:
            last_check_q = (
                select(Check).where(Check.site_id == site.id)
                .order_by(desc(Check.checked_at)).limit(1)
            )
            last = (await db.execute(last_check_q)).scalar_one_or_none()

            total_q = select(func.count(Check.id)).where(Check.site_id == site.id)
            total = (await db.execute(total_q)).scalar() or 0
            up_q = select(func.count(Check.id)).where(Check.site_id == site.id, Check.is_up == True)
            up_count = (await db.execute(up_q)).scalar() or 0
            uptime = round((up_count / total * 100) if total > 0 else 0, 1)

            if last:
                is_up = last.is_up
                status_class = "up" if is_up else "down"
                last_checked_str = last.checked_at.strftime("%Y-%m-%d %H:%M UTC")
            else:
                status_class = "pending"
                last_checked_str = ""

            if not (last and last.is_up) and last:
                all_up = False

            if uptime >= 99:
                uptime_class = "good"
            elif uptime >= 90:
                uptime_class = "warn"
            else:
                uptime_class = "bad"

            site_data.append({
                "site": site,
                "last_check": last,
                "status_class": status_class,
                "uptime": uptime,
                "uptime_class": uptime_class,
                "last_checked_str": last_checked_str,
            })

    lang = request.cookies.get("lang", "en")
    t = get_translations(lang)

    return templates.TemplateResponse(request, "status.html", {
        "display_user": display_user.username,
        "sites": site_data,
        "all_up": all_up,
        "t": t,
    })


@app.get("/badge/{site_id}.svg")
async def badge_svg(site_id: int):
    from fastapi.responses import Response
    async with async_session() as db:
        site = await db.get(Site, site_id)
        if not site:
            return Response(content='<svg xmlns="http://www.w3.org/2000/svg" width="110" height="20"><text x="5" y="14" font-family="sans-serif" font-size="11" fill="#94a3b8">not found</text></svg>', media_type="image/svg+xml")

        last_check_q = (
            select(Check).where(Check.site_id == site.id)
            .order_by(desc(Check.checked_at)).limit(1)
        )
        last = (await db.execute(last_check_q)).scalar_one_or_none()

        total_q = select(func.count(Check.id)).where(Check.site_id == site.id)
        total = (await db.execute(total_q)).scalar() or 0
        up_q = select(func.count(Check.id)).where(Check.site_id == site.id, Check.is_up == True)
        up_count = (await db.execute(up_q)).scalar() or 0
        uptime = round((up_count / total * 100) if total > 0 else 0, 1)

        if last and last.is_up:
            color = "#4ade80"
            label = "up"
        elif last:
            color = "#f87171"
            label = "down"
        else:
            color = "#facc15"
            label = "pending"

        badge_text = f"{uptime}% uptime"

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="130" height="20" role="img" aria-label="uptime: {badge_text}">
  <title>uptime: {badge_text}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="130" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="65" height="20" fill="{color}"/>
    <rect x="65" width="65" height="20" fill="{color}" fill-opacity=".4"/>
    <rect width="130" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">
    <text x="33" y="15" fill="#010101" fill-opacity=".3">uptime</text>
    <text x="33" y="14">uptime</text>
    <text x="98" y="15" fill="#010101" fill-opacity=".3">{badge_text}</text>
    <text x="98" y="14">{badge_text}</text>
  </g>
</svg>'''
    return Response(content=svg, media_type="image/svg+xml")


@app.post("/settings/language")
async def update_language(
    request: Request,
    language: str = Form("en"),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    async with async_session() as db:
        u = await db.get(User, user.id)
        u.language = language
        await db.commit()
    response = RedirectResponse("/settings?message=Language+saved!", status_code=303)
    response.set_cookie("lang", language, max_age=365 * 86400)
    return response


def render(request: Request, name: str, context: dict, status_code: int = 200):
    """Renders a template and, if it contains a form, transparently attaches
    a valid CSRF token + cookie. Use this instead of templates.TemplateResponse
    for any page with a <form>."""
    session_id, is_new = get_or_create_csrf_session_id(request)
    lang = request.cookies.get("lang", "en")
    t = get_translations(lang)
    context = {**context, "csrf_token": generate_csrf_token(session_id), "t": t}
    response = templates.TemplateResponse(request, name, context, status_code=status_code)
    set_csrf_cookie_if_new(response, session_id, is_new)
    return response


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"error": "Too many requests. Slow down."},
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return RedirectResponse("/landing", status_code=302)


@app.get("/landing", response_class=HTMLResponse)
async def landing_page(request: Request):
    user = await get_current_user(request)
    lang = request.cookies.get("lang", "en")
    t = get_translations(lang)
    async with async_session() as db:
        reviews = (await db.execute(
            select(Review).where(Review.is_approved == True).order_by(Review.created_at.desc()).limit(6)
        )).scalars().all()
    return render(request, "landing.html", {"user": user, "t": t, "reviews": reviews})


SAFE_ERRORS = {
    "Invalid email or password",
    "Account not verified. Please check your email.",
    "Password reset successful. Please sign in.",
    "Session expired. Please log in again.",
    "Please log in to continue.",
}

@app.get("/login", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def login_page(request: Request, error: str = ""):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    safe_error = error if error in SAFE_ERRORS else ""
    return render(request, "login.html", {"error": safe_error})


@app.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    _: bool = Depends(verify_csrf),
):
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            return render(
                request, "login.html", {"error": "Invalid email or password"}
            )

        if not user.is_verified and _is_configured():
            try:
                code = generate_code()
                expires = _utcnow() + datetime.timedelta(minutes=15)
                async with async_session() as vdb:
                    vt = VerificationToken(user_id=user.id, code=code, purpose="verify", expires_at=expires)
                    vdb.add(vt)
                    await vdb.commit()
                    try:
                        await asyncio.wait_for(
                            asyncio.to_thread(send_verification_code, user.email, code, user.username),
                            timeout=8,
                        )
                    except (asyncio.TimeoutError, Exception):
                        pass
            except Exception:
                pass
            token = create_token(user.id)
            response = RedirectResponse("/verify-email?msg=ok", status_code=303)
            response.set_cookie("token", token, httponly=True, secure=True, samesite="lax", max_age=30 * 86400)
            return response

    token = create_token(user.id)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("token", token, httponly=True, secure=True, samesite="lax", max_age=30 * 86400)
    return response


@app.get("/register", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def register_page(request: Request, error: str = ""):
    user = await get_current_user(request)
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return render(request, "register.html", {"error": error})


@app.post("/register")
@limiter.limit("5/minute")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    _: bool = Depends(verify_csrf),
):
    username = username.strip()
    if len(username) < 3 or len(username) > 30:
        return render(request, "register.html", {"error": "Username must be 3-30 characters"})
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return render(request, "register.html", {"error": "Username may only contain letters, numbers, and underscores"})
    if len(email) > 200:
        return render(request, "register.html", {"error": "Email too long"})
    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        return render(request, "register.html", {"error": "Invalid email address"})

    if password != confirm_password:
        return render(request, "register.html", {"error": "Passwords do not match"})

    if len(password) < 8:
        return render(request, "register.html", {"error": "Password must be at least 8 characters"})
    if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'[0-9]', password):
        return render(request, "register.html", {"error": "Password must contain uppercase, lowercase, and a number"})

    async with async_session() as db:
        exists = await db.execute(
            select(User).where((User.email == email) | (User.username == username))
        )
        if exists.scalar_one_or_none():
            return render(
                request, "register.html", {"error": "Email or username already exists"}
            )

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            plan="free",
        )
        db.add(user)
        await db.commit()

        if _is_configured():
            code = generate_code()
            expires = _utcnow() + datetime.timedelta(minutes=15)
            vt = VerificationToken(user_id=user.id, code=code, purpose="verify", expires_at=expires)
            db.add(vt)
            await db.commit()
            token = create_token(user.id)
            try:
                email_sent = await asyncio.wait_for(
                    asyncio.to_thread(send_verification_code, email, code, username),
                    timeout=8,
                )
            except (asyncio.TimeoutError, Exception):
                email_sent = False
            if email_sent:
                response = RedirectResponse("/verify-email?msg=ok", status_code=303)
                response.set_cookie("token", token, httponly=True, secure=True, samesite="lax", max_age=30 * 86400)
                return response
            else:
                u = await db.get(User, user.id)
                u.is_verified = True
                await db.commit()
                response = RedirectResponse("/dashboard", status_code=303)
                response.set_cookie("token", token, httponly=True, secure=True, samesite="lax", max_age=30 * 86400)
                return response

    token = create_token(user.id)
    response = RedirectResponse("/dashboard", status_code=303)
    response.set_cookie("token", token, httponly=True, secure=True, samesite="lax", max_age=30 * 86400)
    return response


@app.post("/logout")
async def logout(request: Request, _: bool = Depends(verify_csrf)):
    token = request.cookies.get("token")
    if token:
        from app.auth import decode_token
        _, jti, _ = decode_token(token)
        if jti:
            async with async_session() as db:
                db.add(RevokedToken(jti=jti))
                await db.commit()
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie("token")
    return response


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_auth), error: str = ""):
    plan_info = PLANS[user.plan]
    safe_errors = {
        "Cannot monitor private or internal URLs",
        "Invalid URL. Please enter a valid http:// or https:// link.",
        "Only http:// and https:// URLs are allowed.",
        "URL is too long (max 2000 characters).",
        "URL already exists.",
    }
    display_error = error if error in safe_errors else ""

    async with async_session() as db:
        result = await db.execute(
            select(Site).where(Site.user_id == user.id).order_by(Site.id.desc())
        )
        sites = result.scalars().all()

        site_data = []
        for site in sites:
            last_check_q = (
                select(Check)
                .where(Check.site_id == site.id)
                .order_by(desc(Check.checked_at))
                .limit(1)
            )
            last_check = (await db.execute(last_check_q)).scalar_one_or_none()

            total_q = select(func.count(Check.id)).where(Check.site_id == site.id)
            total = (await db.execute(total_q)).scalar() or 0

            up_q = select(func.count(Check.id)).where(
                Check.site_id == site.id, Check.is_up == True
            )
            up_count = (await db.execute(up_q)).scalar() or 0
            uptime = round((up_count / total * 100) if total > 0 else 0, 1)

            site_data.append({
                "site": site,
                "last_check": last_check,
                "total_checks": total,
                "uptime": uptime,
            })

    sites_count = len(sites)
    max_sites = plan_info["max_sites"]

    return render(request, "dashboard.html", {
        "user": user,
        "plan": plan_info,
        "sites": site_data,
        "sites_count": sites_count,
        "max_sites": max_sites,
        "error": display_error,
    })


@app.post("/sites/add")
@limiter.limit("20/minute")
async def add_site(
    request: Request,
    name: str = Form(...),
    url: str = Form(...),
    check_ssl: bool = Form(False),
    expected_status: int = Form(200),
    keyword: str = Form(""),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    from urllib.parse import urlparse as _urlparse
    parsed = _urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        return RedirectResponse("/dashboard?error=Invalid+URL.+Please+enter+a+valid+http%3A%2F%2F+or+https%3A%2F%2F+link.", status_code=303)
    if parsed.scheme not in ("http", "https"):
        return RedirectResponse("/dashboard?error=Only+http%3A%2F%2F+and+https%3A%2F%2F+URLs+are+allowed.", status_code=303)
    if parsed.hostname and _is_private_host(parsed.hostname):
        return RedirectResponse("/dashboard?error=Cannot+monitor+private+or+internal+URLs", status_code=303)
    if len(name) > 200:
        name = name[:200]
    if len(url) > 2000:
        return RedirectResponse("/dashboard?error=URL+is+too+long+(max+2000+characters).", status_code=303)

    plan_info = PLANS[user.plan]

    async with async_session() as db:
        count_q = select(func.count(Site.id)).where(Site.user_id == user.id)
        count = (await db.execute(count_q)).scalar() or 0

        if count >= plan_info["max_sites"]:
            return render(request, "dashboard.html", {
                "user": user,
                "plan": plan_info,
                "sites": [],
                "sites_count": count,
                "max_sites": plan_info["max_sites"],
                "error": "Plan limit reached! Upgrade to add more sites.",
            })

        existing = (await db.execute(
            select(Site).where(Site.user_id == user.id, Site.url == url)
        )).scalar_one_or_none()
        if existing:
            return RedirectResponse("/dashboard?error=URL+already+exists.", status_code=303)

        site = Site(
            user_id=user.id,
            name=name,
            url=url,
            check_ssl=check_ssl,
            expected_status=expected_status,
            keyword=keyword if keyword else None,
            interval_sec=plan_info["interval"],
        )
        db.add(site)
        await db.commit()

    return RedirectResponse("/dashboard", status_code=303)


@app.post("/sites/{site_id}/delete")
async def delete_site(site_id: int, user: User = Depends(require_auth), _: bool = Depends(verify_csrf)):
    async with async_session() as db:
        site = await db.get(Site, site_id)
        if site and site.user_id == user.id:
            await db.delete(site)
            await db.commit()
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/sites/{site_id}/check")
async def manual_check(site_id: int, user: User = Depends(require_auth), _: bool = Depends(verify_csrf)):
    async with async_session() as db:
        site = await db.get(Site, site_id)
        if site and site.user_id == user.id:
            await check_site(site, db)
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/sites/{site_id}/toggle")
async def toggle_site(site_id: int, user: User = Depends(require_auth), _: bool = Depends(verify_csrf)):
    async with async_session() as db:
        site = await db.get(Site, site_id)
        if site and site.user_id == user.id:
            site.enabled = not site.enabled
            await db.commit()
    return RedirectResponse("/dashboard", status_code=303)


@app.get("/site/{site_id}", response_class=HTMLResponse)
async def site_detail(request: Request, site_id: int, user: User = Depends(require_auth)):
    async with async_session() as db:
        site = await db.get(Site, site_id)
        if not site or site.user_id != user.id:
            return RedirectResponse("/dashboard", status_code=303)

        result = await db.execute(
            select(Check)
            .where(Check.site_id == site_id)
            .order_by(desc(Check.checked_at))
            .limit(100)
        )
        checks = result.scalars().all()

    session_id, is_new = get_or_create_csrf_session_id(request)
    lang = request.cookies.get("lang", "en")
    t = get_translations(lang)
    return render(request, "detail.html", {
        "user": user,
        "site": site,
        "checks": checks,
        "slack_webhook_url": site.slack_webhook_url or "",
        "discord_webhook_url": site.discord_webhook_url or "",
        "custom_webhooks": site.custom_webhooks or "",
    })


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request):
    user = await get_current_user(request)
    lang = request.cookies.get("lang", "en")
    t = get_translations(lang)
    return templates.TemplateResponse(request, "pricing.html", {"user": user, "plans": PLANS, "t": t})


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, user: User = Depends(require_auth)):
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)

    async with async_session() as db:
        users_q = select(User).order_by(desc(User.created_at))
        all_users = (await db.execute(users_q)).scalars().all()

        total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
        total_sites = (await db.execute(select(func.count(Site.id)))).scalar() or 0
        total_checks = (await db.execute(select(func.count(Check.id)))).scalar() or 0

        pro_users = (await db.execute(select(func.count(User.id)).where(User.plan == "pro"))).scalar() or 0
        ent_users = (await db.execute(select(func.count(User.id)).where(User.plan == "enterprise"))).scalar() or 0
        free_users = total_users - pro_users - ent_users

        total_revenue = pro_users * 9 + ent_users * 29

        for u in all_users:
            u.site_count = (await db.execute(select(func.count(Site.id)).where(Site.user_id == u.id))).scalar() or 0
            u.check_count = (await db.execute(
                select(func.count(Check.id)).join(Site).where(Site.user_id == u.id)
            )).scalar() or 0

    return render(request, "admin.html", {
        "user": user,
        "all_users": all_users,
        "total_users": total_users,
        "total_sites": total_sites,
        "total_checks": total_checks,
        "pro_users": pro_users,
        "ent_users": ent_users,
        "free_users": free_users,
        "total_revenue": total_revenue,
        "plans": PLANS,
    })


@app.post("/admin/user/{user_id}/plan")
async def admin_change_plan(
    user_id: int,
    plan: str = Form(...),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)

    if plan not in PLANS:
        return RedirectResponse("/admin", status_code=303)

    async with async_session() as db:
        target = await db.get(User, user_id)
        if target:
            target.plan = plan
            await db.commit()

    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/user/{user_id}/delete")
async def admin_delete_user(user_id: int, user: User = Depends(require_auth), _: bool = Depends(verify_csrf)):
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)

    if user_id == user.id:
        return RedirectResponse("/admin", status_code=303)

    async with async_session() as db:
        target = await db.get(User, user_id)
        if target:
            await db.execute(delete(Check).where(Check.site_id.in_(
                select(Site.id).where(Site.user_id == user_id)
            )))
            await db.execute(delete(Site).where(Site.user_id == user_id))
            await db.execute(delete(ApiKey).where(ApiKey.user_id == user_id))
            await db.execute(delete(VerificationToken).where(VerificationToken.user_id == user_id))
            await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id))
            await db.delete(target)
            await db.commit()

    return RedirectResponse("/admin", status_code=303)


SAFE_SETTINGS_ERRORS = {"admin_only", "Database not found"}

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user: User = Depends(require_auth), message: str = "", error: str = ""):
    decrypted_chat_id = decrypt_value(user.telegram_chat_id)
    safe_error = error if error in SAFE_SETTINGS_ERRORS else ""
    lang = request.cookies.get("lang", user.language or "en")
    t = get_translations(lang)
    return render(request, "settings.html", {
        "user": user,
        "telegram_chat_id_plain": decrypted_chat_id,
        "slack_webhook_url": user.slack_webhook_url or "",
        "discord_webhook_url": user.discord_webhook_url or "",
        "custom_webhooks": user.custom_webhooks or "",
        "message": message,
        "error": safe_error,
        "t": t,
        "lang": lang,
    })


@app.post("/settings")
async def update_settings(
    request: Request,
    notify_email: bool = Form(False),
    notify_telegram: bool = Form(False),
    telegram_chat_id: str = Form(""),
    notify_slack: bool = Form(False),
    slack_webhook_url: str = Form(""),
    notify_discord: bool = Form(False),
    discord_webhook_url: str = Form(""),
    custom_webhooks: str = Form(""),
    audio_alert: bool = Form(False),
    notify_slow: bool = Form(False),
    slow_threshold_ms: int = Form(3000),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    async with async_session() as db:
        u = await db.get(User, user.id)
        u.notify_email = notify_email
        u.notify_telegram = notify_telegram
        u.audio_alert = audio_alert
        u.telegram_chat_id = encrypt_value(telegram_chat_id) if telegram_chat_id else None
        u.notify_slack = notify_slack
        u.slack_webhook_url = slack_webhook_url if slack_webhook_url else None
        u.notify_discord = notify_discord
        u.discord_webhook_url = discord_webhook_url if discord_webhook_url else None
        u.custom_webhooks = custom_webhooks if custom_webhooks.strip() else None
        u.notify_slow = notify_slow
        u.slow_threshold_ms = max(500, min(30000, slow_threshold_ms))
        await db.commit()
    return RedirectResponse("/settings?message=Settings+saved!", status_code=303)


@app.post("/sites/bulk-import")
@limiter.limit("10/minute")
async def bulk_import(
    request: Request,
    import_data: str = Form(...),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    plan_info = PLANS[user.plan]
    async with async_session() as db:
        count_q = select(func.count(Site.id)).where(Site.user_id == user.id)
        count = (await db.execute(count_q)).scalar() or 0
        remaining = plan_info["max_sites"] - count

        reader = csv.reader(io.StringIO(import_data))
        added = 0
        for row in reader:
            if added >= remaining:
                break
            if len(row) < 2:
                continue
            name = row[0].strip()
            url = row[1].strip()
            ssl_check = row[2].strip().lower() in ("true", "1", "yes") if len(row) > 2 else False
            if not url.startswith("http"):
                url = "https://" + url
            site = Site(
                user_id=user.id,
                name=name,
                url=url,
                check_ssl=ssl_check,
                interval_sec=plan_info["interval"],
            )
            db.add(site)
            added += 1
        await db.commit()
    return RedirectResponse("/dashboard", status_code=303)


_csv_dangerous = re.compile(r'^[=+\-@\t\r]')

def _csv_safe(val):
    s = str(val) if val is not None else ""
    if _csv_dangerous.match(s):
        s = "'" + s
    return s


@app.get("/export/{site_id}")
async def export_site_checks(site_id: int, user: User = Depends(require_auth)):
    async with async_session() as db:
        site = await db.get(Site, site_id)
        if not site or site.user_id != user.id:
            return RedirectResponse("/dashboard", status_code=303)

        result = await db.execute(
            select(Check)
            .where(Check.site_id == site_id)
            .order_by(desc(Check.checked_at))
            .limit(1000)
        )
        checks = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Time", "Status", "HTTP Code", "Response (ms)", "SSL Days", "Error"])
    for c in checks:
        writer.writerow([
            c.checked_at.strftime("%Y-%m-%d %H:%M:%S") if c.checked_at else "",
            "UP" if c.is_up else "DOWN",
            c.status_code or "",
            c.response_ms or "",
            c.ssl_days_left or "",
            _csv_safe(c.error_message),
        ])

    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', site.name)[:50]
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_report.csv"'},
    )


@app.post("/sites/{site_id}/notifications")
async def update_site_notifications(
    request: Request,
    site_id: int,
    notify_slack: bool = Form(False),
    slack_webhook_url: str = Form(""),
    notify_discord: bool = Form(False),
    discord_webhook_url: str = Form(""),
    custom_webhooks: str = Form(""),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    async with async_session() as db:
        site = await db.get(Site, site_id)
        if site and site.user_id == user.id:
            site.notify_slack = notify_slack
            site.slack_webhook_url = slack_webhook_url if slack_webhook_url else None
            site.notify_discord = notify_discord
            site.discord_webhook_url = discord_webhook_url if discord_webhook_url else None
            site.custom_webhooks = custom_webhooks if custom_webhooks.strip() else None
            await db.commit()
    return RedirectResponse(f"/site/{site_id}", status_code=303)


@app.post("/admin/blog/create")
async def create_blog_post(
    request: Request,
    title: str = Form(...),
    slug: str = Form(...),
    excerpt: str = Form(...),
    content: str = Form(...),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)
    slug = re.sub(r'[^a-z0-9\-]', '', slug.lower().replace(' ', '-'))[:300]
    async with async_session() as db:
        post = BlogPost(title=title.strip()[:300], slug=slug, excerpt=excerpt.strip()[:500], content=content)
        db.add(post)
        await db.commit()
    return RedirectResponse("/blog", status_code=303)


@app.get("/blog/{slug}/edit", response_class=HTMLResponse)
async def edit_blog_page(request: Request, slug: str, user: User = Depends(require_auth)):
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)
    async with async_session() as db:
        post = (await db.execute(select(BlogPost).where(BlogPost.slug == slug))).scalar_one_or_none()
    if not post:
        return RedirectResponse("/blog", status_code=303)
    lang = request.cookies.get("lang", "en")
    t = get_translations(lang)
    return render(request, "blog_edit.html", {"user": user, "post": post, "t": t})


@app.post("/blog/{slug}/edit")
async def update_blog_post(
    request: Request,
    slug: str,
    title: str = Form(...),
    content: str = Form(...),
    excerpt: str = Form(...),
    is_published: bool = Form(True),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)
    async with async_session() as db:
        post = (await db.execute(select(BlogPost).where(BlogPost.slug == slug))).scalar_one_or_none()
        if post:
            post.title = title.strip()[:300]
            post.content = content
            post.excerpt = excerpt.strip()[:500]
            post.is_published = is_published
            await db.commit()
    return RedirectResponse(f"/blog/{slug}", status_code=303)


@app.post("/blog/{slug}/delete")
async def delete_blog_post(slug: str, user: User = Depends(require_auth), _: bool = Depends(verify_csrf)):
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)
    async with async_session() as db:
        post = (await db.execute(select(BlogPost).where(BlogPost.slug == slug))).scalar_one_or_none()
        if post:
            await db.delete(post)
            await db.commit()
    return RedirectResponse("/blog", status_code=303)


@app.get("/blog/new", response_class=HTMLResponse)
async def new_blog_page(request: Request, user: User = Depends(require_auth)):
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=303)
    lang = request.cookies.get("lang", "en")
    t = get_translations(lang)
    return render(request, "blog_edit.html", {"user": user, "post": None, "t": t})


@app.get("/api/sites")
@limiter.limit("30/minute")
async def api_sites(request: Request, user: User = Depends(require_auth)):
    async with async_session() as db:
        result = await db.execute(
            select(Site).where(Site.user_id == user.id)
        )
        sites = result.scalars().all()
    return [
        {"id": s.id, "name": s.name, "url": s.url, "enabled": s.enabled}
        for s in sites
    ]


@app.get("/api/checks/{site_id}")
@limiter.limit("30/minute")
async def api_checks(request: Request, site_id: int, limit: int = 50, user: User = Depends(require_auth)):
    async with async_session() as db:
        site = await db.get(Site, site_id)
        if not site or site.user_id != user.id:
            return []
        result = await db.execute(
            select(Check)
            .where(Check.site_id == site_id)
            .order_by(desc(Check.checked_at))
            .limit(limit)
        )
        checks = result.scalars().all()
    return [
        {
            "status_code": c.status_code,
            "response_ms": c.response_ms,
            "is_up": c.is_up,
            "ssl_valid": c.ssl_valid,
            "ssl_days_left": c.ssl_days_left,
            "error": c.error_message,
            "checked_at": c.checked_at.isoformat(),
        }
        for c in checks
    ]


@app.get("/verify-email", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def verify_email_page(request: Request, msg: str = ""):
    user = await get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.is_verified:
        return RedirectResponse("/dashboard", status_code=302)

    error = ""
    message = ""
    if msg == "email_failed":
        error = "Email could not be sent. Please click Resend below."
    elif msg == "ok":
        message = "Verification code sent! Check your email."

    return render(request, "verify_email.html", {"email": user.email, "error": error, "message": message})


@app.post("/verify-email")
@limiter.limit("10/minute")
async def verify_email_submit(
    request: Request,
    code: str = Form(...),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    if user.is_verified:
        return RedirectResponse("/dashboard", status_code=302)

    async with async_session() as db:
        result = await db.execute(
            select(VerificationToken).where(
                VerificationToken.user_id == user.id,
                VerificationToken.purpose == "verify",
            ).order_by(desc(VerificationToken.created_at)).limit(1)
        )
        vt = result.scalar_one_or_none()

        if not vt or not hmac.compare_digest(vt.code, code):
            return render(request, "verify_email.html", {"error": "Invalid code. Try again.", "email": user.email})

        if _utcnow() > vt.expires_at:
            return render(request, "verify_email.html", {"error": "Code expired. Request a new one.", "email": user.email})

        u = await db.get(User, user.id)
        u.is_verified = True
        await db.delete(vt)
        await db.commit()

    return RedirectResponse("/dashboard", status_code=303)


@app.post("/verify-email/resend")
@limiter.limit("3/minute")
async def verify_email_resend(
    request: Request,
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    if user.is_verified:
        return RedirectResponse("/dashboard", status_code=302)

    if _is_configured():
        async with async_session() as db:
            old = await db.execute(
                select(VerificationToken).where(
                    VerificationToken.user_id == user.id,
                    VerificationToken.purpose == "verify",
                )
            )
            for t in old.scalars().all():
                await db.delete(t)

            code = generate_code()
            expires = _utcnow() + datetime.timedelta(minutes=15)
            vt = VerificationToken(user_id=user.id, code=code, purpose="verify", expires_at=expires)
            db.add(vt)
            await db.commit()
            asyncio.ensure_future(asyncio.to_thread(
                send_verification_code, user.email, code, user.username
            ))

    return RedirectResponse("/verify-email?msg=ok", status_code=303)


@app.get("/forgot-password", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def forgot_password_page(request: Request, error: str = "", message: str = ""):
    return render(request, "forgot_password.html", {"error": error, "message": message})


@app.post("/forgot-password")
@limiter.limit("5/minute")
async def forgot_password_submit(
    request: Request,
    email: str = Form(...),
    _: bool = Depends(verify_csrf),
):
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

    if not user or not _is_configured():
        return render(request, "forgot_password.html", {"message": "If an account exists, a reset code has been sent."})

    async with async_session() as db:
        old = await db.execute(
            select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
        )
        for t in old.scalars().all():
            t.used = True

        code = generate_code()
        expires = _utcnow() + datetime.timedelta(minutes=15)
        prt = PasswordResetToken(user_id=user.id, code=code, expires_at=expires)
        db.add(prt)
        await db.commit()

    asyncio.ensure_future(asyncio.to_thread(
        send_password_reset_code, user.email, code, user.username
    ))

    return RedirectResponse(f"/reset-password?email={email}", status_code=303)


@app.get("/reset-password", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def reset_password_page(request: Request, email: str = "", error: str = "", message: str = ""):
    return render(request, "reset_password.html", {"error": error, "message": message, "email": email})


@app.post("/reset-password")
@limiter.limit("5/minute")
async def reset_password_submit(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    _: bool = Depends(verify_csrf),
):
    if password != confirm_password:
        return render(request, "reset_password.html", {"error": "Passwords do not match", "email": email})
    if len(password) < 8:
        return render(request, "reset_password.html", {"error": "Password must be at least 8 characters", "email": email})
    if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'[0-9]', password):
        return render(request, "reset_password.html", {"error": "Password must contain uppercase, lowercase, and a number", "email": email})

    async with async_session() as db:
        user_result = await db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()
        if not user:
            return render(request, "reset_password.html", {"error": "Invalid request"})

        result = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used == False,
            ).order_by(desc(PasswordResetToken.created_at)).limit(5)
        )
        tokens = result.scalars().all()
        matched = None
        for t in tokens:
            if hmac.compare_digest(t.code, code):
                matched = t
                break

        if not matched:
            return render(request, "reset_password.html", {"error": "Invalid code", "email": email})

        if _utcnow() > matched.expires_at:
            return render(request, "reset_password.html", {"error": "Code expired. Request a new one.", "email": email})

        matched.used = True
        user.password_hash = hash_password(password)
        user.password_changed_at = _utcnow()
        await db.commit()

    return RedirectResponse("/login?error=Password+reset+successful.+Please+sign+in.", status_code=303)


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request, user: User = Depends(require_auth)):
    async with async_session() as db:
        result = await db.execute(
            select(Site).where(Site.user_id == user.id).order_by(Site.id.desc())
        )
        sites = result.scalars().all()

        total_sites = len(sites)
        up_count = 0
        down_count = 0
        total_checks = 0
        total_response = 0.0
        response_count = 0
        site_stats = []

        for site in sites:
            last_check_q = (
                select(Check).where(Check.site_id == site.id)
                .order_by(desc(Check.checked_at)).limit(1)
            )
            last = (await db.execute(last_check_q)).scalar_one_or_none()
            if last and last.is_up:
                up_count += 1
            elif last and not last.is_up:
                down_count += 1

            total_q = select(func.count(Check.id)).where(Check.site_id == site.id)
            site_total = (await db.execute(total_q)).scalar() or 0
            up_q = select(func.count(Check.id)).where(Check.site_id == site.id, Check.is_up == True)
            site_up = (await db.execute(up_q)).scalar() or 0
            uptime = round((site_up / site_total * 100) if site_total > 0 else 0, 1)

            avg_q = select(func.avg(Check.response_ms)).where(Check.site_id == site.id, Check.is_up == True)
            avg_resp = (await db.execute(avg_q)).scalar()
            avg_resp = round(avg_resp, 1) if avg_resp else 0

            total_checks += site_total
            if avg_resp > 0:
                total_response += avg_resp
                response_count += 1

            last_str = last.checked_at.strftime("%Y-%m-%d %H:%M") if last else "Never"

            site_stats.append({
                "name": site.name,
                "url": site.url,
                "uptime": uptime,
                "avg_response": avg_resp,
                "last_check": last_str,
            })

        overall_uptime = 0
        if total_checks > 0:
            all_up_q = select(func.count(Check.id)).where(Check.is_up == True)
            all_up = (await db.execute(all_up_q)).scalar() or 0
            overall_uptime = round(all_up / total_checks * 100, 1)

        avg_response = round(total_response / response_count, 1) if response_count > 0 else 0

    return render(request, "stats.html", {
        "user": user,
        "total_sites": total_sites,
        "up_count": up_count,
        "down_count": down_count,
        "total_checks": total_checks,
        "avg_response": avg_response,
        "overall_uptime": overall_uptime,
        "site_stats": site_stats,
    })


@app.get("/backup/download")
async def backup_download(request: Request, user: User = Depends(require_auth)):
    if not user.is_admin:
        return RedirectResponse("/settings?error=admin_only", status_code=303)

    from app.database import DATABASE_URL as _unused
    if "sqlite" in DATABASE_URL:
        import shutil
        import tempfile
        db_path = os.path.join("data", "monitor.db")
        if not os.path.exists(db_path):
            return RedirectResponse("/settings?error=admin_only", status_code=303)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            shutil.copy2(db_path, tmp.name)
            tmp_path = tmp.name
        def iter_file():
            with open(tmp_path, "rb") as f:
                yield from f
            os.unlink(tmp_path)
        filename = "sitewatch_backup.db"
        return StreamingResponse(
            iter_file(),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    async with async_session() as db:
        users = (await db.execute(select(User))).scalars().all()
        sites = (await db.execute(select(Site))).scalars().all()
        checks = (await db.execute(select(Check).limit(50000))).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["=== USERS ==="])
    writer.writerow(["id", "username", "email", "plan", "is_admin", "is_verified", "created_at"])
    for u in users:
        writer.writerow([u.id, u.username, u.email, u.plan, u.is_admin, u.is_verified,
                         u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else ""])
    writer.writerow([])
    writer.writerow(["=== SITES ==="])
    writer.writerow(["id", "user_id", "name", "url", "enabled", "check_ssl", "expected_status", "interval_sec"])
    for s in sites:
        writer.writerow([s.id, s.user_id, s.name, s.url, s.enabled, s.check_ssl, s.expected_status, s.interval_sec])
    writer.writerow([])
    writer.writerow(["=== CHECKS (last 50k) ==="])
    writer.writerow(["id", "site_id", "status_code", "response_ms", "is_up", "ssl_days_left", "error_message", "checked_at"])
    for c in checks:
        writer.writerow([c.id, c.site_id, c.status_code, c.response_ms, c.is_up, c.ssl_days_left,
                         (c.error_message or "")[:200], c.checked_at.strftime("%Y-%m-%d %H:%M") if c.checked_at else ""])

    output.seek(0)
    filename = "sitewatch_backup.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/changelog", response_class=HTMLResponse)
async def changelog_page(request: Request):
    user = await get_current_user(request)
    lang = request.cookies.get("lang", "en")
    t = get_translations(lang)
    return templates.TemplateResponse(request, "changelog.html", {"user": user, "t": t})


@app.post("/settings/audio")
async def toggle_audio(
    audio_alert: bool = Form(False),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    async with async_session() as db:
        u = await db.get(User, user.id)
        u.audio_alert = audio_alert
        await db.commit()
    return RedirectResponse("/settings", status_code=303)


@app.get("/api/alerts")
@limiter.limit("30/minute")
async def api_alerts(request: Request, user: User = Depends(require_auth)):
    alerts = []
    async with async_session() as db:
        result = await db.execute(
            select(Site).where(Site.user_id == user.id, Site.enabled == True)
        )
        sites = result.scalars().all()
        for site in sites:
            last_check_q = (
                select(Check).where(Check.site_id == site.id)
                .order_by(desc(Check.checked_at)).limit(1)
            )
            last = (await db.execute(last_check_q)).scalar_one_or_none()
            if last and not last.is_up:
                alerts.append({
                    "site_id": site.id,
                    "name": site.name,
                    "url": site.url,
                    "error": last.error_message,
                    "last_checked": last.checked_at.isoformat(),
                })
    return alerts


@app.get("/api-keys", response_class=HTMLResponse)
async def api_keys_page(request: Request, user: User = Depends(require_auth)):
    async with async_session() as db:
        result = await db.execute(
            select(ApiKey).where(ApiKey.user_id == user.id).order_by(desc(ApiKey.created_at))
        )
        keys = result.scalars().all()
    new_key = request.query_params.get("new_key", "")
    return render(request, "api_keys.html", {"user": user, "keys": keys, "new_key": new_key})


@app.post("/api-keys/generate")
@limiter.limit("10/minute")
async def generate_api_key(
    request: Request,
    name: str = Form(...),
    user: User = Depends(require_auth),
    _: bool = Depends(verify_csrf),
):
    key = "sk_" + secrets.token_hex(32)
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    key_prefix = key[:11] + "\u2026"
    async with async_session() as db:
        api_key = ApiKey(user_id=user.id, key_hash=key_hash, key_prefix=key_prefix, name=name)
        db.add(api_key)
        await db.commit()
    async with async_session() as db:
        result = await db.execute(
            select(ApiKey).where(ApiKey.user_id == user.id).order_by(desc(ApiKey.created_at))
        )
        keys = result.scalars().all()
    return render(request, "api_keys.html", {"user": user, "keys": keys, "new_key": key})


@app.post("/api-keys/{key_id}/delete")
async def delete_api_key(key_id: int, user: User = Depends(require_auth), _: bool = Depends(verify_csrf)):
    async with async_session() as db:
        api_key = await db.get(ApiKey, key_id)
        if api_key and api_key.user_id == user.id:
            await db.delete(api_key)
            await db.commit()
    return RedirectResponse("/api-keys", status_code=303)


@app.post("/api-keys/{key_id}/toggle")
async def toggle_api_key(key_id: int, user: User = Depends(require_auth), _: bool = Depends(verify_csrf)):
    async with async_session() as db:
        api_key = await db.get(ApiKey, key_id)
        if api_key and api_key.user_id == user.id:
            api_key.is_active = not api_key.is_active
            await db.commit()
    return RedirectResponse("/api-keys", status_code=303)


@app.get("/v1/status")
@limiter.limit("60/minute")
async def api_v1_status(request: Request, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Missing or invalid API key"})

    token = authorization.replace("Bearer ", "")
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    async with async_session() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.key_hash == token_hash, ApiKey.is_active == True))
        api_key = result.scalar_one_or_none()

        if not api_key:
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})

        user = await db.get(User, api_key.user_id)
        api_key.last_used_at = _utcnow()
        api_key.requests_today += 1
        await db.commit()

    plan_limit = PLANS[user.plan]["max_sites"]
    async with async_session() as db:
        sites_q = select(Site).where(Site.user_id == user.id)
        sites = (await db.execute(sites_q)).scalars().all()

        site_list = []
        for site in sites:
            last_check_q = (
                select(Check)
                .where(Check.site_id == site.id)
                .order_by(desc(Check.checked_at))
                .limit(1)
            )
            last = (await db.execute(last_check_q)).scalar_one_or_none()
            site_list.append({
                "id": site.id,
                "name": site.name,
                "url": site.url,
                "is_up": last.is_up if last else None,
                "response_ms": last.response_ms if last else None,
                "ssl_days_left": last.ssl_days_left if last else None,
                "last_checked": last.checked_at.isoformat() if last else None,
            })

    return {
        "user": user.username,
        "plan": user.plan,
        "sites_limit": plan_limit,
        "sites_count": len(sites),
        "sites": site_list,
    }


@app.get("/v1/check/{site_url:path}")
@limiter.limit("30/minute")
async def api_v1_check_site(request: Request, site_url: str, authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "Missing or invalid API key"})

    token = authorization.replace("Bearer ", "")
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    async with async_session() as db:
        result = await db.execute(select(ApiKey).where(ApiKey.key_hash == token_hash, ApiKey.is_active == True))
        api_key = result.scalar_one_or_none()

        if not api_key:
            return JSONResponse(status_code=401, content={"error": "Invalid API key"})

        user = await db.get(User, api_key.user_id)
        api_key.last_used_at = _utcnow()
        api_key.requests_today += 1
        await db.commit()

        site_q = select(Site).where(Site.user_id == user.id, Site.url == site_url)
        site = (await db.execute(site_q)).scalar_one_or_none()

        if not site:
            return JSONResponse(status_code=404, content={"error": "Site not found"})

        check = await check_site(site, db)

    return {
        "site": site.name,
        "url": site.url,
        "is_up": check.is_up,
        "status_code": check.status_code,
        "response_ms": check.response_ms,
        "ssl_valid": check.ssl_valid,
        "ssl_days_left": check.ssl_days_left,
        "error": check.error_message,
        "checked_at": check.checked_at.isoformat(),
    }


@app.get("/blog", response_class=HTMLResponse)
async def blog_list(request: Request):
    user = await get_current_user(request)
    async with async_session() as db:
        posts = (await db.execute(
            select(BlogPost).where(BlogPost.is_published == True).order_by(desc(BlogPost.created_at))
        )).scalars().all()
    return render(request, "blog.html", {"user": user, "posts": posts})


@app.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_post(request: Request, slug: str):
    user = await get_current_user(request)
    async with async_session() as db:
        post = (await db.execute(
            select(BlogPost).where(BlogPost.slug == slug, BlogPost.is_published == True)
        )).scalar_one_or_none()
    if not post:
        return RedirectResponse("/blog", status_code=302)
    return render(request, "blog_post.html", {"user": user, "post": post})


@app.post("/reviews/submit")
@limiter.limit("5/minute")
async def submit_review(
    request: Request,
    author_name: str = Form("Anonymous"),
    rating: int = Form(...),
    text: str = Form(...),
    _: bool = Depends(verify_csrf),
):
    author_name = author_name.strip()[:100] or "Anonymous"
    text = text.strip()[:2000]
    if rating < 1 or rating > 5:
        return RedirectResponse("/#testimonials", status_code=303)
    async with async_session() as db:
        user = await get_current_user(request)
        review = Review(
            user_id=user.id if user else None,
            author_name=author_name,
            rating=rating,
            comment=text,
            is_approved=True,
        )
        db.add(review)
        await db.commit()
    return RedirectResponse("/#testimonials", status_code=303)


@app.get("/api/reviews")
async def api_reviews():
    async with async_session() as db:
        reviews = (await db.execute(
            select(Review).where(Review.is_approved == True).order_by(desc(Review.created_at)).limit(20)
        )).scalars().all()
    return [
        {"author": r.author_name, "rating": r.rating, "comment": r.comment, "date": r.created_at.strftime("%Y-%m-%d") if r.created_at else ""}
        for r in reviews
    ]
