"""Synthetic Base Log time-series for the Site Supervisor honeypot.

Generates ~24h of per-point samples locally. Never contacts real devices.
"""
from __future__ import annotations

import hashlib
import math
import random
import struct
import time
import zlib
from typing import Any

# Log cadence matching real Base Log
LOG_INTERVAL = 60  # seconds
HISTORY_SEC = 86400  # 24 hours
MAX_SAMPLES = HISTORY_SEC // LOG_INTERVAL  # 1440

# Binary GetLogData valueType
VT_FLOAT = 1
VT_UINT = 2
VT_DIG = 3

# Compact in-memory series: key "(iid):(pid)" -> list[(ts, val)]
# dig/uint stored as int; float as float
_SERIES: dict[str, list[tuple[int, float]]] = {}
_SERIES_META: dict[str, dict[str, Any]] = {}  # value_type, base, noise, kind
_LAST_APPEND_TS = 0
_BASE_LOG_IID = "539799930"


def _rng(seed: str) -> random.Random:
    h = hashlib.md5(seed.encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def _key(iid: str, pid: str) -> str:
    return f"{iid}:{pid}"


def pid_crc32(pid: str) -> int:
    return zlib.crc32(pid.encode("utf-8")) & 0xFFFFFFFF


def classify_pid(pid: str, dtype: str | None = None, cls: str | None = None) -> str:
    """Return 'dig' | 'temp' | 'psi' | 'pct' | 'uint' | 'float' | 'str'."""
    if dtype == "dig" or pid.startswith("StageOut") or pid.startswith("FanOut") or pid in (
        "Compressor", "Fan", "Defrost", "Online", "LightsOutput", "RefrigOut",
        "DefrostOut", "FanOut", "CoolOut",
    ):
        return "dig"
    if dtype == "uint" or pid in (
        "StagesActive", "TotalStages", "ActiveZone", "BaudRate", "UnitNumber",
        "LogInterval", "FanStages",
    ):
        return "uint"
    if dtype == "str" or pid in (
        "AppName", "SiteName", "UnitName", "PortName", "FwVersion", "FwStatus",
        "DisplayStatus", "CP^Category",
    ):
        return "str"
    if cls == "temp" or pid in (
        "ControlTemp", "ActiveClStpt", "ActCtrlTemp", "CASE_TEMP", "CaseTempStpt",
        "SUPPLY_TEMP", "SUPPLY_STPT", "SENSOR_VALUE", "TCtrlValOut", "TCtrlValStpt",
        "AI1", "AI2",
    ):
        return "temp"
    if pid in ("SuctionPres", "CurPresStpt", "CtrlValOut", "CtrlValStpt", "FastRecStpt", "FastRecIn"):
        return "psi"
    if pid in ("PercentUsed", "ModHeatOut", "ModCoolOut", "CtrlPid") or pid.startswith("ValvePos"):
        return "pct"
    return "float"


def _value_type_for(kind: str) -> int:
    if kind == "dig":
        return VT_DIG
    if kind == "uint":
        return VT_UINT
    return VT_FLOAT


def _seed_value(iid: str, pid: str, kind: str, store_val: str | None) -> float:
    """Initial / base value for a series."""
    if store_val is not None and store_val not in ("", "N0n3"):
        try:
            if kind == "dig":
                return 1.0 if str(store_val) in ("1", "On", "ON", "true") else 0.0
            return float(store_val)
        except (TypeError, ValueError):
            pass
    r = _rng(f"base:{iid}:{pid}")
    if kind == "dig":
        return float(r.choice([0, 1]))
    if kind == "temp":
        # Celsius on wire (typical case/room)
        return r.uniform(-22.0, 25.0)
    if kind == "psi":
        return r.uniform(15.0, 220.0)
    if kind == "pct":
        return r.uniform(0.0, 100.0)
    if kind == "uint":
        return float(r.randint(0, 9))
    return r.uniform(0.0, 100.0)


def _noise_for(kind: str) -> float:
    return {
        "dig": 0.0,
        "temp": 0.08,
        "psi": 0.12,
        "pct": 0.35,
        "uint": 0.0,
        "float": 0.2,
        "str": 0.0,
    }.get(kind, 0.15)


def _gen_history(
    iid: str,
    pid: str,
    kind: str,
    base: float,
    now_ts: int,
    stages_pattern: tuple[int, ...] | None = None,
) -> list[tuple[int, float]]:
    """Generate HISTORY_SEC of samples ending at now_ts (aligned to LOG_INTERVAL)."""
    if kind == "str":
        return []
    end = now_ts - (now_ts % LOG_INTERVAL)
    start = end - (MAX_SAMPLES - 1) * LOG_INTERVAL
    r = _rng(f"hist:{iid}:{pid}")
    noise = _noise_for(kind)
    out: list[tuple[int, float]] = []
    # Slow diurnal / load swing
    for i in range(MAX_SAMPLES):
        ts = start + i * LOG_INTERVAL
        hour = (ts % 86400) / 3600.0
        diurnal = math.sin((hour - 6) / 24.0 * 2 * math.pi)
        if kind == "dig":
            if stages_pattern is not None:
                # pid StageOutN -> N
                try:
                    n = int(pid.replace("StageOut", "").replace("FanOut", "") or "0")
                except ValueError:
                    n = 0
                on = 1.0 if n in stages_pattern else 0.0
                # rare flicker
                if r.random() < 0.002:
                    on = 1.0 - on
                val = on
            else:
                # mostly sticky around base, rare flips
                val = base
                if r.random() < 0.003:
                    val = 1.0 - val
                    base = val
        elif kind == "uint":
            val = base
            if r.random() < 0.01:
                val = max(0, min(16, base + r.choice([-1, 0, 1])))
                base = val
        elif kind == "temp":
            # gentle walk + diurnal (~0.5C)
            base += r.uniform(-0.03, 0.03)
            val = base + diurnal * 0.4 + r.uniform(-noise, noise)
        elif kind == "psi":
            base += r.uniform(-0.05, 0.05)
            val = max(0.0, base + diurnal * 1.2 + r.uniform(-noise, noise))
        elif kind == "pct":
            base = max(0.0, min(100.0, base + r.uniform(-0.4, 0.4)))
            val = max(0.0, min(100.0, base + diurnal * 5.0 + r.uniform(-noise, noise)))
        else:
            base += r.uniform(-0.05, 0.05)
            val = base + r.uniform(-noise, noise)
        out.append((ts, float(val)))
    return out


def init_log_history(
    inventory_apps: list[dict],
    dashboard: dict,
    app_point_vals: dict[str, dict[str, str]],
    suctions: list,
    base_log_iid: str = "539799930",
) -> None:
    """Seed ~24h of history for every dashboard point on every app."""
    global _SERIES, _SERIES_META, _LAST_APPEND_TS, _BASE_LOG_IID
    _BASE_LOG_IID = str(base_log_iid)
    _SERIES = {}
    _SERIES_META = {}
    now_ts = int(time.time())
    _LAST_APPEND_TS = now_ts - (now_ts % LOG_INTERVAL)

    suction_stages = {
        str(iid): stages_on for iid, _n, _p, _s, _a, _t, _pct, stages_on in suctions
    }

    for app in inventory_apps:
        iid = str(app["iid"])
        apptype = app.get("apptype") or ""
        dash = dashboard.get(apptype) or {}
        store = app_point_vals.get(iid) or {}
        stages = suction_stages.get(iid)
        for p in dash.get("points") or []:
            pid = p["pid"]
            kind = classify_pid(pid, p.get("dtype"), p.get("class"))
            if kind == "str":
                continue
            base = _seed_value(iid, pid, kind, store.get(pid))
            # Prefer live store for dig stage pattern consistency
            hist = _gen_history(iid, pid, kind, base, now_ts, stages if pid.startswith(("StageOut", "FanOut")) else None)
            # Snap last sample to current store value so Status matches graph end
            if hist and store.get(pid) is not None and store.get(pid) != "N0n3":
                try:
                    if kind == "dig":
                        cur = 1.0 if str(store[pid]) in ("1", "On", "ON") else 0.0
                    else:
                        cur = float(store[pid])
                    ts_last, _ = hist[-1]
                    hist[-1] = (ts_last, cur)
                    base = cur
                except (TypeError, ValueError):
                    pass
            k = _key(iid, pid)
            _SERIES[k] = hist
            _SERIES_META[k] = {
                "value_type": _value_type_for(kind),
                "kind": kind,
                "base": base,
                "noise": _noise_for(kind),
            }



def seed_log_history_for_app(
    app: dict,
    dashboard: dict,
    app_point_vals: dict[str, dict[str, str]],
    suctions: list | None = None,
) -> int:
    """Append ~24h history for one newly created app. Returns series count added."""
    global _SERIES, _SERIES_META
    iid = str(app["iid"])
    apptype = app.get("apptype") or ""
    dash = dashboard.get(apptype) or {}
    store = app_point_vals.get(iid) or {}
    suction_stages = None
    if suctions:
        for row in suctions:
            if str(row[0]) == iid:
                suction_stages = row[-1]
                break
    now_ts = int(time.time())
    added = 0
    for p in dash.get("points") or []:
        pid = p["pid"]
        kind = classify_pid(pid, p.get("dtype"), p.get("class"))
        if kind == "str":
            continue
        base = _seed_value(iid, pid, kind, store.get(pid))
        stages = suction_stages if pid.startswith(("StageOut", "FanOut")) else None
        hist = _gen_history(iid, pid, kind, base, now_ts, stages)
        if hist and store.get(pid) is not None and store.get(pid) != "N0n3":
            try:
                if kind == "dig":
                    cur = 1.0 if str(store[pid]) in ("1", "On", "ON") else 0.0
                else:
                    cur = float(store[pid])
                ts_last, _ = hist[-1]
                hist[-1] = (ts_last, cur)
                base = cur
            except (TypeError, ValueError):
                pass
        k = _key(iid, pid)
        _SERIES[k] = hist
        _SERIES_META[k] = {
            "value_type": _value_type_for(kind),
            "kind": kind,
            "base": base,
            "noise": _noise_for(kind),
        }
        added += 1
    return added


def drop_log_history_for_iid(iid: str) -> int:
    """Remove all series for an iid. Returns count removed."""
    global _SERIES, _SERIES_META
    iid = str(iid)
    keys = [k for k in list(_SERIES.keys()) if k.startswith(iid + ":")]
    for k in keys:
        _SERIES.pop(k, None)
        _SERIES_META.pop(k, None)
    return len(keys)



def all_log_ptrs() -> list[dict[str, str]]:
    """GetPointsForLogGroup points list: [{ptr: 'iid:pid'}, ...]."""
    return [{"ptr": k} for k in sorted(_SERIES.keys())]


def apps_for_log_group() -> dict[str, Any]:
    """GetAppsForLogGroup payload."""
    by_app: dict[str, list[str]] = {}
    for k in _SERIES:
        iid, _, pid = k.partition(":")
        by_app.setdefault(iid, []).append(pid)
    allpoints = [{"iid": iid, "pids": pids} for iid, pids in by_app.items()]
    return {"allpoints": allpoints, "apps": [{"iid": iid} for iid in by_app]}


def series_count() -> int:
    return len(_SERIES)


def sample_count(iid: str | None = None, pid: str | None = None) -> int:
    if iid and pid:
        return len(_SERIES.get(_key(iid, pid), []))
    return sum(len(v) for v in _SERIES.values())


def append_live_samples(app_point_vals: dict[str, dict[str, str]], now_ts: int | None = None) -> int:
    """Append one sample per series when a new LOG_INTERVAL bucket elapses. Returns # appended."""
    global _LAST_APPEND_TS
    now_ts = int(now_ts or time.time())
    bucket = now_ts - (now_ts % LOG_INTERVAL)
    if bucket <= _LAST_APPEND_TS:
        return 0
    _LAST_APPEND_TS = bucket
    n = 0
    for k, meta in _SERIES_META.items():
        iid, _, pid = k.partition(":")
        store = app_point_vals.get(iid) or {}
        kind = meta["kind"]
        series = _SERIES.setdefault(k, [])
        val = meta.get("base", 0.0)
        raw = store.get(pid)
        if raw is not None and raw != "N0n3":
            try:
                if kind == "dig":
                    val = 1.0 if str(raw) in ("1", "On", "ON") else 0.0
                else:
                    val = float(raw)
            except (TypeError, ValueError):
                # jitter around base
                val = meta["base"] + random.uniform(-meta["noise"], meta["noise"])
        else:
            if kind == "dig":
                val = meta["base"]
            elif kind == "uint":
                val = meta["base"]
            else:
                meta["base"] = meta["base"] + random.uniform(-meta["noise"] * 0.3, meta["noise"] * 0.3)
                if kind == "pct":
                    meta["base"] = max(0.0, min(100.0, meta["base"]))
                val = meta["base"] + random.uniform(-meta["noise"], meta["noise"])
        meta["base"] = val if kind != "dig" else meta["base"]
        series.append((bucket, float(val)))
        if len(series) > MAX_SAMPLES:
            del series[: len(series) - MAX_SAMPLES]
        n += 1
    return n


def query_samples(
    iid: str,
    pid: str,
    *,
    start: int | None = None,
    end: int | None = None,
    index: int | None = None,
    direction: int = 0,
    total_hint: int | None = None,
    idxtime: int | None = None,
    duration: int | None = None,
    max_points: int = 2000,
) -> tuple[list[tuple[int, float]], dict[str, int]]:
    """Return (samples, header_meta) for GetLogData.

    header_meta: offset, num_actual, num_remaining, value_type
    Index 0 = oldest, N-1 = newest.
    """
    k = _key(str(iid), str(pid))
    series = _SERIES.get(k) or []
    meta = _SERIES_META.get(k) or {"value_type": VT_FLOAT}
    n = len(series)
    if n == 0:
        return [], {"offset": 0, "num_actual": 0, "num_remaining": 0, "value_type": meta.get("value_type", VT_FLOAT)}

    # Date-range query
    if start is not None and end is not None and start >= 0 and end >= 0:
        lo, hi = (start, end) if start <= end else (end, start)
        # inclusive-ish window
        idxs = [i for i, (ts, _) in enumerate(series) if lo <= ts <= hi]
        if not idxs:
            return [], {"offset": 0, "num_actual": 0, "num_remaining": 0, "value_type": meta["value_type"]}
        first, last = idxs[0], idxs[-1]
        chunk = series[first : last + 1]
        if len(chunk) > max_points:
            chunk = chunk[-max_points:]
            first = last + 1 - len(chunk)
        # offset = samples older than this chunk that exist globally? use first index
        return chunk, {
            "offset": first,
            "num_actual": len(chunk),
            "num_remaining": 0,  # SPA: lastLogIndex = numRemaining; treat batch as starting at 0 relative
            "value_type": meta["value_type"],
            # Override: we want lastLogIndex=first, firstLogIndex=last for absolute indices
            "_abs_first": first,
            "_abs_last": first + len(chunk) - 1,
            "_total": n,
        }

    # Duration / index navigation
    direction = int(direction or 0)
    if index is not None and str(index) != "":
        try:
            idx = int(index)
        except (TypeError, ValueError):
            idx = n - 1
    else:
        idx = n - 1

    count = 1000
    if duration and idxtime:
        # approximate samples in duration
        count = max(1, min(max_points, int(abs(duration)) // LOG_INTERVAL + 1))
    count = min(count, max_points)

    if direction < 0:  # OLDER — samples strictly older than index
        end_i = max(0, min(idx, n) - 1)
        start_i = max(0, end_i - count + 1)
        chunk = series[start_i : end_i + 1]
        return chunk, {
            "offset": start_i,
            "num_actual": len(chunk),
            "num_remaining": 0,
            "value_type": meta["value_type"],
            "_abs_first": start_i,
            "_abs_last": start_i + len(chunk) - 1 if chunk else start_i,
            "_total": n,
        }
    if direction > 0:  # NEWER
        start_i = min(n, max(0, idx + 1))
        end_i = min(n - 1, start_i + count - 1)
        if start_i >= n:
            return [], {
                "offset": n,
                "num_actual": 0,
                "num_remaining": 0,
                "value_type": meta["value_type"],
                "_total": n,
            }
        chunk = series[start_i : end_i + 1]
        return chunk, {
            "offset": start_i,
            "num_actual": len(chunk),
            "num_remaining": 0,
            "value_type": meta["value_type"],
            "_abs_first": start_i,
            "_abs_last": start_i + len(chunk) - 1,
            "_total": n,
        }

    # INIT / default: last `count` samples
    start_i = max(0, n - count)
    chunk = series[start_i:]
    return chunk, {
        "offset": start_i,
        "num_actual": len(chunk),
        "num_remaining": 0,
        "value_type": meta["value_type"],
        "_abs_first": start_i,
        "_abs_last": n - 1,
        "_total": n,
    }


def pack_log_binary(
    lgiid: int | str,
    appiid: int | str,
    pid: str,
    samples: list[tuple[int, float]],
    meta: dict[str, Any],
) -> bytes:
    """Pack GetLogData binary response matching SPA readBinaryLogs()."""
    value_type = int(meta.get("value_type", VT_FLOAT))
    n = len(samples)
    # Prefer absolute index mapping so SPA first/lastLogIndex track backendTotal
    if meta.get("_total") is not None and meta.get("_abs_first") is not None:
        abs_first = int(meta["_abs_first"])
        abs_last = int(meta.get("_abs_last", abs_first + n - 1))
        total = int(meta["_total"])
        # lastLogIndex = numRemaining; firstLogIndex = numRemaining + numActual - 1
        # => numRemaining = abs_first, numActual = n, offset = total - (abs_last+1) = samples after chunk? 
        # backendTotal = numRemaining + numActual + offset = total
        # So offset = total - abs_first - n
        num_remaining = abs_first
        num_actual = n
        offset = max(0, total - num_remaining - num_actual)
    else:
        offset = int(meta.get("offset", 0))
        num_actual = n
        num_remaining = int(meta.get("num_remaining", 0))

    if n == 0:
        # empty success (errorCode 101) when no data
        error_code = 101
        num_actual = 0
        num_remaining = 0
        offset = 0
    else:
        error_code = 0

    # dataLength = payload bytes after header
    if value_type == VT_DIG:
        sample_size = 4 + 1 + 1  # ts + int8 + status
    else:
        sample_size = 4 + 4 + 1  # ts + float32/uint32 + status
    data_length = num_actual * sample_size

    header_length = 40
    protocol_version = 1
    try:
        lgiid_i = int(lgiid)
    except (TypeError, ValueError):
        lgiid_i = 0
    try:
        appiid_i = int(appiid)
    except (TypeError, ValueError):
        appiid_i = 0
    crc = pid_crc32(pid)
    eng_unit = 0  # REU_NONE — SPA uses point unit for labels

    buf = bytearray()
    buf += struct.pack(
        "<IIIIIIII",
        header_length,
        protocol_version,
        lgiid_i & 0xFFFFFFFF,
        appiid_i & 0xFFFFFFFF,
        crc,
        offset & 0xFFFFFFFF,
        num_actual & 0xFFFFFFFF,
        num_remaining & 0xFFFFFFFF,
    )
    buf += struct.pack("<bbb", eng_unit, value_type, error_code)
    buf += b"\x00"  # pad to offset 36
    buf += struct.pack("<I", data_length & 0xFFFFFFFF)

    for ts, val in samples:
        buf += struct.pack("<I", int(ts) & 0xFFFFFFFF)
        if value_type == VT_DIG:
            buf += struct.pack("<b", 1 if val >= 0.5 else 0)
        elif value_type == VT_UINT:
            buf += struct.pack("<I", int(val) & 0xFFFFFFFF)
        else:
            buf += struct.pack("<f", float(val))
        buf += struct.pack("<b", 0)  # status OK
    return bytes(buf)


def empty_log_binary(lgiid=0, appiid=0, pid="") -> bytes:
    return pack_log_binary(lgiid, appiid, pid, [], {"value_type": VT_FLOAT})
