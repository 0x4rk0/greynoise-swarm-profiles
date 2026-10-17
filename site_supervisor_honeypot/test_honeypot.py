#!/usr/bin/env python3
"""Smoke test: GetSessionID → (optional) Login → GetSystemInformation → SetPointValues → GetPointValues."""
import json
import sys
import time
import urllib.parse
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8010"


def rpc(method, params=None, sid=None):
    payload = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": "1"}
    if sid:
        payload["params"] = dict(payload["params"])
        payload["params"]["sid"] = sid
    body = urllib.parse.urlencode({"m": json.dumps(payload), **({"sid": sid} if sid else {})}).encode()
    req = urllib.request.Request(
        f"{BASE}/cgi-bin/mgw.cgi",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        # Check no Server banner preferred; print what we got
        server = resp.headers.get("Server", "(none)")
        data = json.loads(resp.read().decode())
        return data, server


def main():
    print(f"Testing {BASE}")
    r, srv = rpc("GetSessionID")
    print(f"  Server header: {srv}")
    assert "result" in r and "sid" in r["result"], r
    sid = r["result"]["sid"]
    print(f"  GetSessionID → {sid}")

    # Login is optional; call it to exercise the stub
    r, _ = rpc("Login", {"username": "Admin", "password": "Admin"}, sid)
    print(f"  Login Admin/Admin → {r.get('result')}")

    r, _ = rpc("GetSystemInformation", {}, sid)
    info = r["result"]
    from plant_data import SITE
    assert info["SiteName"] == SITE["SiteName"], info
    print(f"  GetSystemInformation → SiteName={info['SiteName']} platform={info['platform']} model={info['unitmodel']}")

    SP = "487988082:CurPresStpt"   # +16 SUCTION EN pressure setpoint (psi)
    PV = "487988082:SuctionPres"
    def vals(ptrs):
        r, _ = rpc("GetPointValues", {"points": [{"ptr": p} for p in ptrs]}, sid)
        return {p["ptr"]: float(p["val"]) for p in r["result"]["points"]}
    v = vals([SP, PV])
    old_sp, old_val = v[SP], v[PV]
    new_sp = round(old_sp + 5.0, 1)
    print(f"  Before: +16 SUCTION EN pressure={old_val} setpoint={old_sp}")

    r, _ = rpc("SetPointValues", {"points": [{"ptr": SP, "val": str(new_sp)}]}, sid)
    res = r["result"]["points"][0]
    assert "err" not in res, r
    print(f"  SetPointValues → setpoint {old_sp} → {new_sp}")

    time.sleep(8)
    v = vals([SP, PV])
    print(f"  After ~8s: pressure={v[PV]} setpoint={v[SP]}")
    assert abs(v[SP] - new_sp) < 0.01, v
    moved = abs(v[PV] - new_sp) < abs(old_val - new_sp)
    assert moved, f"value did not drift: {old_val} → {v[PV]} (sp {new_sp})"
    print("PASS — setpoint accepted and temperature drifted")


if __name__ == "__main__":
    main()
