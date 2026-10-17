#!/usr/bin/env python3
"""Copeland Site Supervisor / E3 CXe honeypot — synthetic site: maplewood.

Aligned with Copeland Supervisory Control Platform (P/N 026-1803) and
Site Supervisor Quick Setup Guide (026-4144): System Summary, Control Inventory,
Case Temp Hi Limit Exceeded alarms, Site Name, engineering units (°F), setpoints.

NO login wall — System Summary is open (matches observed real-device behavior for
viewing summary). Login RPC still exists as an optional stub. SetPointValues works
without prior Login and is heavily logged.

Do not contact real devices. All actions are fake.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs
import urllib.request
import threading

from aiohttp import WSMsgType, web
import aiohttp.web_response as _web_response
# Real Site Supervisor sample had no Server header
_web_response.SERVER_SOFTWARE = ""

BASE = Path(__file__).resolve().parent
# Prefer literally-wget'd mirror of the live Site Supervisor SPA; fall back to static/
MIRROR = BASE / "mirror"
STATIC = MIRROR if (MIRROR / "index.html").exists() else (BASE / "static")
SUMMARY_PATH = BASE / "summary.html"  # legacy custom UI (kept for reference)
LOG_PATH = BASE / "logs" / "attacks.jsonl"
PORT = int(os.environ.get("PORT", "8010"))
ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "").strip()
ALERT_WEBHOOK_FORMAT = os.environ.get("ALERT_WEBHOOK_FORMAT", "json").strip().lower() or "json"
ALERT_CLASSIFICATIONS = {
    "setpoint_change", "config_change", "alarm_ack", "alarm_reset",
    "schedule_change", "user_add_attempt", "app_add", "app_remove", "app_duplicate",
    "novel_auth_probe", "path_traversal_probe",
}

# Default credentials per guide (user/pass) plus common field defaults
# Known usernames (SPA hashes passwords with session id — accept any non-empty
# secret for these accounts). Plain pairs also listed for docs / direct tests.
KNOWN_USERS = {
    "admin": "Admin",          # canonical display name
    "Admin": "Admin",
    "user": "user",
    "Technician": "Technician",
    "technician": "Technician",
    "system.default": "system.default",
}
CREDS = {
    ("user", "pass"),
    ("Admin", "Admin"),
    ("Admin", "pass"),
    ("Admin", "Admin123!"),
    ("admin", "admin"),
    ("admin", "Admin123!"),
    ("Technician", "Technician"),
    ("Technician", "Tech1234"),
    ("system.default", "Admin"),
}

# SPA loginStore.role / Login.permissions: privilege-key -> level (>=20 = ON)
# Keys are ki values: user-management, system-values, app-setpoint, ...
ADMIN_PERMISSIONS = {
    "user-management": 40,
    "system-values": 40,
    "logging": 40,
    "app-commands": 40,
    "applications": 40,
    "add-del": 40,
    "app-bypass": 40,
    "sys-wide-sum": 40,
    "app-override": 40,
    "app-setpoint": 40,
    "alarm-trans": 40,
    "alarm-ack": 40,
    "alarm-mute": 40,
    "alarm-reset": 40,
}
TECH_PERMISSIONS = {
    "system-values": 20,
    "logging": 20,
    "app-commands": 20,
    "applications": 20,
    "app-bypass": 20,
    "sys-wide-sum": 20,
    "app-override": 20,
    "app-setpoint": 40,
    "alarm-trans": 20,
    "alarm-ack": 40,
    "alarm-mute": 40,
    "alarm-reset": 40,
}
USER_PERMISSIONS = {
    "sys-wide-sum": 20,
    "app-setpoint": 20,
    "alarm-ack": 20,
    "alarm-mute": 20,
}

# Plant identity + inventory from live maplewood System Tile DOM (synthetic values only)
from plant_data import (
    SITE, APPDESC, DASHBOARD, NONE_VAL, CIRCUITS, SUCTIONS, AHUS, APPTYPE_META,
    build_inventory, seed_point_vals, default_vals_for_app, _app as make_app,
    POINT_META, LIST_SELECTIONS, SETPOINT_PIDS, TEMP_PIDS, f2c, c2f,
)
import log_history
import app_descriptions
import novel_vulns

# Real device sample had NO Server header — omit it
SECURITY_HEADERS = {
    "X-Frame-Options": "SAMEORIGIN",
    "X-Content-Type-Options": "nosniff",
    "Strict-Transport-Security": "max-age=63072000; includeSubdomains; preload",
    "Content-Security-Policy": "object-src 'none'",
    "X-Permitted-Cross-Domain-Policies": "none",
    "X-XSS-Protection": "1",
}


def _iid(seed: str | None = None) -> str:
    """Stable numeric iid from seed (app name); random only when seed omitted."""
    if seed is None:
        return str(random.randint(100_000_000, 4_294_967_295))
    import hashlib
    h = hashlib.md5(f"ss-honeypot:{seed}".encode()).hexdigest()
    n = int(h[:8], 16) % 3_000_000_000 + 100_000_000
    return str(n)


def _now() -> int:
    return int(time.time())



# --- Inventory / live point store (from plant_data) ---
INVENTORY_APPS: list[dict[str, Any]] = build_inventory()
APP_BY_IID: dict[str, dict[str, Any]] = {str(a["iid"]): a for a in INVENTORY_APPS}
APP_POINT_VALS: dict[str, dict[str, str]] = seed_point_vals()

# Seed remaining inventory apps with plausible defaults
for _app in INVENTORY_APPS:
    _aid = str(_app["iid"])
    if _aid not in APP_POINT_VALS:
        APP_POINT_VALS[_aid] = default_vals_for_app(_app)
    else:
        # ensure AppName present
        APP_POINT_VALS[_aid].setdefault("AppName", _app.get("appname") or _app.get("name") or "")

# Lightweight sim objects for jitter on key analog values (temps in °F internally)
class Point:
    __slots__ = ("pid", "name", "apptype", "eu", "value", "setpoint", "noise", "rate",
                 "point_label", "base_value", "easing", "unit")

    def __init__(self, iid, name, apptype, eu, value, setpoint, noise=0.15, rate=0.04,
                 point_label="", unit="temp"):
        self.pid = str(iid)
        self.name = name
        self.apptype = apptype
        self.eu = eu
        self.value = float(value)
        self.base_value = float(value)
        self.setpoint = float(setpoint) if setpoint is not None else float(value)
        self.noise = noise
        self.rate = rate
        self.point_label = point_label or name
        self.easing = False
        self.unit = unit  # "temp" | "psi" | "pct" | "raw"

    def tick(self):
        if self.easing:
            gap = self.setpoint - self.value
            if abs(gap) < 0.25:
                self.value = self.setpoint + random.uniform(-self.noise, self.noise)
                self.base_value = self.setpoint
                self.easing = False
            else:
                self.value += gap * self.rate + random.uniform(-0.05, 0.05)
        else:
            self.value = self.base_value + random.uniform(-self.noise, self.noise)


def _build_points():
    pts = []
    for iid, name, state, ctrl_f, stpt_f, flags in CIRCUITS:
        sp = stpt_f if stpt_f is not None else ctrl_f
        pts.append(Point(iid, name, "StdCircuit", "°F", ctrl_f, sp, 0.12, 0.04, "CONTROL TEMP", "temp"))
    for iid, name, pres, stpt, active, total, pct, stages_on in SUCTIONS:
        pts.append(Point(iid, name, "Enhanced Suct", "PSI", pres, stpt, 0.08, 0.03, "SUCTION PRES", "psi"))
    for iid, name, temp_f, stpt_f, occ, status, heat, cool in AHUS:
        pts.append(Point(iid, name, "AHULarge", "°F", temp_f, stpt_f, 0.1, 0.04, "ACT CTRL TEMP", "temp"))
    # Condenser pressure
    pts.append(Point("2086068878", "CONDENSER A", "Condenser", "PSI", 212.75, 210.0, 0.15, 0.03, "CTRL VAL OUT", "psi"))
    return pts


POINTS = _build_points()
POINT_BY_PID = {p.pid: p for p in POINTS}
POINT_BY_NAME = {p.name: p for p in POINTS}


def _circuit_state(pt: Point) -> str:
    store = APP_POINT_VALS.get(pt.pid) or {}
    m = {"0": "Refrigeration", "1": "Defrost", "2": "Drip", "3": "Clean"}
    return m.get(str(store.get("CaseState", "0")), "Refrigeration")


def _sync_live_summary_vals(iid: str):
    """Push simulated Point.value into APP_POINT_VALS for streaming tiles."""
    pt = POINT_BY_PID.get(str(iid))
    if not pt:
        return
    store = APP_POINT_VALS.setdefault(str(iid), {})
    if pt.unit == "temp":
        wire = f"{f2c(pt.value):.3f}"
        if pt.apptype == "StdCircuit":
            store["ControlTemp"] = wire
            store["CASE_TEMP"] = wire
        elif pt.apptype == "AHULarge":
            store["ActCtrlTemp"] = wire
            store["SUPPLY_TEMP"] = wire
    elif pt.unit == "psi":
        wire = f"{pt.value:.2f}"
        if pt.apptype == "Enhanced Suct":
            store["SuctionPres"] = wire
        elif pt.apptype == "Condenser":
            store["CtrlValOut"] = wire
            store["FastRecIn"] = f"{pt.value - 0.1:.2f}"



def _wire_val(pt: Point) -> float | str:
    """Primary analog on the wire for device pages."""
    if pt.unit == "temp":
        return round(f2c(pt.value), 3)
    return round(pt.value, 3)




def _app_description_for_iid(iid: str) -> dict | None:
    """Build GetAppDescription payload for an inventory iid (all apptypes)."""
    iid = str(iid)
    pt = POINT_BY_PID.get(iid)
    app = next((a for a in INVENTORY_APPS if str(a.get("iid")) == iid), None)
    if not pt and not app:
        return None
    name = (pt.name if pt else (app.get("appname") or app.get("name") or iid))
    apptype = (pt.apptype if pt else (app.get("apptype") or ""))
    store = APP_POINT_VALS.setdefault(iid, {})
    _sync_live_summary_vals(iid)
    desc = app_descriptions.build_description(
        iid=iid, name=name, apptype=apptype, store=store, pt=pt,
    )
    # Seed value store from description defaults (don't overwrite attacker edits)
    for p in desc.get("points") or []:
        pid = p.get("pid")
        if not pid:
            continue
        if pid not in store:
            store[pid] = str(p.get("val", "0"))
        if pid in store:
            p["val"] = store[pid]
        if pt and pid == "AppName":
            store[pid] = pt.name
            p["val"] = pt.name
        elif pid == "AppName":
            store[pid] = name
            p["val"] = name
    return desc





SESSIONS: dict[str, dict[str, Any]] = {}
WS_CLIENTS: set = set()
_REQUEST_UA = ""
_REQUEST_IP = ""


def _alert_payload(rec: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    """Build body + headers for ALERT_WEBHOOK_FORMAT (ntfy|slack|discord|json)."""
    fmt = ALERT_WEBHOOK_FORMAT
    cls = rec.get("classification", "event")
    src = rec.get("src_ip", "?")
    method = rec.get("method", "")
    ua = rec.get("user_agent", "") or ""
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(rec.get("ts_unix") or time.time()))
    name = rec.get("name") or (rec.get("params") or {}).get("name") or ""
    old_v = rec.get("old_setpoint", rec.get("old"))
    new_v = rec.get("new_setpoint", rec.get("new"))
    detail = ""
    if old_v is not None and new_v is not None:
        detail = f"{name or 'point'} {old_v} → {new_v}"
    elif name:
        detail = str(name)
    elif rec.get("params"):
        detail = json.dumps(rec.get("params"), default=str)[:200]
    title = f"Site Supervisor honeypot · {cls}"
    text = f"[{cls}] {src} {method} {detail}".strip()
    if ua:
        text += f"\nua: {ua[:120]}"
    text += f"\n{ts}"
    if fmt == "ntfy":
        headers = {"Title": title, "Content-Type": "text/plain; charset=utf-8",
                   "Tags": "warning,thermometer" if "setpoint" in cls else "warning",
                   "Priority": "high" if cls == "setpoint_change" else "default"}
        return text.encode("utf-8"), headers
    if fmt == "slack":
        body = {"text": f"*{title}*\n{text}"}
        return json.dumps(body).encode(), {"Content-Type": "application/json"}
    if fmt == "discord":
        body = {"content": f"**{title}**\n```{text}```"}
        return json.dumps(body).encode(), {"Content-Type": "application/json"}
    # default json
    body = {"title": title, "text": text, "event": rec}
    return json.dumps(body, default=str).encode(), {"Content-Type": "application/json"}


def _fire_alert(rec: dict[str, Any]) -> None:
    """Non-blocking POST to ALERT_WEBHOOK_URL. Never raises into the request path."""
    url = ALERT_WEBHOOK_URL
    if not url or rec.get("classification") not in ALERT_CLASSIFICATIONS:
        return

    def _send():
        try:
            body, headers = _alert_payload(rec)
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3) as resp:
                resp.read(64)
        except Exception as e:
            print(f"[alert] webhook failed: {e}", flush=True)

    try:
        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        pass


def log_event(classification, src_ip, method="", params=None, sid="", username="",
              extra=None, user_agent=""):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "ts_unix": time.time(),
        "classification": classification,
        "src_ip": src_ip,
        "sid": sid,
        "username": username,
        "method": method,
        "params": params if params is not None else {},
        "user_agent": user_agent or _REQUEST_UA or "",
    }
    if extra:
        rec.update(extra)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    if classification in ("login_success", "login_fail", "setpoint_change",
                          "alarm_ack", "schedule_change", "user_add_attempt", "config_change",
                          "app_add", "app_remove", "app_duplicate",
                          "novel_auth_probe", "path_traversal_probe"):
        print(f"[{classification}] {src_ip} sid={(sid or '-')[:8]} user={username or '-'} {method} {extra or params}", flush=True)
    _fire_alert(rec)


ACCESS_LOG_PATH = BASE / "logs" / "access.log"

def middleware_access():
    @web.middleware
    async def _acc(request, handler):
        status = 0
        try:
            resp = await handler(request)
            status = resp.status
            return resp
        except web.HTTPException as ex:
            status = ex.status
            raise
        finally:
            try:
                with open(ACCESS_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(f"{int(time.time())} {status} {request.method} {request.rel_url}\n")
            except Exception:
                pass
    return _acc


def middleware_headers():
    @web.middleware
    async def add_headers(request, handler):
        try:
            resp = await handler(request)
        except web.HTTPException as ex:
            for k, v in SECURITY_HEADERS.items():
                ex.headers[k] = v
            while "Server" in ex.headers:
                del ex.headers["Server"]
            raise
        for k, v in SECURITY_HEADERS.items():
            resp.headers[k] = v
        # Drop Server entirely (real sample had no Server header)
        while "Server" in resp.headers:
            del resp.headers["Server"]
        return resp
    return add_headers


def ensure_session(sid, src_ip):
    if sid and sid in SESSIONS:
        SESSIONS[sid]["last_touch"] = time.time()
        return sid
    new_sid = str(uuid.uuid4())
    SESSIONS[new_sid] = {"username": "", "created": time.time(), "last_touch": time.time(), "src_ip": src_ip}
    return new_sid


def handle_GetSessionID(params, sid, src_ip, username):
    new_sid = ensure_session(None, src_ip)
    log_event("recon", src_ip, "GetSessionID", params, new_sid, username)
    return {"sid": new_sid}


def handle_TouchSession(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "TouchSession", params, sid, username)
    return {"ok": True, "sid": sid}


def _canonical_user(user: str) -> str:
    if user in KNOWN_USERS:
        return KNOWN_USERS[user]
    low = user.lower()
    for k, canon in KNOWN_USERS.items():
        if k.lower() == low:
            return canon
    return user


def _permissions_for(user: str) -> dict:
    canon = _canonical_user(user)
    if canon == "Admin":
        return dict(ADMIN_PERMISSIONS)
    if canon == "Technician":
        return dict(TECH_PERMISSIONS)
    if canon == "user":
        return dict(USER_PERMISSIONS)
    return {}


def handle_Login(params, sid, src_ip, username):
    """SPA Login RPC. Guest boot uses key=system.default, value="".
    SPA hashes passwords with session id — accept any secret for known users.
    permissions must be a privilege-key→level object (not a string list).

    Novel bait (SS-HONEY-2026-01): built-in SERVICE + UTC day-token — see novel_vulns.py.
    """
    sid = ensure_session(sid, src_ip)
    p = params or {}
    user = str(p.get("key") or p.get("username") or p.get("user") or "")
    pw = str(p.get("value") if "value" in p else (p.get("password") or p.get("pass") or ""))

    # --- SERVICE day-token (intentional decoy; not real ONEDAY / Frostbyte) ---
    if novel_vulns.is_service_username(user):
        chk = novel_vulns.check_service_credentials(user, pw, site=SITE, sid=sid)
        log_event(
            "novel_auth_probe", src_ip, "Login",
            {"username": novel_vulns.SERVICE_USERNAME, "token_matched": chk["matched"],
             "day": chk["day"], "serial": chk["serial"], "decoy_id": chk["decoy_id"]},
            sid, novel_vulns.SERVICE_USERNAME,
            extra={"token_matched": chk["matched"], "decoy_id": chk["decoy_id"]},
        )
        if chk["matched"]:
            SESSIONS[sid]["username"] = novel_vulns.SERVICE_USERNAME
            SESSIONS[sid]["is_admin"] = True
            log_event("login_success", src_ip, "Login",
                      {"username": novel_vulns.SERVICE_USERNAME, "via": "service_day_token"},
                      sid, novel_vulns.SERVICE_USERNAME)
            return novel_vulns.service_admin_login_result(sid, dict(ADMIN_PERMISSIONS))
        log_event("login_fail", src_ip, "Login",
                  {"username": novel_vulns.SERVICE_USERNAME, "via": "service_day_token"},
                  sid, novel_vulns.SERVICE_USERNAME)
        return {"success": False, "error": "Invalid username or password", "permissions": {},
                "validate_result": "Invalid username or password"}

    canon = _canonical_user(user) if user else ""
    ok = (
        (user == "system.default" and pw == "")
        or (user, pw) in CREDS
        or (canon in ("Admin", "user", "Technician") and pw != "")
        or (canon == "Admin" and pw == "")
    )
    if ok:
        display = canon or user or "system.default"
        SESSIONS[sid]["username"] = display
        SESSIONS[sid]["is_admin"] = display == "Admin"
        perms = _permissions_for(display) if display != "system.default" else {}
        log_event("login_success", src_ip, "Login", {"username": display}, sid, display)
        return {
            "success": True,
            "permissions": perms,
            "newsid": sid,
            "sid": sid,
            "role": "System Admin" if display == "Admin" else display,
            "username": display,
            "validate_result": "OK",
        }
    log_event("login_fail", src_ip, "Login", {"username": user}, sid, user)
    return {"success": False, "error": "Invalid username or password", "permissions": {},
            "validate_result": "Invalid username or password"}


def handle_Logout(params, sid, src_ip, username):
    if sid in SESSIONS:
        SESSIONS[sid]["username"] = ""
    log_event("recon", src_ip, "Logout", params, sid or "", username)
    return {"ok": True}


def handle_GetSystemInformation(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetSystemInformation", params, sid, username)
    out = dict(SITE)
    out["time"] = _now()
    named = {s.get("username") for s in SESSIONS.values()
             if s.get("username") and s.get("username") != "system.default"}
    out["active_users"] = max(len(named), 1 if any(s.get("is_admin") for s in SESSIONS.values()) else 0)
    # Keep footer interesting even before auto-login settles
    if out["active_users"] == 0:
        out["active_users"] = 1
    return out


def handle_GetSystemInventory(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetSystemInventory", params, sid, username)
    return {"aps": INVENTORY_APPS}


def handle_GetAlarms(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAlarms", params, sid, username)
    meat = POINT_BY_NAME.get("21 B SRV MEAT")
    frozen = POINT_BY_NAME.get("01 N.CUSTM FRZ")
    t = _now()
    alarms = []
    # Schema matches real GetAlarms (Case Temp Hi Limit Exceeded)
    def make_alarm(pt, cat, lim_offset, uid, prio="20"):
        return {
            "ack": "UNACK", "ackuser": "", "advinstanceid": f"0000000000{uid}",
            "apptype": pt.apptype if pt else "StdCircuit",
            "attributes": ["ProAct", "Refrigeration"],
            "category": cat, "class": "temp",
            "databasekey": "StdCirAlrmCasHiLimt1", "datatype": "float",
            "devicetype": "E3", "dispEU": "yes", "displaymessage": "",
            "iid": pt.pid if pt else _iid(),
            "limitvalue": f"{(pt.setpoint + lim_offset) if pt else 36:.6f}",
            "messagekey": "Case Temp Hi Limit Exceeded 1",
            "monitorstate": "NOMON",
            "originator": f"{pt.name if pt else '21 B SRV MEAT'}:CASE TEMP 1",
            "priority": prio, "repeatrate": "0", "repeattime": "",
            "reportvalue": f"{(pt.value if pt else 34.5):.6f}",
            "resolution": "AUTO", "resolutiontimestamp": str(t - 2000),
            "sitename": SITE["unitname"], "timestamp": str(t - 400),
            "uid": uid, "unitnum": "1",
        }
    if meat and meat.value > meat.setpoint + 1.5:
        alarms.append(make_alarm(meat, "Critical", 2.0, "710"))
    if frozen and frozen.value > frozen.setpoint + 3:
        alarms.append(make_alarm(frozen, "Critical", 3.0, "711"))
    if not alarms:
        alarms.append(make_alarm(meat, "Advisory", 2.0, "710", "40"))
    for a in alarms:
        st = ALARM_STATE.get(str(a.get("uid")))
        if st:
            a["ack"] = st.get("ack", a["ack"])
            a["ackuser"] = st.get("ackuser", "")
    return {"alarms": alarms}



def _point_meta(pid: str, app: dict | None = None) -> dict:
    meta = dict(POINT_META.get(pid) or {})
    if not meta:
        meta = {"name": pid, "class": "", "dtype": "float", "prec": 1}
    if pid in TEMP_PIDS:
        meta["class"] = "temp"
        meta.setdefault("dtype", "float")
        meta.setdefault("prec", 1)
    return meta


def _point_desc(iid, pid, pt=None, app=None):
    """Build a GetPointsDescription point entry the SPA accepts."""
    pid = str(pid)
    store = APP_POINT_VALS.get(str(iid)) or {}
    meta = _point_meta(pid, app)
    val = store.get(pid, "0")
    if pid == "AppName":
        name = (pt.name if pt else (app.get("appname") if app else str(iid)))
        return {"pid": "AppName", "name": "Name", "group": "Overview", "grpseq": "1",
                "subgrpseq": "1", "class": "", "funct": "", "dtype": "str", "attr": [], "val": name}
    desc = {
        "pid": pid,
        "name": meta.get("name") or pid,
        "group": "Overview",
        "grpseq": "1",
        "subgrpseq": "1",
        "class": meta.get("class") or "",
        "funct": "output",
        "desc": meta.get("name") or pid,
        "dtype": meta.get("dtype") or "float",
        "attr": [],
        "val": str(val),
        "visible": "Basic",
    }
    if desc["dtype"] == "float":
        desc["prec"] = str(meta.get("prec", 1))
    if pid in LIST_SELECTIONS:
        desc["dtype"] = "list"
        desc["list"] = LIST_SELECTIONS[pid]
    elif desc["dtype"] == "dig":
        desc["dtype"] = "list"
        desc["list"] = [{"key": "0", "val": "Off"}, {"key": "1", "val": "On"}]
    return desc


def _point_value_record(ptr):
    """Build a GetPointValues/RealTime point record (val on wire in device unit)."""
    iid, _, pid = str(ptr).partition(":")
    pt = POINT_BY_PID.get(iid)
    app = APP_BY_IID.get(iid)
    _sync_live_summary_vals(iid)
    store = APP_POINT_VALS.get(iid) or {}
    meta = _point_meta(pid, app)
    if pid == "AppName":
        return {"ptr": ptr, "val": (pt.name if pt else store.get("AppName", iid)),
                "status": "0", "dtype": "str", "adv": []}
    val = store.get(pid)
    if val is None:
        # Fallback for unknown pids
        if pt and pid in TEMP_PIDS:
            val = f"{f2c(pt.value):.3f}"
        else:
            val = "0"
    dtype = meta.get("dtype") or "float"
    cls = meta.get("class") or ""
    if pid in LIST_SELECTIONS or dtype == "dig":
        dtype = "list"
    elif pid in ("AppName", "PortName", "SiteName", "UnitName", "FwVersion", "FwStatus", "DisplayStatus", "CP^Category"):
        dtype = "str"
    elif dtype == "uint":
        dtype = "uint"
    rec = {"ptr": ptr, "val": str(val), "status": "0", "class": cls, "dtype": dtype, "adv": []}
    if dtype == "float":
        rec["prec"] = meta.get("prec", 1)
    return rec


def _request_ptrs(params):
    p = params or {}
    pts = p.get("points") if isinstance(p, dict) else (p if isinstance(p, list) else [])
    out = []
    for item in (pts or []):
        if isinstance(item, dict) and item.get("ptr"):
            out.append(str(item["ptr"]))
        elif isinstance(item, str):
            out.append(item)
    return out


def handle_GetPointValues(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetPointValues", params, sid, username)
    ptrs = _request_ptrs(params)
    if not ptrs:
        # All dashboard text points for every app
        for app in INVENTORY_APPS:
            dash = DASHBOARD.get(app.get("apptype") or "") or {}
            for p in dash.get("points") or []:
                if not p.get("icon"):
                    ptrs.append(f"{app['iid']}:{p['pid']}")
    return {"points": [_point_value_record(ptr) for ptr in ptrs]}


def handle_GetRealTimePointsData(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetRealTimePointsData", params, sid, username)
    ptrs = _request_ptrs(params)
    if not ptrs:
        for app in INVENTORY_APPS:
            dash = DASHBOARD.get(app.get("apptype") or "") or {}
            for p in dash.get("points") or []:
                if not p.get("icon"):
                    ptrs.append(f"{app['iid']}:{p['pid']}")
    return {"time": _now(), "points": [_point_value_record(ptr) for ptr in ptrs]}


def handle_GetPointsDescription(params, sid, src_ip, username):
    """Request: {points:{iid:[pid,...]}}. Response keyed by iid: {header, points:[desc]}."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetPointsDescription", params, sid, username)
    req = {}
    p = params or {}
    if isinstance(p, dict) and isinstance(p.get("points"), dict):
        req = p["points"]
    elif isinstance(p, dict) and isinstance(p.get("points"), list):
        for it in p["points"]:
            if isinstance(it, dict) and it.get("iid"):
                req[str(it["iid"])] = it.get("pids") or it.get("points") or []
    out = {}
    for iid, pids in req.items():
        iid = str(iid)
        pt = POINT_BY_PID.get(iid)
        app = APP_BY_IID.get(iid)
        apptype = (app.get("apptype") if app else (pt.apptype if pt else ""))
        header = {
            "name": (app.get("appname") if app else (pt.name if pt else iid)),
            "apptype": apptype,
            "description": APPDESC.get(apptype, apptype),
            "attr": [],
            "desc": [{"type": "group", "name": "Overview", "id": "Overview", "visible": "1", "seq": "1"}],
        }
        # If no pids requested, return all dashboard pids for this apptype
        if not pids:
            dash = DASHBOARD.get(apptype) or {}
            pids = [x["pid"] for x in dash.get("points") or []]
        descs = [_point_desc(iid, str(pid), pt, app) for pid in (pids or [])]
        out[iid] = {"header": header, "points": descs}
    return out


def handle_RegisterPoint(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "RegisterPoint", {"count": len(_request_ptrs(params))}, sid, username)
    return {"success": True}


def handle_UnregisterPoint(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "UnregisterPoint", {"count": len(_request_ptrs(params))}, sid, username)
    return {"success": True}


def handle_GetUserSelectedTilePoints(params, sid, src_ip, username):
    """Request: {user_name, iids:[...]}. Response: {iid: null} (no per-user overrides)."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetUserSelectedTilePoints", params, sid, username)
    iids = (params or {}).get("iids") or []
    return {str(i): None for i in iids}


def handle_GetDashboardSummaryProps(params, sid, src_ip, username):
    """Request: {apptype}. Response: {DSummary:{online_offline_icon, no_alarm_icon, points:[...]}}."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetDashboardSummaryProps", params, sid, username)
    apptype = (params or {}).get("apptype")
    dash = DASHBOARD.get(apptype) or {
        "no_alarm_icon": False, "online_offline_icon": True, "points": [],
    }
    # Return a shallow copy so callers cannot mutate the template
    points = []
    for p in dash.get("points") or []:
        entry = {k: v for k, v in p.items()}
        points.append(entry)
    return {
        "DSummary": {
            "no_alarm_icon": bool(dash.get("no_alarm_icon", False)),
            "online_offline_icon": bool(dash.get("online_offline_icon", True)),
            "points": points,
        }
    }


def handle_GetGroups(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetGroups", params, sid, username)
    return {"groups": [
        {"name": "Refrigeration", "id": "1"},
        {"name": "HVAC", "id": "2"},
        {"name": "Other", "id": "3"},
        {"name": "System", "id": "4"},
    ]}



def handle_GetHomeScreenState(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetHomeScreenState", params, sid, username)
    return {"state": False, "sid": sid}


def handle_GetProfile(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetProfile", params, sid, username)
    p = params or {}
    u = str(p.get("username") or SESSIONS.get(sid, {}).get("username") or "system.default")
    u = _canonical_user(u) if u in KNOWN_USERS or u.lower() in {k.lower() for k in KNOWN_USERS} else u
    # viewlevel MUST be exactly "Advanced" (SPA oa() switch is case-sensitive)
    profile = {
        "username": u,
        "locale": "en-US",
        "dateFormat": "MM/dd/yyyy",
        "timeFormat": "hh:mm:ss",
        "theme": "default",
        "homescreen": {"val": "systemsummary"},
        "userlevel": "4",
        "viewlevel": "Advanced",
        "graphDefaultDisplayRange": 86400,
        "localization": {
            "locale": "en-US",
            "engunits": {
                "temp": "fahren",
                "delta temp": "delta f",
                "pres": "psi",
                "delta pres": "psi",
                "light": "fc",
                "flow": "gpm",
            },
        },
        "displaypeertiles": False,
        "functionkeys": {},
    }
    return {
        "username": u,
        "role": "System Admin" if u == "Admin" else u,
        "locale": "en-US",
        "profile": profile,
        "permissions": _permissions_for(u),
    }


def handle_GetLicenses(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetLicenses", params, sid, username)
    # SPA builds kT(a) per license: reads FID, apptype, name, activeinstances,
    # license, license_string, maxinstances. license_string non-empty avoids the
    # maxinstances.toString() crash and marks the feature enabled.
    feats = [
        ("182052295", "Case Control Circuits", "CaseControlCircuit"),
        ("162757857", "Standard Circuits", "StdCircuit"),
        ("3706664376", "XM Circuits", "XMCircuit"),
        ("3118790244", "BACnet", "BACnet"),
        ("841157322", "MQTT", "MQTT"),
        ("3124480230", "Performance Meter", "PerformanceMeter"),
        ("2948137144", "SSH Tunnel Access", "SSHTunnel"),
    ]
    licenses = []
    for fid, nm, apptype in feats:
        licenses.append({
            "FID": fid,
            "name": nm,
            "apptype": apptype,
            "activeinstances": "0",
            "license": "",
            "license_string": "Enabled",
            "maxinstances": "no limit",
        })
    return {"licenses": licenses}


def handle_GetLayouts(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetLayouts", params, sid, username)
    return {"layouts": []}


def handle_GetUnitList(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetUnitList", params, sid, username)
    return {"units": [{
        "unitnumber": SITE["unitnumber"],
        "unitname": SITE["unitname"],
        "unitmodel": SITE["unitmodel"],
        "platform": SITE["platform"],
        "online": True,
        "desc": SITE["desc"],
    }]}


def handle_GetTimezoneInfo(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetTimezoneInfo", params, sid, username)
    return {"timezone": "America/Los_Angeles", "offset": SITE["timezoneOffset"], "dst": True}


def handle_stub_ok(params, sid, src_ip, username, method="Stub"):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, method, params, sid, username, extra={"note": "stub"})
    return {}


def handle_SetPointValues(params, sid, src_ip, username):
    """SPA write: params {points:[{ptr:"iid:pid", val:"<device unit>"}]}.
    For class temp the SPA sends Celsius; convert to degF for primary setpoints,
    store all pid values, log, and fire ALERT_WEBHOOK_URL.
    Response {points:[{ptr,val}]}; no err == success."""
    sid = ensure_session(sid, src_ip)
    p = params or {}
    items = p.get("points") if isinstance(p, dict) and isinstance(p.get("points"), list) else (
        p if isinstance(p, list) else [p])
    results = []
    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        ptr = item.get("ptr") or ""
        if ptr:
            iid, _, pid = str(ptr).partition(":")
        else:
            iid = str(item.get("pid") or item.get("iid") or "")
            pid = ""
            ptr = f"{iid}:{pid}" if iid else ""
        pt = POINT_BY_PID.get(iid) or POINT_BY_NAME.get(str(item.get("name") or ""))
        raw = item.get("val", item.get("value", item.get("setpoint")))
        if raw is None:
            results.append({"ptr": ptr, "err": "No value"})
            continue
        if iid and iid not in APP_POINT_VALS:
            _app_description_for_iid(iid)
        store = APP_POINT_VALS.setdefault(iid, {}) if iid else {}
        app = next((a for a in INVENTORY_APPS if str(a.get("iid")) == iid), None)
        if not pt and not app and pid not in store:
            log_event("setpoint_change", src_ip, "SetPointValues",
                      {"ptr": ptr, "val": raw}, sid, username, extra={"note": "unknown_point"})
            results.append({"ptr": ptr, "err": "Point not found"})
            continue
        store[pid] = str(raw)
        changed = True
        results.append({"ptr": ptr, "val": str(raw)})

        is_primary_sp = pid in SETPOINT_PIDS or pid in (
            "CaseTempStpt", "SUPPLY_STPT", "SUCTION_STPT", "DISCH_STPT",
            "SENSOR_STPT", "ActiveClStpt",
        )
        is_limit_sp = pid in ("CaseTempHiLim", "CaseTempLoLim", "HiLim", "LoLim",
                              "HiLimit", "LoLimit", "AlarmPPM", "WarnPPM",
                              "TerminateTemp", "CaseTempDB")
        is_temp_sp = pid in TEMP_PIDS
        if pt and (is_primary_sp or is_limit_sp):
            try:
                raw_f = float(raw) if str(raw) != NONE_VAL else None
            except (TypeError, ValueError):
                raw_f = None
            if raw_f is not None and is_primary_sp:
                new_f = c2f(raw_f) if is_temp_sp else raw_f
                old_f = pt.setpoint
                pt.setpoint = new_f
                pt.easing = True
                if is_temp_sp and pid != "ActiveClStpt":
                    store["ActiveClStpt"] = str(raw)
                if pt.apptype == "Enhanced Suct":
                    store["CurPresStpt"] = str(raw)
                log_event(
                    "setpoint_change", src_ip, "SetPointValues",
                    {"ptr": ptr, "name": pt.name, "pid": pid,
                     "old": round(old_f, 2), "new": round(new_f, 2)},
                    sid, username or SESSIONS.get(sid, {}).get("username", ""),
                    extra={"name": pt.name, "old_setpoint": round(old_f, 2),
                           "new_setpoint": round(new_f, 2),
                           "current_value": round(pt.value, 2),                           "unit": ("degF" if is_temp_sp else (pt.eu or "device")), "pid": pid},
                )
            else:
                log_event(
                    "setpoint_change", src_ip, "SetPointValues",
                    {"ptr": ptr, "name": pt.name, "pid": pid, "val": raw},
                    sid, username or SESSIONS.get(sid, {}).get("username", ""),
                    extra={"name": pt.name, "pid": pid, "new_setpoint": str(raw),
                           "old_setpoint": "", "unit": "device"},
                )
        else:
            log_event(
                "setpoint_change", src_ip, "SetPointValues",
                {"ptr": ptr, "name": (pt.name if pt else (app or {}).get("name", iid)),
                 "pid": pid, "val": raw},
                sid, username or SESSIONS.get(sid, {}).get("username", ""),
                extra={"name": (pt.name if pt else iid), "pid": pid,
                       "new_setpoint": str(raw), "old_setpoint": "", "unit": "device"},
            )
    if changed:
        try:
            asyncio.get_running_loop().create_task(broadcast_points())
        except RuntimeError:
            pass
    if not results:
        return {"points": [], "success": False}
    return {"points": results}


# ---------------- Menu / view stubs (synthetic) ----------------
BOOT_TS = _now() - 86400 * 37 - 4211
ALARM_STATE: dict[str, dict[str, Any]] = {}



def handle_GetDefrostSummary(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetDefrostSummary", params, sid, username)
    rows = []
    t = _now()
    for p in POINTS:
        if p.apptype != "StdCircuit":
            continue
        cycle = 6 * 3600 if p.setpoint > 0 else 8 * 3600
        phase = (t + int(p.pid[-3:] or "0")) % cycle
        next_in = cycle - phase
        rows.append({
            "pid": p.pid, "name": p.name, "apptype": p.apptype,
            "temp": round(p.value, 2), "setpoint": round(p.setpoint, 2), "eu": p.eu,
            "state": _circuit_state(p),
            "defrost_type": "Off Time" if p.setpoint > 0 else "Electric",
            "next_defrost": t + next_in,
            "next_defrost_in_sec": next_in,
            "duration_min": 25 if p.setpoint > 0 else 40,
        })
    return {"circuits": rows}


def handle_GetNetworkSummary(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetNetworkSummary", params, sid, username)
    # SPA reads i.devices and derives thisSS = device with status "This Unit"
    local_unit = {
        "iid": next((str(a["iid"]) for a in INVENTORY_APPS if a.get("apptype") == "AreaCtrl"), _iid("E3 Unit01")),
        "appname": SITE["unitname"], "apptype": "AreaCtrl",
        "ControllerType": "107", "status": "This Unit", "online": True,
        "devicetype": "E3", "version": SITE["unitversion"],
        "ipaddress": "192.168.10.50", "model": SITE["unitmodel"],
        "sitename": SITE["SiteName"], "unitnum": "1",
        # SPA sets Q().unitNumber from thisSS.address; missing => /unitundefined/cgi-bin 404s
        "address": "1", "isaggregator": "0", "isannunciator": "0",
    }
    devices = [local_unit]
    for a in INVENTORY_APPS:
        if not a.get("device"):
            continue
        devices.append({
            "iid": str(a["iid"]), "appname": a.get("appname") or a.get("name"),
            "apptype": a.get("apptype"), "status": "Online", "online": True,
            "devicetype": a.get("devicetype") or "",
            "DevAddr": a.get("DevAddr", ""), "Route": a.get("Route", ""),
            "ControllerType": a.get("devicetype") or "",
        })
    return {"devices": devices}


def handle_GetSchedules(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetSchedules", params, sid, username)
    return {"schedules": [
        {"id": "SCHED-LIGHTS", "name": "Sales Floor Lights", "type": "Lighting",
         "enabled": True,
         "events": [
             {"day": "Mon-Fri", "on": "06:00", "off": "22:00"},
             {"day": "Sat", "on": "07:00", "off": "23:00"},
             {"day": "Sun", "on": "08:00", "off": "21:00"},
         ]},
        {"id": "SCHED-CASE-NIGHT", "name": "Case Night Setback", "type": "Refrigeration",
         "enabled": True,
         "events": [
             {"day": "Daily", "on": "00:00", "off": "05:00", "setpoint_offset": 2.0},
         ]},
        {"id": "SCHED-HVAC", "name": "Store HVAC Occupied", "type": "HVAC",
         "enabled": True,
         "events": [
             {"day": "Mon-Sat", "on": "05:30", "off": "22:30"},
             {"day": "Sun", "on": "07:00", "off": "21:00"},
         ]},
    ]}


def handle_SetSchedule(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    p = params or {}
    log_event("schedule_change", src_ip, "SetSchedule", p, sid, username,
              extra={"schedule_id": p.get("id") or p.get("schedule_id"), "name": p.get("name")})
    return {"success": True, "accepted": True, "id": p.get("id") or p.get("schedule_id")}


def handle_GetUsers(params, sid, src_ip, username):
    """SPA login sets isAdministrator via _.includes(user.roles, "System Admin")."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetUsers", params, sid, username)
    return {"users": [
        {
            "username": "Admin",
            "roles": ["System Admin"],
            "role": "System Admin",
            "enabled": True,
            "last_login": BOOT_TS + 1000,
        },
        {
            "username": "Technician",
            "roles": ["Technician"],
            "role": "Technician",
            "enabled": True,
            "last_login": BOOT_TS + 20000,
        },
        {
            "username": "user",
            "roles": ["Technician"],
            "role": "Technician",
            "enabled": True,
            "last_login": BOOT_TS + 50000,
        },
        {
            "username": "system.default",
            "roles": [],
            "role": "Service",
            "enabled": True,
            "last_login": BOOT_TS,
        },
    ]}


def handle_GetSessions(params, sid, src_ip, username):
    """SPA sessionStore: setActiveSessions(report.length)."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetSessions", params, sid, username)
    report = []
    for s_id, sess in SESSIONS.items():
        u = sess.get("username") or ""
        if not u or u == "system.default":
            continue
        report.append({
            "username": u,
            "sid": s_id,
            "ip": sess.get("src_ip") or src_ip,
            "logintime": int(sess.get("created") or time.time()),
            "unitnumber": SITE["unitnumber"],
        })
    if not report:
        report.append({
            "username": "Admin",
            "sid": sid,
            "ip": src_ip,
            "logintime": _now() - 120,
            "unitnumber": SITE["unitnumber"],
        })
    return {"report": report, "sessions": report}


def handle_AddUser(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    p = params or {}
    # Never persist — just log the attempt
    log_event("user_add_attempt", src_ip, "AddUser",
              {"username": p.get("username"), "role": p.get("role")},
              sid, username, extra={"attempted_user": p.get("username")})
    return {"success": False, "error": "User management locked by policy", "code": 403}


def handle_GetLogs(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetLogs", params, sid, username)
    t = _now()
    entries = [
        {"ts": BOOT_TS, "level": "INFO", "source": "System", "message": "Unit power-up · E3 CXe fw 2.30F01"},
        {"ts": BOOT_TS + 12, "level": "INFO", "source": "Network", "message": "eth0 link up 192.168.10.50"},
        {"ts": t - 7200, "level": "INFO", "source": "Defrost", "message": "01 N.CUSTM FRZ entered Defrost"},
        {"ts": t - 6900, "level": "INFO", "source": "Defrost", "message": "01 N.CUSTM FRZ Defrost complete · Drip"},
        {"ts": t - 3600, "level": "WARN", "source": "Alarm", "message": "21 B SRV MEAT Case Temp Hi Limit Exceeded 1"},
        {"ts": t - 3500, "level": "INFO", "source": "Alarm", "message": "21 B SRV MEAT auto-resolved"},
        {"ts": t - 1800, "level": "INFO", "source": "Defrost", "message": "Dairy Case N entered Defrost"},
        {"ts": t - 900, "level": "INFO", "source": "Schedule", "message": "Sales Floor Lights ON"},
        {"ts": t - 120, "level": "INFO", "source": "System", "message": "Session touch from operator UI"},
    ]
    return {"entries": entries, "total": len(entries)}


def handle_GetLogGroups(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetLogGroups", params, sid, username)
    base = next((a for a in INVENTORY_APPS if a.get("apptype") == "Log Group"), None)
    iid = str(base["iid"]) if base else "539799930"
    n = log_history.series_count()
    return {"groups": [
        {"name": "Base Log", "iid": iid, "points": n, "interval_sec": 60},
    ]}


def handle_AcknowledgeAlarm(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    p = params or {}
    uid = str(p.get("uid") or p.get("id") or "")
    ALARM_STATE[uid] = {"ack": "ACK", "ackuser": username or "guest", "ts": _now()}
    log_event("alarm_ack", src_ip, "AcknowledgeAlarm", p, sid, username, extra={"uid": uid})
    return {"success": True, "uid": uid, "ack": "ACK"}


def handle_ResetAlarm(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    p = params or {}
    uid = str(p.get("uid") or p.get("id") or "")
    ALARM_STATE[uid] = {"ack": "RESET", "ackuser": username or "guest", "ts": _now()}
    log_event("alarm_reset", src_ip, "ResetAlarm", p, sid, username, extra={"uid": uid})
    return {"success": True, "uid": uid, "ack": "RESET"}


def handle_GetPhysicalIOStatus(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetPhysicalIOStatus", params, sid, username)
    ios = []
    for i in range(1, 5):
        ios.append({"device": f"16AI_{i:03d}", "type": "16 Analog Inputs", "online": True,
                    "channels": 16, "route": "IONet-01", "addr": str(i)})
        ios.append({"device": f"8RO_{i:03d}", "type": "8 Relay Outputs", "online": True,
                    "channels": 8, "route": "IONet-01", "addr": str(i)})
    return {"devices": ios}


def handle_GetGeneralSystem(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetGeneralSystem", params, sid, username)
    return {
        "site": dict(SITE),
        "engineering_units": "°F",
        "language": "en-US",
        "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_sec": _now() - BOOT_TS,
        "serial": SITE.get("unit_serial") or SITE.get("serial") or "CXE-RM-2024-0142",
    }


def handle_SetGeneralSystem(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    p = params or {}
    log_event("config_change", src_ip, "SetGeneralSystem", p, sid, username)
    # Accept SiteName write into SITE (synthetic only)
    if isinstance(p, dict) and p.get("SiteName"):
        SITE["SiteName"] = str(p["SiteName"])[:64]
    return {"success": True}


def handle_GetProtocolMapping(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetProtocolMapping", params, sid, username)
    return {"mappings": [
        {"protocol": "Modbus RTU", "port": "COM1", "baud": 9600, "devices": 1},
        {"protocol": "IONet", "port": "IONet-01", "baud": 38400, "devices": 8},
        {"protocol": "BACnet/IP", "port": "UDP/47808", "devices": 0},
    ]}


def handle_GetFloorPlan(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetFloorPlan", params, sid, username)
    return {
        "name": "Sales Floor",
        "width": 800, "height": 480,
        "nodes": [
            {"pid": p.pid, "name": p.name, "x": 80 + (i % 4) * 180, "y": 60 + (i // 4) * 140,
             "temp": round(p.value, 1), "eu": p.eu}
            for i, p in enumerate([x for x in POINTS if x.apptype == "StdCircuit"])
        ],
    }


def handle_GetAppDescription(params, sid, src_ip, username):
    """SPA device page boot RPC. Params: {iid} or {iid, filter:{pids:[...]}}.
    Response: {header:{name,apptype,description,attr,desc:[groups]}, points:[Ye fields]}."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAppDescription", params, sid, username)
    p = params or {}
    iid = str(p.get("iid") or "")
    if not iid:
        return {"header": {}, "points": []}
    desc = _app_description_for_iid(iid)
    if not desc:
        return {"header": {"name": iid, "apptype": "", "description": "", "attr": [],
                           "desc": []}, "points": []}
    # Optional pid filter (get-on-use refresh)
    filt = p.get("filter") if isinstance(p.get("filter"), dict) else None
    if filt and isinstance(filt.get("pids"), list) and filt["pids"]:
        want = set(str(x) for x in filt["pids"])
        desc = {
            "header": desc["header"],
            "points": [pt for pt in desc["points"] if pt.get("pid") in want],
        }
    return desc


def handle_GetAppCommands(params, sid, src_ip, username):
    """Params: {iid}. Response: {cmds:[{cmd,mark,confirm,visible,...}]}."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAppCommands", params, sid, username)
    iid = str((params or {}).get("iid") or "")
    pt = POINT_BY_PID.get(iid)
    app = APP_BY_IID.get(iid)
    apptype = (pt.apptype if pt else (app.get("apptype") if app else ""))
    cmds = []
    if apptype == "StdCircuit":
        cmds = [
            {"cmd": "Start Defrost", "mark": "START_DEFROST", "confirm": True,
             "visible": "Basic", "opt": ""},
            {"cmd": "Stop Defrost", "mark": "STOP_DEFROST", "confirm": True,
             "visible": "Basic", "opt": ""},
            {"cmd": "Reset Alarms", "mark": "RESET_ALARMS", "confirm": False,
             "visible": "Basic", "opt": ""},
            {"cmd": "Clean Mode", "mark": "CLEAN_MODE", "confirm": True,
             "visible": "Basic", "opt": ""},
        ]
    elif apptype == "Enhanced Suct":
        cmds = [
            {"cmd": "Reset Alarms", "mark": "RESET_ALARMS", "confirm": False,
             "visible": "Basic", "opt": ""},
            {"cmd": "Force Stage Up", "mark": "STAGE_UP", "confirm": True,
             "visible": "Advanced", "opt": ""},
            {"cmd": "Force Stage Down", "mark": "STAGE_DOWN", "confirm": True,
             "visible": "Advanced", "opt": ""},
        ]
    elif apptype == "AHULarge":
        cmds = [
            {"cmd": "Reset Alarms", "mark": "RESET_ALARMS", "confirm": False,
             "visible": "Basic", "opt": ""},
            {"cmd": "Force Occupied", "mark": "FORCE_OCC", "confirm": True,
             "visible": "Basic", "opt": ""},
            {"cmd": "Force Unoccupied", "mark": "FORCE_UNOCC", "confirm": True,
             "visible": "Basic", "opt": ""},
        ]
    elif apptype in ("Condenser", "RLDS", "MULTIFLEX ESR"):
        cmds = [
            {"cmd": "Reset Alarms", "mark": "RESET_ALARMS", "confirm": False,
             "visible": "Basic", "opt": ""},
        ]
    return {"cmds": cmds}



def _apptype_meta(apptype: str) -> dict[str, Any]:
    meta = dict(APPTYPE_META.get(apptype) or {})
    meta.setdefault("category", "Other")
    meta.setdefault("device", False)
    # SPA Te.convertProtocolName(t) calls t.toLowerCase() — must be a string
    meta.setdefault("devicetype", "")
    meta.setdefault("name_prefix", APPDESC.get(apptype, apptype)[:12] or "APP")
    return meta


def _next_app_iid() -> str:
    """Unique 32-bit-ish decimal iid not already in inventory."""
    for _ in range(64):
        iid = str(random.randint(100000000, 4294967294))
        if iid not in APP_BY_IID:
            return iid
    return str(int(time.time() * 1000) % 4294967294)


def _next_default_name(apptype: str, prefix_override: str | None = None) -> str:
    """Copeland-style default: 'AHU 03', 'CIRCUIT 32', etc."""
    meta = _apptype_meta(apptype)
    prefix = (prefix_override or meta["name_prefix"] or "APP").strip() or "APP"
    existing = [
        a.get("appname") or a.get("name") or ""
        for a in INVENTORY_APPS
        if (a.get("apptype") or "") == apptype
    ]
    # Prefer sequential number after count of this type
    n = len(existing) + 1
    # Skip names already taken (custom names don't consume the number pattern)
    taken = {nm.strip().upper() for nm in existing}
    for _ in range(500):
        candidate = f"{prefix} {n:02d}"
        if candidate.upper() not in taken:
            return candidate
        n += 1
    return f"{prefix} {int(time.time()) % 10000:04d}"


def _register_new_app(
    apptype: str,
    *,
    name: str | None = None,
    category: str | None = None,
    src_ip: str = "",
    sid: str = "",
    username: str = "",
    method: str = "AddApp",
) -> dict[str, Any]:
    """Create in-memory app, point vals, log history; return inventory dict."""
    meta = _apptype_meta(apptype)
    cat = category or meta["category"]
    appname = name or _next_default_name(apptype)
    iid = _next_app_iid()
    extras: dict[str, Any] = {
        "device": bool(meta.get("device")),
        "devicetype": str(meta.get("devicetype") or ""),
    }
    if extras["device"] and extras["devicetype"]:
        extras["commissionable"] = 1
        if extras["devicetype"] == "Modbus":
            extras.setdefault("Route", "Modbus-01")
        elif extras["devicetype"] == "IONet":
            extras.setdefault("Route", "IONet-01")
        extras.setdefault("DevAddr", str(1 + sum(
            1 for a in INVENTORY_APPS
            if a.get("devicetype") == extras["devicetype"]
        )))
    app = make_app(iid, appname, apptype, cat, **extras)
    INVENTORY_APPS.append(app)
    APP_BY_IID[iid] = app
    vals = default_vals_for_app(app)
    vals["AppName"] = appname
    # Sensible AHU / circuit defaults for brand-new instances
    if apptype == "AHULarge":
        vals.setdefault("ActCtrlTemp", f"{f2c(72.0):.3f}")
        vals.setdefault("ActiveClStpt", f"{f2c(72.0):.3f}")
        vals.setdefault("OccState", "1")
        vals.setdefault("AHStatus", "0")
        vals.setdefault("ModHeatOut", "0.00")
        vals.setdefault("ModCoolOut", "15.00")
        vals.setdefault("Fan", "1")
        # Optional Point for sim jitter on new AHUs
        pt = Point(iid, appname, "AHULarge", "°F", 72.0, 72.0, 0.1, 0.04, "ACT CTRL TEMP", "temp")
        POINTS.append(pt)
        POINT_BY_PID[iid] = pt
        POINT_BY_NAME[appname] = pt
    elif apptype == "StdCircuit":
        vals.setdefault("CaseState", "0")
        vals.setdefault("ControlTemp", f"{f2c(30.0):.3f}")
        vals.setdefault("ActiveClStpt", f"{f2c(30.0):.3f}")
        vals.setdefault("Compressor", "1")
        vals.setdefault("Fan", "1")
        vals.setdefault("Defrost", "0")
        pt = Point(iid, appname, "StdCircuit", "°F", 30.0, 30.0, 0.12, 0.04, "CONTROL TEMP", "temp")
        POINTS.append(pt)
        POINT_BY_PID[iid] = pt
        POINT_BY_NAME[appname] = pt
    elif apptype == "Enhanced Suct":
        vals.setdefault("SuctionPres", "40.00")
        vals.setdefault("CurPresStpt", "40.00")
        vals.setdefault("StagesActive", "2")
        vals.setdefault("TotalStages", "6")
        vals.setdefault("PercentUsed", "33.00")
        vals.setdefault("RackFail", "0")
        for i in range(1, 10):
            vals.setdefault(f"StageOut{i}", "1" if i <= 2 else "0")
        pt = Point(iid, appname, "Enhanced Suct", "PSI", 40.0, 40.0, 0.08, 0.03, "SUCTION PRES", "psi")
        POINTS.append(pt)
        POINT_BY_PID[iid] = pt
        POINT_BY_NAME[appname] = pt
    elif apptype == "Condenser":
        vals.setdefault("CtrlValOut", "210.00")
        vals.setdefault("CtrlValStpt", "210.00")
        vals.setdefault("CondState", "0")
        vals.setdefault("SplitValve", "0")
    APP_POINT_VALS[iid] = vals
    try:
        log_history.seed_log_history_for_app(app, DASHBOARD, APP_POINT_VALS, SUCTIONS)
    except Exception as e:
        print(f"[addapp] log history seed failed: {e}", flush=True)
    # Warm GetAppDescription so device page has full ADF tabs immediately
    try:
        _app_description_for_iid(iid)
    except Exception as e:
        print(f"[addapp] description warm failed: {e}", flush=True)
    log_event(
        "app_add", src_ip, method,
        {"apptype": apptype, "iid": iid, "appname": appname, "category": cat},
        sid, username,
        extra={"iid": iid, "appname": appname, "apptype": apptype},
    )
    return app


def _unregister_app(iid: str, *, src_ip="", sid="", username="", method="RemoveApp") -> str:
    """Remove app from session inventory. Returns 'ok' or error token."""
    iid = str(iid)
    app = APP_BY_IID.get(iid)
    if not app:
        return "ok"  # already gone — SPA treats as success
    # Protect core system apps
    if app.get("apptype") in ("AreaCtrl", "SystemSettings", "Firmware Update", "SerialPortConfig"):
        return "error"
    INVENTORY_APPS[:] = [a for a in INVENTORY_APPS if str(a.get("iid")) != iid]
    APP_BY_IID.pop(iid, None)
    APP_POINT_VALS.pop(iid, None)
    pt = POINT_BY_PID.pop(iid, None)
    if pt:
        try:
            POINTS.remove(pt)
        except ValueError:
            pass
        POINT_BY_NAME.pop(pt.name, None)
    try:
        log_history.drop_log_history_for_iid(iid)
    except Exception:
        pass
    log_event(
        "app_remove", src_ip, method,
        {"iid": iid, "apptype": app.get("apptype"), "appname": app.get("appname")},
        sid, username,
        extra={"iid": iid},
    )
    return "ok"


def handle_GetAppTypes(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAppTypes", params, sid, username)
    seen: dict[str, dict[str, Any]] = {}
    # Prefer meta so device/devicetype/category are always present for SPA addApp
    for at, desc in APPDESC.items():
        meta = _apptype_meta(at)
        count = sum(1 for a in INVENTORY_APPS if (a.get("apptype") or "") == at)
        seen[at] = {
            "apptype": at,
            "appdesc": desc,
            "availinst": max(50 - count, 0),
            "category": meta["category"],
            "categorydef": meta["category"],
            "device": bool(meta["device"]),
            "devicetype": str(meta.get("devicetype") or ""),
        }
    # Include any inventory apptypes not in APPDESC
    for a in INVENTORY_APPS:
        at = a.get("apptype") or ""
        if at and at not in seen:
            meta = _apptype_meta(at)
            seen[at] = {
                "apptype": at,
                "appdesc": APPDESC.get(at, at),
                "availinst": 50,
                "category": a.get("category") or meta["category"],
                "categorydef": a.get("categorydef") or a.get("category") or meta["category"],
                "device": bool(a.get("device", meta["device"])),
                "devicetype": str(a.get("devicetype") if a.get("devicetype") is not None else meta.get("devicetype") or ""),
            }
    return {"apptypes": list(seen.values())}


def handle_AddApp(params, sid, src_ip, username):
    """Params: {apptype, appgroup?}. Result: {iid, appname} (SPA reads a.iid/a.appname)."""
    sid = ensure_session(sid, src_ip)
    p = params or {}
    apptype = str(p.get("apptype") or p.get("id") or "").strip()
    if not apptype:
        return {"err": "Missing apptype", "success": False}
    appgroup = p.get("appgroup") or p.get("category")
    category = str(appgroup) if appgroup else None
    # Map SPA category ids if needed
    if category in ("refrigeration", "hvac", "other", "system"):
        category = category[:1].upper() + category[1:]
    if category and category.lower() in ("refrigeration", "hvac", "other", "system"):
        category = {"refrigeration": "Refrigeration", "hvac": "HVAC",
                    "other": "Other", "system": "System"}[category.lower()]
    app = _register_new_app(
        apptype, category=category, src_ip=src_ip, sid=sid, username=username, method="AddApp",
    )
    return {"iid": app["iid"], "appname": app["appname"], "success": True}


def handle_AddApps(params, sid, src_ip, username):
    """Params: {apps:[{apptype, quantity, naming:{prefix}}]}.
    Result: [{apps:[{iid, appname}]}] matching SPA $_addLogGroup expectations."""
    sid = ensure_session(sid, src_ip)
    p = params or {}
    specs = p.get("apps") or []
    if not isinstance(specs, list):
        specs = []
    out = []
    for spec in specs:
        if not isinstance(spec, dict):
            out.append({"apps": [{"err": "invalid"}]})
            continue
        apptype = str(spec.get("apptype") or "").strip()
        try:
            qty = int(spec.get("quantity") or 1)
        except (TypeError, ValueError):
            qty = 1
        qty = max(1, min(qty, 20))
        naming = spec.get("naming") or {}
        prefix = None
        if isinstance(naming, dict):
            prefix = naming.get("prefix") or naming.get("name")
        created = []
        for i in range(qty):
            if prefix and qty == 1:
                name = str(prefix)
            elif prefix:
                name = _next_default_name(apptype, str(prefix))
            else:
                name = None
            # Avoid duplicate exact names when prefix given once
            if name and any((a.get("appname") or "") == name for a in INVENTORY_APPS):
                name = _next_default_name(apptype, str(prefix) if prefix else None)
            app = _register_new_app(
                apptype, name=name, src_ip=src_ip, sid=sid, username=username, method="AddApps",
            )
            created.append({"iid": app["iid"], "appname": app["appname"]})
        out.append({"apps": created})
    return out


def handle_DuplicateApp(params, sid, src_ip, username):
    """Params: {iid, count}. SPA then fetchInventory()."""
    sid = ensure_session(sid, src_ip)
    p = params or {}
    src_iid = str(p.get("iid") or "")
    try:
        count = int(p.get("count") or 1)
    except (TypeError, ValueError):
        count = 1
    count = max(1, min(count, 20))
    src = APP_BY_IID.get(src_iid)
    if not src:
        return {"err": "App not found", "apps": []}
    apptype = src.get("apptype") or ""
    created = []
    for _ in range(count):
        app = _register_new_app(
            apptype,
            category=src.get("category"),
            src_ip=src_ip, sid=sid, username=username, method="DuplicateApp",
        )
        # Copy point vals from source where sensible
        src_vals = APP_POINT_VALS.get(src_iid) or {}
        dst = APP_POINT_VALS.setdefault(app["iid"], {})
        for k, v in src_vals.items():
            if k == "AppName":
                continue
            dst.setdefault(k, v)
        dst["AppName"] = app["appname"]
        created.append({"iid": app["iid"], "appname": app["appname"]})
    log_event(
        "app_duplicate", src_ip, "DuplicateApp",
        {"iid": src_iid, "count": count, "created": [c["iid"] for c in created]},
        sid, username,
    )
    return {"apps": created, "success": True}


def handle_RemoveApp(params, sid, src_ip, username):
    """Params: {iid}."""
    sid = ensure_session(sid, src_ip)
    p = params or {}
    iid = str(p.get("iid") or "")
    status = _unregister_app(iid, src_ip=src_ip, sid=sid, username=username, method="RemoveApp")
    if status != "ok":
        return {"success": False, "err": status, "iid": iid}
    return {"success": True, "iid": iid}


def handle_RemoveApps(params, sid, src_ip, username):
    """Params: {iids:[...]}. Result: {iid: 'ok'|'error', ...}."""
    sid = ensure_session(sid, src_ip)
    p = params or {}
    iids = p.get("iids") or []
    if not isinstance(iids, list):
        iids = [iids] if iids else []
    result = {}
    for raw in iids:
        iid = str(raw.get("iid") if isinstance(raw, dict) else raw)
        result[iid] = _unregister_app(
            iid, src_ip=src_ip, sid=sid, username=username, method="RemoveApps",
        )
    return result


def handle_GetAlarmStatus(params, sid, src_ip, username):
    """Params: {apps:[{iid},...]}. Response: {apps:[{iid, alarmstate?}]}."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAlarmStatus", params, sid, username)
    apps_in = (params or {}).get("apps") or []
    out = []
    for item in apps_in:
        iid = str(item.get("iid") if isinstance(item, dict) else item)
        # Optional advisory state for meat case when value high
        pt = POINT_BY_PID.get(iid)
        entry = {"iid": iid}
        if pt and pt.value > pt.setpoint + 1.5:
            entry["alarmstate"] = "alm"
        out.append(entry)
    return {"apps": out}


def handle_GetTagFile(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetTagFile", params, sid, username)
    return {"tags": [], "filename": None}


def handle_GetDefaultLogGroup(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetDefaultLogGroup", params, sid, username)
    base = next((a for a in INVENTORY_APPS if a.get("apptype") == "Log Group"), None)
    iid = str(base["iid"]) if base else _iid("Base Log")
    return {"lgriid": [iid]}


def handle_GetPointsForLogGroup(params, sid, src_ip, username):
    """Return every dashboard point ptr so device graphs default-select tile points."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetPointsForLogGroup", params, sid, username)
    return {"points": log_history.all_log_ptrs()}


def handle_GetAppsForLogGroup(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAppsForLogGroup", params, sid, username)
    return log_history.apps_for_log_group()


def handle_GetUserSelectedGraphPoints(params, sid, src_ip, username):
    """Empty/null graph_points => SPA falls back to tile defaultSelectedPoints."""
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetUserSelectedGraphPoints", params, sid, username)
    return {}


def handle_SetUserSelectedGraphPoints(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("config_change", src_ip, "SetUserSelectedGraphPoints", params, sid, username)
    return {"success": True}


def handle_GetLogGroupSummary(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetLogGroupSummary", params, sid, username)
    # SPA reads .space for logging storage meter
    used = min(95.0, 12.0 + log_history.series_count() / 50.0)
    return {"space": {"used_pct": round(used, 1), "used": int(used), "total": 100}}


def handle_GetAppRegisteredLogPoints(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAppRegisteredLogPoints", params, sid, username)
    iid = str((params or {}).get("iid") or "")
    pts = []
    for ptr in log_history.all_log_ptrs():
        if ptr["ptr"].startswith(iid + ":"):
            pts.append(ptr)
    return {"points": pts}


def handle_GetSAGraphPoints(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetSAGraphPoints", params, sid, username)
    return {"points": []}


def handle_GetAppLogManifest(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAppLogManifest", params, sid, username)
    return {"logtype": "pointList", "points": []}


def handle_GetAppLogData(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAppLogData", params, sid, username)
    return {"points": []}


def handle_GetLogData(params, sid, src_ip, username):
    """Build binary Base Log payload for dygraphs (returned raw by mgw_cgi)."""
    sid = ensure_session(sid, src_ip)
    p = params or {}
    log_event("recon", src_ip, "GetLogData",
              {"lgiid": p.get("lgiid"), "appiid": p.get("appiid"), "pntid": p.get("pntid"),
               "start": p.get("start"), "end": p.get("end")},
              sid, username)
    lgiid = p.get("lgiid") or "539799930"
    appiid = str(p.get("appiid") or "")
    pid = str(p.get("pntid") or "")
    if not appiid or not pid:
        return log_history.empty_log_binary(lgiid, appiid or 0, pid)

    start = p.get("start")
    end = p.get("end")
    try:
        start_i = int(start) if start is not None else None
    except (TypeError, ValueError):
        start_i = None
    try:
        end_i = int(end) if end is not None else None
    except (TypeError, ValueError):
        end_i = None

    samples, meta = log_history.query_samples(
        appiid, pid,
        start=start_i, end=end_i,
        index=p.get("index"),
        direction=int(p.get("direction") or 0),
        total_hint=p.get("total"),
        idxtime=p.get("idxtime"),
        duration=p.get("duration"),
    )
    return log_history.pack_log_binary(lgiid, appiid, pid, samples, meta)


def handle_GetAggregationSubCategoriesApps(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetAggregationSubCategoriesApps", params, sid, username)
    return {"apps": []}


def handle_GetParents(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetParents", params, sid, username)
    return {"parents": []}


def handle_GetDeviceDetail(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetDeviceDetail", params, sid, username)
    p = params or {}
    iid = str(p.get("iid") or p.get("pid") or "")
    pt = POINT_BY_PID.get(iid)
    app = next((a for a in INVENTORY_APPS if str(a.get("iid")) == iid), None)
    if pt:
        return {
            "iid": pt.pid, "name": pt.name, "apptype": pt.apptype,
            "points": [
                {"pid": pt.pid, "name": pt.point_label, "value": round(pt.value, 2),
                 "setpoint": round(pt.setpoint, 2), "eu": pt.eu, "writable": True},
                {"pid": pt.pid + "-hi", "name": "Case Temp Hi Limit", "value": round(pt.setpoint + 2.0, 2),
                 "setpoint": round(pt.setpoint + 2.0, 2), "eu": pt.eu, "writable": True},
                {"pid": pt.pid + "-lo", "name": "Case Temp Lo Limit", "value": round(pt.setpoint - 3.0, 2),
                 "setpoint": round(pt.setpoint - 3.0, 2), "eu": pt.eu, "writable": True},
            ],
            "state": _circuit_state(pt) if pt.apptype == "StdCircuit" else "Online",
        }
    if app:
        return {"iid": app["iid"], "name": app["name"], "apptype": app["apptype"],
                "points": [], "state": "Online", "device": app.get("device", False)}
    return {"error": "Not found", "iid": iid}




def handle_GetSetupWizardStatus(params, sid, src_ip, username):
    sid = ensure_session(sid, src_ip)
    log_event("recon", src_ip, "GetSetupWizardStatus", params, sid, username)
    # SPA does s.setup.hasOwnProperty(pageKey); missing -> throws -> boot hangs on loader.
    # All pages complete => isIncomplete=false => no setup wizard, lands on System Summary.
    return {"setup": {"localization": True, "generalvalues": True, "internetvalues": True},
            "status": False}



def handle_GetHelpFile(params, sid, src_ip, username):
    """Unauthenticated decoy RPC (SS-HONEY-2026-01 adjacent to unauth file-read CVEs).

    Params: {name}. Never reads the real filesystem. Path-looking names get a fake
    HTML blob and classification path_traversal_probe.
    """
    # Soft session ok but not required — scanners often omit sid
    if sid:
        sid = ensure_session(sid, src_ip)
    p = params or {}
    name = str(p.get("name") or p.get("file") or p.get("path") or "")
    result = novel_vulns.help_file_response(name)
    if novel_vulns.is_path_probe(name):
        log_event(
            "path_traversal_probe", src_ip, "GetHelpFile",
            {"name": name, "decoy_id": novel_vulns.DECOY_ID},
            sid or "", username or "",
            extra={"decoy_id": novel_vulns.DECOY_ID},
        )
    else:
        log_event("recon", src_ip, "GetHelpFile", {"name": name}, sid or "", username or "")
    # Do not leak internal _decoy marker as a required field; keep decoy_id for analysts
    out = {k: v for k, v in result.items() if not k.startswith("_")}
    return out



HANDLERS = {
    "GetSessionID": handle_GetSessionID,
    "TouchSession": handle_TouchSession,
    "Login": handle_Login,
    "GetHelpFile": handle_GetHelpFile,
    "Logout": handle_Logout,
    "GetSystemInformation": handle_GetSystemInformation,
    "GetSystemInventory": handle_GetSystemInventory,
    "GetAlarms": handle_GetAlarms,
    "GetAlarmStatus": handle_GetAlarmStatus,
    "GetPointValues": handle_GetPointValues,
    "GetRealTimePointsData": handle_GetRealTimePointsData,
    "RegisterPoint": handle_RegisterPoint,
    "UnregisterPoint": handle_UnregisterPoint,
    "GetPointsDescription": handle_GetPointsDescription,
    "GetAppDescription": handle_GetAppDescription,
    "GetAppCommands": handle_GetAppCommands,
    "GetAppTypes": handle_GetAppTypes,
    "AddApp": handle_AddApp,
    "AddApps": handle_AddApps,
    "DuplicateApp": handle_DuplicateApp,
    "RemoveApp": handle_RemoveApp,
    "RemoveApps": handle_RemoveApps,
    "GetUserSelectedTilePoints": handle_GetUserSelectedTilePoints,
    "GetDashboardSummaryProps": handle_GetDashboardSummaryProps,
    "GetGroups": handle_GetGroups,
    "GetAggregationSubCategoriesApps": handle_GetAggregationSubCategoriesApps,
    "GetHomeScreenState": handle_GetHomeScreenState,
    "GetProfile": handle_GetProfile,
    "GetLicenses": handle_GetLicenses,
    "GetLayouts": handle_GetLayouts,
    "GetUnitList": handle_GetUnitList,
    "GetTimezoneInfo": handle_GetTimezoneInfo,
    "GetSetupWizardStatus": handle_GetSetupWizardStatus,
    "SetPointValues": handle_SetPointValues,
    "GetDefrostSummary": handle_GetDefrostSummary,
    "GetNetworkSummary": handle_GetNetworkSummary,
    "GetSchedules": handle_GetSchedules,
    "SetSchedule": handle_SetSchedule,
    "GetUsers": handle_GetUsers,
    "GetSessions": handle_GetSessions,
    "AddUser": handle_AddUser,
    "GetLogs": handle_GetLogs,
    "GetLogGroups": handle_GetLogGroups,
    "GetDefaultLogGroup": handle_GetDefaultLogGroup,
    "GetPointsForLogGroup": handle_GetPointsForLogGroup,
    "GetAppsForLogGroup": handle_GetAppsForLogGroup,
    "GetLogData": handle_GetLogData,
    "GetUserSelectedGraphPoints": handle_GetUserSelectedGraphPoints,
    "SetUserSelectedGraphPoints": handle_SetUserSelectedGraphPoints,
    "GetLogGroupSummary": handle_GetLogGroupSummary,
    "GetAppRegisteredLogPoints": handle_GetAppRegisteredLogPoints,
    "GetSAGraphPoints": handle_GetSAGraphPoints,
    "GetAppLogManifest": handle_GetAppLogManifest,
    "GetAppLogData": handle_GetAppLogData,
    "GetTagFile": handle_GetTagFile,
    "GetParents": handle_GetParents,
    "AcknowledgeAlarm": handle_AcknowledgeAlarm,
    "ResetAlarm": handle_ResetAlarm,
    "GetPhysicalIOStatus": handle_GetPhysicalIOStatus,
    "GetGeneralSystem": handle_GetGeneralSystem,
    "SetGeneralSystem": handle_SetGeneralSystem,
    "GetProtocolMapping": handle_GetProtocolMapping,
    "GetFloorPlan": handle_GetFloorPlan,
    "GetDeviceDetail": handle_GetDeviceDetail,
}


def dispatch_rpc(payload, src_ip, sid_hint):
    method = payload.get("method") or ""
    params = payload.get("params")
    req_id = payload.get("id")
    sid = sid_hint or ""
    if isinstance(params, dict) and params.get("sid"):
        sid = str(params.get("sid"))
    username = SESSIONS.get(sid, {}).get("username", "") if sid else ""
    if method not in HANDLERS:
        # Soft stub: SPA probes many Get* methods; empty result keeps UI alive.
        log_event("recon", src_ip, method or "unknown", params, sid, username, extra={"note": "stubbed"})
        if method.startswith("Get") or method.startswith("get"):
            return {"jsonrpc": "2.0", "result": {}, "id": req_id}
        if method.startswith("Set") or method.startswith("Add") or method.startswith("Remove") or method in (
            "OverridePoint", "SendPointValues", "UserAction", "Backup", "Restore", "SystemReset",
        ):
            log_event("config_change", src_ip, method, params, sid, username, extra={"note": "stubbed_write"})
            return {"jsonrpc": "2.0", "result": {"success": True, "ok": True}, "id": req_id}
        return {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": req_id}
    try:
        result = HANDLERS[method](params, sid, src_ip, username)
        return {"jsonrpc": "2.0", "result": result, "id": req_id}
    except Exception as e:
        log_event("recon", src_ip, method, params, sid, username, extra={"error": str(e)})
        return {"jsonrpc": "2.0", "error": {"code": -32000, "message": str(e)}, "id": req_id}


async def parse_mgw_payload(request):
    sid_hint = request.rel_url.query.get("sid") or request.cookies.get("sid")
    payload = None
    if request.method == "POST":
        ctype = (request.content_type or "")
        if "json" in ctype:
            try:
                payload = await request.json()
            except Exception:
                payload = None
        elif "multipart" in ctype:
            data = await request.post()
            m = data.get("m") or data.get("json") or data.get("rpc")
            if m:
                payload = json.loads(m) if isinstance(m, (str, bytes)) else m
            if not sid_hint:
                sid_hint = data.get("sid")
        else:
            raw = await request.read()
            body = raw.decode("utf-8", errors="replace")
            if body:
                try:
                    payload = json.loads(body)
                except Exception:
                    qs = parse_qs(body)
                    if "m" in qs:
                        try:
                            payload = json.loads(qs["m"][0])
                        except Exception:
                            pass
                    if not sid_hint and "sid" in qs:
                        sid_hint = qs["sid"][0]
    else:
        m = request.rel_url.query.get("m")
        if m:
            try:
                payload = json.loads(m)
            except Exception:
                payload = None
    return payload, sid_hint


async def mgw_cgi(request):
    global _REQUEST_UA, _REQUEST_IP
    src_ip = request.headers.get("X-Forwarded-For", request.remote or "0.0.0.0").split(",")[0].strip()
    _REQUEST_IP = src_ip
    _REQUEST_UA = request.headers.get("User-Agent", "") or ""
    payload, sid_hint = await parse_mgw_payload(request)
    if not payload or not isinstance(payload, dict):
        log_event("recon", src_ip, "mgw.cgi", {"raw": "invalid"}, sid_hint or "")
        return web.json_response({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})
    # GetLogData is raw binary (SPA responseType:arraybuffer) — not JSON-RPC wrapped
    if payload.get("method") == "GetLogData":
        sid = sid_hint or ""
        if isinstance(payload.get("params"), dict) and payload["params"].get("sid"):
            sid = str(payload["params"]["sid"])
        username = SESSIONS.get(sid, {}).get("username", "") if sid else ""
        body = handle_GetLogData(payload.get("params"), sid, src_ip, username)
        if not isinstance(body, (bytes, bytearray)):
            body = log_history.empty_log_binary()
        return web.Response(
            body=bytes(body),
            content_type="application/octet-stream",
            headers={"Content-Transfer-Encoding": "binary"},
        )

    result = dispatch_rpc(payload, src_ip, sid_hint)
    resp = web.json_response(result)
    r = result.get("result") or {}
    if isinstance(r, dict) and r.get("sid"):
        resp.set_cookie("sid", r["sid"], path="/")
    return resp


async def cgi_stub(request):
    src_ip = request.headers.get("X-Forwarded-For", request.remote or "0.0.0.0").split(",")[0].strip()
    name = request.match_info.get("name", "unknown")
    classification = "upload_attempt" if ("upl" in name.lower() or "G4upl" in name) else "recon"
    log_event(classification, src_ip, f"cgi-bin/{name}", {"method": request.method, "qs": dict(request.rel_url.query)})
    if "dl" in name:
        return web.json_response({"error": "Invalid Download Type"})
    if "lpolling" in name:
        return web.json_response({"ok": True, "events": []})
    if "tm" in name:
        return web.json_response({"time": _now()})
    if "upl" in name.lower() or "G4upl" in name:
        return web.json_response({"error": "Upload not permitted", "code": 403})
    return web.json_response({"error": "Not supported"})


def _points_frame():
    """Websocket push: dashboard points for EVERY inventory app (fake controller)."""
    pts = []
    # Keep Point-backed analogs in sync first
    for p in POINTS:
        _sync_live_summary_vals(p.pid)
    for app in INVENTORY_APPS:
        iid = str(app["iid"])
        apptype = app.get("apptype") or ""
        dash = DASHBOARD.get(apptype) or {}
        store = APP_POINT_VALS.get(iid) or {}
        for dp in dash.get("points") or []:
            pid = dp["pid"]
            meta = _point_meta(pid)
            val = store.get(pid, "0")
            dtype = meta.get("dtype") or "float"
            if pid in LIST_SELECTIONS or dtype == "dig":
                dtype = "list"
            elif pid in ("AppName", "PortName", "SiteName", "UnitName", "FwVersion",
                         "FwStatus", "DisplayStatus", "CP^Category"):
                dtype = "str"
            rec = {
                "ptr": f"{iid}:{pid}",
                "val": str(val),
                "status": "0",
                "class": meta.get("class") or "",
                "dtype": dtype,
                "adv": [],
            }
            if dtype == "float":
                rec["prec"] = meta.get("prec", 1)
            pts.append(rec)
    return {"points": pts, "unitnum": "1", "time": _now()}


async def broadcast_points():
    if not WS_CLIENTS:
        return
    msg = json.dumps(_points_frame())
    dead = []
    for ws in list(WS_CLIENTS):
        try:
            await ws.send_str(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        WS_CLIENTS.discard(ws)


async def ws_stream(request):
    src_ip = request.headers.get("X-Forwarded-For", request.remote or "0.0.0.0").split(",")[0].strip()
    sid = ensure_session(request.rel_url.query.get("sid") or None, src_ip)
    log_event("recon", src_ip, "WebSocket /stream", {"sid": sid}, sid)
    ws = web.WebSocketResponse(heartbeat=30)
    await ws.prepare(request)
    WS_CLIENTS.add(ws)
    # Push an initial points frame + time so tiles get values immediately on subscribe.
    try:
        await ws.send_str(json.dumps(_points_frame()))
        await ws.send_str(json.dumps({"time": _now(), "unitnum": "1"}))
    except Exception:
        pass
    try:
        async for msg in ws:
            # Stream is server->client only on the real device; just keep it open.
            if msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break
    finally:
        WS_CLIENTS.discard(ws)
    return ws


async def sim_loop(app):
    """Fake controller: tick every analog and push /stream for all System Tile apps."""
    while True:
        for p in POINTS:
            p.tick()
            _sync_live_summary_vals(p.pid)
        # Jitter remaining inventory analogs (Other / System / RLDS / ESR valves, etc.)
        for iid, store in list(APP_POINT_VALS.items()):
            if iid in POINT_BY_PID:
                continue
            for pid, val in list(store.items()):
                kind = log_history.classify_pid(pid)
                if kind in ("temp", "psi", "pct", "float") and val not in (None, "", "N0n3"):
                    try:
                        f = float(val)
                    except (TypeError, ValueError):
                        continue
                    f2 = f + random.uniform(-0.05, 0.05)
                    if kind == "pct":
                        f2 = max(0.0, min(100.0, f2))
                    store[pid] = f"{f2:.3f}" if kind == "temp" else f"{f2:.2f}"
        log_history.append_live_samples(APP_POINT_VALS)
        await broadcast_points()
        await asyncio.sleep(3.0)


async def on_startup(app):
    base = next((a for a in INVENTORY_APPS if a.get("apptype") == "Log Group"), None)
    base_iid = str(base["iid"]) if base else "539799930"
    log_history.init_log_history(
        INVENTORY_APPS, DASHBOARD, APP_POINT_VALS, SUCTIONS, base_log_iid=base_iid,
    )
    app["sim_task"] = asyncio.create_task(sim_loop(app))
    print(f"Site Supervisor honeypot on 0.0.0.0:{PORT} (maplewood / E3 CXe)", flush=True)
    print(f"  SPA (mirrored Site Supervisor, no login): http://127.0.0.1:{PORT}/", flush=True)
    print(f"  Static root: {STATIC}", flush=True)
    print(f"  JSON-RPC: POST http://127.0.0.1:{PORT}/cgi-bin/mgw.cgi", flush=True)
    print(f"  Base Log series: {log_history.series_count()}  samples/series≈{log_history.MAX_SAMPLES}", flush=True)
    print(f"  Logs: {LOG_PATH}", flush=True)


async def on_cleanup(app):
    t = app.get("sim_task")
    if t:
        t.cancel()


async def index(request):
    # Serve the mirrored live SPA shell (no login wall). Hash routes stay client-side.
    spa = STATIC / "index.html"
    if spa.exists():
        return web.Response(text=spa.read_text(encoding="utf-8"), content_type="text/html")
    if SUMMARY_PATH.exists():
        return web.Response(text=SUMMARY_PATH.read_text(encoding="utf-8"), content_type="text/html")
    return web.Response(text="<h1>Site Supervisor</h1><p>index missing</p>", content_type="text/html")


async def spa_shell(request):
    return await index(request)


def create_app():
    app = web.Application(middlewares=[middleware_access(), middleware_headers()])
    app.router.add_get("/", index)
    app.router.add_get("/summary", index)
    app.router.add_get("/spa", spa_shell)
    app.router.add_route("*", "/cgi-bin/mgw.cgi", mgw_cgi)
    app.router.add_route("*", "/cgi-bin/{name}", cgi_stub)
    app.router.add_get("/stream", ws_stream)
    # Static assets from wget mirror (js/css/images/fonts)
    for sub in ("images", "js", "css", "fonts", "static-json"):
        path = STATIC / sub
        if path.is_dir():
            app.router.add_static(f"/{sub}/", path=str(path), show_index=False)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Peer-unit URL prefix used by SPA (/unit1/cgi-bin/mgw.cgi). Same handlers.
    async def _unit_mgw(request):
        return await mgw_cgi(request)
    async def _unit_stream(request):
        return await ws_stream(request)
    async def _unit_cgi(request):
        return await cgi_stub(request)
    async def _unit_index(request):
        return await index(request)
    app.router.add_route("*", "/unit{num}/cgi-bin/mgw.cgi", _unit_mgw)
    app.router.add_route("*", "/unit{num}/cgi-bin/{name}", _unit_cgi)
    app.router.add_get("/unit{num}/stream", _unit_stream)
    app.router.add_get("/unit{num}/", _unit_index)
    app.router.add_get("/unit{num}", _unit_index)
    return app


def main():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    # aiohttp sets Server by default; suppress via handler
    web.run_app(create_app(), host="0.0.0.0", port=PORT, print=lambda *_: None)


if __name__ == "__main__":
    main()
