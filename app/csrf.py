"""
CSRF (Cross-Site Request Forgery) protection.

Uses the "double submit cookie" pattern, which needs no server-side session
storage:
  1. Every page that renders a form gets a random `csrf_session` cookie
     (set once, httponly, reused on future visits).
  2. The page embeds a signed, time-limited token (HMAC of the session id)
     as a hidden form field.
  3. On submit, we verify the hidden field's signature matches the cookie
     the browser sent — a third-party site can never read the cookie value
     or forge a valid signature without the server's SECRET_KEY.
"""
import hmac
import hashlib
import time
import secrets

from fastapi import Request, HTTPException, Form

from app.auth import SECRET_KEY

CSRF_COOKIE_NAME = "csrf_session"
CSRF_TOKEN_MAX_AGE = 4 * 3600  # 4 hours


def _sign(session_id: str, timestamp: str) -> str:
    message = f"{session_id}:{timestamp}".encode()
    return hmac.new(SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def generate_csrf_token(session_id: str) -> str:
    timestamp = str(int(time.time()))
    return f"{timestamp}.{_sign(session_id, timestamp)}"


def _verify_csrf_value(token: str, session_id: str) -> bool:
    try:
        timestamp_str, signature = token.split(".", 1)
        timestamp = int(timestamp_str)
    except (ValueError, AttributeError):
        return False
    if time.time() - timestamp > CSRF_TOKEN_MAX_AGE:
        return False
    expected = _sign(session_id, timestamp_str)
    return hmac.compare_digest(expected, signature)


def get_or_create_csrf_session_id(request: Request):
    """Returns (session_id, is_new). Call BEFORE rendering the template so
    csrf_token can be added to the context in time."""
    session_id = request.cookies.get(CSRF_COOKIE_NAME)
    if session_id:
        return session_id, False
    return secrets.token_hex(32), True


def set_csrf_cookie_if_new(response, session_id: str, is_new: bool) -> None:
    """Call AFTER creating the response, only when is_new is True."""
    if is_new:
        response.set_cookie(
            CSRF_COOKIE_NAME,
            session_id,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=CSRF_TOKEN_MAX_AGE,
        )


async def verify_csrf(request: Request, csrf_token: str = Form(default="")):
    """
    FastAPI dependency for POST routes. Add `_: bool = Depends(verify_csrf)`
    to any route that must be protected. Requires the form to include a
    `csrf_token` hidden field.
    """
    session_id = request.cookies.get(CSRF_COOKIE_NAME)
    if not session_id or not csrf_token or not _verify_csrf_value(csrf_token, session_id):
        raise HTTPException(
            status_code=403,
            detail="Invalid or expired security token. Please refresh the page and try again.",
        )
    return True
