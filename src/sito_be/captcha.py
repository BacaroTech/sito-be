"""Self-hosted proof-of-work captcha (no external services).

The server issues an HMAC-signed challenge: the browser must find the number N
such that sha256(salt + N) == challenge. Solving takes ~1s of CPU in the browser,
verifying is instant. Each solution can be used only once and expires.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete

from .db import UsedCaptcha, get_session

# Set CAPTCHA_SECRET in production (and whenever running more than one worker).
CAPTCHA_SECRET = os.getenv("CAPTCHA_SECRET") or secrets.token_hex(32)
MAX_NUMBER = int(os.getenv("CAPTCHA_MAX_NUMBER", "50000"))
EXPIRES_SECONDS = int(os.getenv("CAPTCHA_EXPIRES_SECONDS", "300"))

CAPTCHA_FIELD = "captcha"
HONEYPOT_FIELD = "website"


def _sign(challenge: str) -> str:
    return hmac.new(CAPTCHA_SECRET.encode(), challenge.encode(), hashlib.sha256).hexdigest()


def _hash(salt: str, number: int) -> str:
    return hashlib.sha256(f"{salt}{number}".encode()).hexdigest()


def create_challenge() -> dict:
    expires = int(time.time()) + EXPIRES_SECONDS
    salt = f"{secrets.token_hex(12)}.{expires}."
    number = secrets.randbelow(MAX_NUMBER + 1)
    challenge = _hash(salt, number)
    return {
        "algorithm": "SHA-256",
        "salt": salt,
        "challenge": challenge,
        "maxnumber": MAX_NUMBER,
        "signature": _sign(challenge),
    }


def _bad(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


async def verify_captcha(request: Request, session: Session = Depends(get_session)) -> None:
    form = await request.form()

    if form.get(HONEYPOT_FIELD):
        raise _bad("Captcha non valido")

    raw = form.get(CAPTCHA_FIELD)
    if not isinstance(raw, str) or not raw:
        raise _bad("Captcha mancante")

    try:
        payload = json.loads(base64.b64decode(raw, validate=True))
        salt = str(payload["salt"])
        number = int(payload["number"])
        challenge = str(payload["challenge"])
        signature = str(payload["signature"])
        expires = int(salt.split(".")[1])
    except (ValueError, KeyError, IndexError, TypeError):
        raise _bad("Captcha non valido") from None

    if expires < time.time():
        raise _bad("Captcha scaduto, riprova")
    if not hmac.compare_digest(_sign(challenge), signature):
        raise _bad("Captcha non valido")
    if not hmac.compare_digest(_hash(salt, number), challenge):
        raise _bad("Captcha non valido")

    # Single use: remember the signature until it expires.
    now = datetime.now(UTC)
    session.exec(delete(UsedCaptcha).where(col(UsedCaptcha.expires_at) < now))
    session.add(UsedCaptcha(signature=signature, expires_at=datetime.fromtimestamp(expires, UTC)))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise _bad("Captcha già utilizzato") from None
