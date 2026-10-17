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
    assert info["SiteName"] == "Riverside Market", info
    print(f"  GetSystemInformation → SiteName={info['SiteName']} platform={info['platform']} model={info['unitmodel']}")

    r, _ = rpc("GetPointValues", {}, sid)
    pts = r["result"]["points"]
    assert pts, "no points"
    target = pts[0]
    old_sp = target["setpoint"]
    old_val = target["value"]
    new_sp = round(old_sp + 5.0, 1)
    print(f"  Before: {target['name']} value={old_val} setpoint={old_sp}")

    r, _ = rpc("SetPointValues", {"points": [{"pid": target["pid"], "setpoint": new_sp}]}, sid)
    assert r["result"].get("success"), r
    print(f"  SetPointValues → setpoint {old_sp} → {new_sp}")

    # Wait for drift toward new setpoint
    time.sleep(8)
    r, _ = rpc("GetPointValues", {"pids": [target["pid"]]}, sid)
    updated = r["result"]["points"][0]
    print(f"  After ~8s: value={updated['value']} setpoint={updated['setpoint']}")
    assert updated["setpoint"] == new_sp, updated
    # Value should have moved toward new setpoint
    moved = abs(updated["value"] - old_val) > 0.3 or abs(updated["value"] - new_sp) < abs(old_val - new_sp)
    assert moved, f"value did not drift: {old_val} → {updated['value']} (sp {new_sp})"
    print("PASS — setpoint accepted and temperature drifted")


if __name__ == "__main__":
    main()
