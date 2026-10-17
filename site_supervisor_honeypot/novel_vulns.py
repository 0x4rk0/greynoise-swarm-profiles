"""Intentional honeypot decoy flaws (SS-HONEY-2026-01) — NOT real Frostbyte CVEs.

GreyNoise / researcher bait. Edit this file to change formulas, serial, or decoy
payloads. Do not copy real Armis / Frostbyte exploit algorithms here.

Decoys:
  1) SERVICE day-token auth gap (adjacent in spirit to CVE-2025-6519 ONEDAY,
     but different account, different algorithm).
  2) Unauthenticated GetHelpFile path-style probe (adjacent in spirit to
     CVE-2025-52544 unauth file read, but different RPC and no real FS access).
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any

# --- Tunables Cody can change -------------------------------------------------

# Fictional tracking id for this bait (not a real CVE).
DECOY_ID = "SS-HONEY-2026-01"

# Built-in account name (NOT "oneday" / ONEDAY).
SERVICE_USERNAME = "SERVICE"

# Default unit serial when SITE does not carry one. Override via env or SITE.
DEFAULT_UNIT_SERIAL = os.environ.get("HONEY_UNIT_SERIAL", "CXE-RM-2024-0142")

# How many hex chars of SHA256(serial + "-" + YYYYMMDD_UTC) to use as the token.
TOKEN_HEX_LEN = 12

# Fake blob returned for traversal-looking GetHelpFile names (never reads disk).
FAKE_HELP_TRAVERSAL_BLOB = (
    f"<!-- {DECOY_ID} decoy help stub — not a real filesystem read -->\n"
    "<html><head><title>Help</title></head><body>\n"
    "<h1>Site Supervisor Help</h1>\n"
    "<p>Document root unavailable. Contact Copeland support.</p>\n"
    "<pre>errno=2 path=REDACTED</pre>\n"
    "</body></html>\n"
)

FAKE_HELP_NORMAL = (
    f"<!-- {DECOY_ID} help index -->\n"
    "<html><body><h1>Help</h1>"
    "<p>Select a topic from the application Help menu.</p></body></html>\n"
)


# --- SERVICE day-token --------------------------------------------------------

def unit_serial(site: dict[str, Any] | None = None) -> str:
    """Serial used in the day-token formula (from SITE / env)."""
    if site:
        for key in ("unit_serial", "serial", "SerialNumber", "serialnumber"):
            val = site.get(key)
            if val:
                return str(val).strip()
    return DEFAULT_UNIT_SERIAL


def utc_yyyymmdd(when: datetime | None = None) -> str:
    """UTC calendar day as YYYYMMDD."""
    dt = when or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y%m%d")


def service_day_token(serial: str | None = None, when: datetime | None = None) -> str:
    """Password for SERVICE: first TOKEN_HEX_LEN hex chars of SHA256(serial-YYYYMMDD).

    Example material: SHA256("CXE-RM-2024-0142-20261017") -> take [:12].
    """
    ser = (serial or DEFAULT_UNIT_SERIAL).strip()
    day = utc_yyyymmdd(when)
    material = f"{ser}-{day}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return digest[:TOKEN_HEX_LEN]


def is_service_username(username: str) -> bool:
    return str(username or "").strip().upper() == SERVICE_USERNAME


def check_service_credentials(
    username: str,
    password: str,
    *,
    site: dict[str, Any] | None = None,
    sid: str = "",
) -> dict[str, Any]:
    """Validate SERVICE + day-token (plaintext RPC value).

    Also accepts MD5(token) and MD5(token+sid) so SPA-hashed Logins can match
    when scanners or scripts send those forms — still not the real ONEDAY algo.

    Returns dict: matched (bool), token_expected, serial, day, username.
    """
    user = str(username or "").strip()
    pw = str(password or "")
    ser = unit_serial(site)
    day = utc_yyyymmdd()
    expected = service_day_token(ser)
    matched = False
    if is_service_username(user) and pw:
        candidates = {expected, expected.lower(), expected.upper()}
        # Common client-side wraps (not Armis): raw, md5(token), md5(token+sid)
        candidates.add(hashlib.md5(expected.encode()).hexdigest())
        if sid:
            candidates.add(hashlib.md5(f"{expected}{sid}".encode()).hexdigest())
            candidates.add(hashlib.sha256(f"{expected}{sid}".encode()).hexdigest()[:TOKEN_HEX_LEN])
        matched = pw in candidates or pw.lower() in {c.lower() for c in candidates}
    return {
        "matched": matched,
        "username": user,
        "token_expected": expected,
        "serial": ser,
        "day": day,
        "decoy_id": DECOY_ID,
    }


def service_admin_login_result(sid: str, permissions: dict[str, Any]) -> dict[str, Any]:
    """Same shape as a successful Admin / System Admin Login."""
    return {
        "success": True,
        "permissions": permissions,
        "newsid": sid,
        "sid": sid,
        "role": "System Admin",
        "username": SERVICE_USERNAME,
        "validate_result": "OK",
    }


# --- GetHelpFile path-style decoy ---------------------------------------------

def is_path_probe(name: str) -> bool:
    n = str(name or "")
    return (".." in n) or n.startswith("/") or n.startswith("\\")


def help_file_response(name: str) -> dict[str, Any]:
    """Build GetHelpFile result. Never opens real files."""
    probe = is_path_probe(name)
    if probe:
        content = FAKE_HELP_TRAVERSAL_BLOB
        kind = "traversal_decoy"
    else:
        # Benign help stub; include requested name in a comment for realism
        safe = str(name or "index")[:64].replace("<", "").replace(">", "")
        content = FAKE_HELP_NORMAL.replace("Help", f"Help:{safe}", 1)
        kind = "normal"
    return {
        "name": str(name or ""),
        "content": content,
        "content_type": "text/html",
        "size": len(content),
        "ok": True,
        "_decoy": kind,  # stripped before wire if desired; harmless for scanners
        "decoy_id": DECOY_ID,
    }
