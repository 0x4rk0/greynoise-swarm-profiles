# Site Supervisor / E3 CXe Honeypot (Riverside Market)


## Fake controller (no live PLC)

This honeypot **is** the controller. There is no Modbus/BACnet peer and nothing is
polled from a real Site Supervisor / E3.

- **`plant_data.py`** — synthetic maplewood inventory + Status tile point seeds  
- **`sim_loop`** — every ~3s jitters analogs for all System Tile apps and appends Base Log history  
- **`GET /stream`** — WebSocket push of dashboard points (same shape the SPA expects)  
- **`POST /cgi-bin/mgw.cgi`** — JSON-RPC (Login, GetPointValues, SetPointValues, GetLogData, …)

Gauges keep moving without any external I/O.

**Port:** default `8010`. If another local honeypot already binds 8010, stop it first or change `PORT` / compose mapping. Setpoint writes are accepted locally,
logged to `logs/attacks.jsonl`, and optionally POSTed to `ALERT_WEBHOOK_URL`.

### Auto-login (Admin / System Admin)

On page load, `js/honeypot-autologin.js` signs in as **Admin** / `Admin123!` so the
UI matches an authenticated technician session (Edit / Advanced / Save / System menu
unlocked). Manual login still works for `user`/`pass`, `Admin`/`Admin`, and
`Technician` / `Tech1234` (SPA requires passwords ≥ 8 characters to skip the reset
password screen — use `Admin123!` for Admin in the form).




## Novel honeypot decoys (SS-HONEY-2026-01) — intentional bait

These are **fictional, honeypot-only** flaws for GreyNoise / researcher bait. They are
**not** implementations of real Frostbyte / Armis CVEs. Do not treat them as product
vulnerabilities.

All logic lives in **`novel_vulns.py`** (edit there to change formulas or payloads).

### 1) SERVICE day-token auth gap

- Built-in user: **`SERVICE`** (not `oneday` / ONEDAY).
- Password (day token) = first **12 hex chars** of  
  `SHA256( unit_serial + "-" + YYYYMMDD )` where the date is **UTC**.
- `unit_serial` comes from `SITE["unit_serial"]` / `GetSystemInformation`  
  (default `CXE-RM-2024-0142`, overridable with env `HONEY_UNIT_SERIAL`).
- Successful Login returns **System Admin** permissions (same shape as Admin).
- Every SERVICE attempt is logged as **`novel_auth_probe`** (webhook if configured)
  with `token_matched`, username, serial, day, and src_ip.

Example (compute today’s token, then RPC Login):

```bash
python3 -c "import novel_vulns; print(novel_vulns.service_day_token())"
curl -s -X POST http://127.0.0.1:8010/cgi-bin/mgw.cgi -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"Login","params":{"key":"SERVICE","value":"<token>"},"id":1}'
```

### 2) GetHelpFile path-style probe

- Unauthenticated JSON-RPC **`GetHelpFile`** with param `name`.
- If `name` contains `..` or starts with `/`, the honeypot returns a **short fake
  HTML blob** (no real filesystem read) and logs **`path_traversal_probe`**.
- Adjacent in *spirit* to unauth file-read research, but a different method and no
  real disclosure.


## UI source (mirrored SPA)

The honeypot serves a **literally wget-mirrored** copy of a live Site Supervisor
SPA under `mirror/` (index.html, js/, css/, images/, fonts/). The fake JSON-RPC
backend (`cgi-bin/mgw.cgi` + `/stream`) still supplies synthetic point values and
logs SetPointValues changes.

Do **not** re-spider a live device aggressively. Mirror was taken with page-
requisites only (GET), no POSTs / no SetPointValues against production.


High-interaction decoy that mimics a **Copeland Site Supervisor / E3 supervisory controller (CXe)** so attackers believe they can view **System Summary** and **change setpoints / Case Temp** values. Every action is fake and appended to `logs/attacks.jsonl`.

Synthetic site identity: **Riverside Market** (not a real store). Built for GreyNoise Swarm custom-persona deployment.

## Official terminology (source docs)

Aligned with:

- **Supervisory Control Platform Installation & Operation User Manual** — Copeland P/N **026-1803** ([E3 docs page](https://www.copeland.com/en-us/products/controls-monitoring-systems/facility-controls-electronics/facility-and-system-controls/documents/supervisory-e3), PDF: [Supervisory Control E3 Manual](https://media.copeland.com/24cdca41-8c5f-47f7-9ebb-b16d004f4492/Supervisory%20Control%20E3%20Manual.pdf))
- **Site Supervisor Controller Quick Setup Guide** — P/N **026-4144** (R22, ©2024 Copeland LP)

Key UI / product terms used here:

| Term | Meaning |
|------|---------|
| Site Name | Facility label (Setup Wizard → System Values) |
| System Summary | Home overview with application tiles (Status tab) |
| Control Inventory | Application / device inventory |
| Case Temp | Circuit temperature point on StdCircuit apps |
| Setpoint | Target value attackers “write” via SetPointValues |
| Case Temp Hi Limit Exceeded | Alarm messagekey from real GetAlarms schema |
| Engineering units | °F (en-US default) |
| E3 / CXe | Platform / unit model (P/N 860-1330 E3 CXe) |

Default ETH1 IP in the guide is `192.168.1.250`; default login for *configuration* is **user / pass**. This honeypot **does not put a login wall in front of System Summary** (matches observed open summary behavior). The `Login` JSON-RPC method remains as an optional stub and is logged.

## Recommended OS (sensor / Swarm deploy)

| Item | Recommendation |
|------|----------------|
| OS | **Debian 12** or **Ubuntu 22.04 / 24.04** (amd64) |
| Python | **3.10+** (`python3`, `python3-venv`, `python3-pip`) |
| Optional | Docker / Docker Compose |

These Linux targets are the practical base when you want the host OS and HTTP front-end to fingerprint close to a real Site Supervisor appliance (see fingerprint section below).

## Quick start (Linux)

```bash
# 1. Unzip the package (if you received site_supervisor_honeypot.zip)
unzip site_supervisor_honeypot.zip
cd site_supervisor_honeypot

# 2. Virtualenv + deps
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 3. Run — binds http://0.0.0.0:8010/
.venv/bin/python server.py
```

Open **http://0.0.0.0:8010/** (or http://127.0.0.1:8010/ locally). System Summary loads with live Case Temp tiles — **no login wall**. Change a **Setpoint** — the UI shows a success toast (`Setpoint updated: … °F`) and the value eases gently toward the new target (tiny ±0.1–0.3 °F jitter when idle).

Background:

```bash
mkdir -p logs
nohup .venv/bin/python server.py >> logs/server.out 2>&1 &
```

Smoke test (server must be running):

```bash
.venv/bin/python test_honeypot.py http://127.0.0.1:8010
```

### Docker (optional)

If `Dockerfile` / `docker-compose.yml` are present:

```bash
docker compose up --build
# or: docker build -t site-supervisor-hp . && docker run --rm -p 8010:8010 -v "$PWD/logs:/app/logs" site-supervisor-hp
```


## Navigation (hash routes)

Single-page UI with a left nav matching Site Supervisor sections. Routes (no login):

| Hash route | View |
|------------|------|
| `#/systemsummary` | Home tiles + live temps / setpoints |
| `#/alarms` | Active alarms with Ack / Reset (logged) |
| `#/alarmhandling` | Notice-class stub |
| `#/casedefrostsummary` | Case circuits, state, next defrost |
| `#/device/<iid>` | Device / circuit point list (editable setpoints) |
| `#/inventory` | Control Inventory |
| `#/schedules` | Weekly lighting / case / HVAC schedules (edits logged) |
| `#/users` | User list; Add User is blocked but logged |
| `#/logs` | Synthetic event log |
| `#/networksummary`, `#/physicaliostatus`, `#/floorplan`, … | Status / config stubs |

Mutating RPCs append to `logs/attacks.jsonl` with classifications: `setpoint_change`, `alarm_ack`, `alarm_reset`, `schedule_change`, `user_add_attempt`, `config_change`, plus `recon` / `login_*` / `upload_attempt`.

## Real-time alerts (webhook)

On every mutating classification above, the honeypot can POST an alert to an optional webhook. Failures never block or crash the request path (3s timeout, background thread).

| Env var | Default | Meaning |
|---------|---------|---------|
| `ALERT_WEBHOOK_URL` | _(empty = off)_ | Destination URL |
| `ALERT_WEBHOOK_FORMAT` | `json` | `ntfy` · `slack` · `discord` · `json` |

Payload always includes `src_ip`, UTC time, point/name, old → new (when applicable), and `User-Agent`.

### ntfy.sh (phone push)

```bash
# Create/open a topic in the ntfy app, then:
export ALERT_WEBHOOK_URL="https://ntfy.sh/your-private-topic"
export ALERT_WEBHOOK_FORMAT=ntfy
.venv/bin/python server.py
```

### Slack incoming webhook

```bash
export ALERT_WEBHOOK_URL="https://hooks.slack.com/services/T…/B…/…"
export ALERT_WEBHOOK_FORMAT=slack
```

### Discord webhook

```bash
export ALERT_WEBHOOK_URL="https://discord.com/api/webhooks/…/…"
export ALERT_WEBHOOK_FORMAT=discord
```

### Docker Compose

```yaml
environment:
  - PORT=8010
  - ALERT_WEBHOOK_URL=https://ntfy.sh/your-private-topic
  - ALERT_WEBHOOK_FORMAT=ntfy
```

SMTP / email alerting is not built in; use ntfy or Slack/Discord instead.

## What an attacker sees

1. Title **Site Supervisor**, favicon at `./images/favicon-DPD4Tvk1.ico` (Shodan `http.favicon.hash:290468447`, byte-identical to sample).
2. Open **System Summary** with Status tiles (meat/dairy/frozen cases, suction, discharge, Store RTU).
3. JSON-RPC on `POST/GET /cgi-bin/mgw.cgi` (form field `m` = JSON-RPC body, optional `sid`).
4. WebSocket `/stream?sid=…` pushing point updates every ~2.5s.
5. `SetPointValues` **succeeds without Login**; subsequent reads and the WS stream show temps drifting toward the new setpoint.
6. Stub CGIs: `dl.cgi`, `lpolling.cgi`, `tm.cgi`, `G4upl.cgi`.
7. Real SPA assets still served under `/js/`, `/css/`, `/images/` and `/spa` for fingerprinting; usable UI is `/` (custom summary).

### Setpoint deception

In-memory points hold `value` and `setpoint`. A background loop eases `value` toward `setpoint` with small noise. After `SetPointValues`, an attacker watching System Summary or polling `GetPointValues` sees the Case Temp move — they believe the rack responded.

## Logging

JSONL: `logs/attacks.jsonl`

```json
{"ts":"...","classification":"setpoint_change","src_ip":"1.2.3.4","sid":"...","username":"","method":"SetPointValues","params":{"pid":"...","name":"21 B SRV MEAT","old":34.0,"new":39.0},"old_setpoint":34.0,"new_setpoint":39.0,"current_value":34.2}
```

Classifications: `login_success`, `login_fail`, `setpoint_change`, `recon`, `upload_attempt`.

Console also prints one-liners for login and setpoint events.

## OS / HTTP fingerprint (match the real box)

### What we observed on a real sample

| Signal | Observed |
|--------|----------|
| HTTP `Server` | **Absent** (no nginx/Apache/Python banner) |
| Security headers | `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, HSTS, CSP `object-src 'none'`, `X-Permitted-Cross-Domain-Policies: none`, `X-XSS-Protection: 1` |
| Port | **8010** (web UI); also commonly 80/443 when TLS enabled |
| Platform fields | `platform=E3`, `unitmodel=CXe`, `unitversion` like `2.30F01` |
| OS | Embedded Linux (E3/Site Supervisor hardware; ARM-class controllers; guide mentions Linux armv7l WebView on 10" display) |
| Default ETH1 | 192.168.1.250 (guide) — not required for Swarm WAN exposure |

### Recommended deploy options

**(a) Docker (good enough for HTTP/favicon/path fingerprint)**

Use the included `Dockerfile` (`python:3.11-slim-bookworm`). Map **8010** (and optionally 80/443). The app omits/strips `Server`. For a stricter banner match, put **nginx** in front with `server_tokens off` + `proxy_hide_header Server` (see `deploy/nginx.conf`; `headers-more` `more_clear_headers Server` if available).

**(b) Host OS notes for deeper fingerprint**

- Prefer **Linux**; if Swarm/Nmap sees `uname`, an **ARM** image/host is closer to controller hardware than x86_64 desktop.
- Do **not** advertise OpenSSH/FTP on the persona unless intentional (Copeland security guidance: restrict admin protocols).
- Terminate TLS on 443 if you want HTTPS explorers; use a generic cert CN if needed.
- Keep open ports limited to **8010** (+80/443) for the web persona.

## GreyNoise Swarm — custom profile request template

```yaml
# Draft request for a Swarm custom persona
name: Copeland Site Supervisor E3 CXe (Riverside Market)
description: >
  High-interaction Site Supervisor / E3 CXe web UI honeypot.
  Open System Summary; JSON-RPC setpoint writes accepted and logged.
ports:
  - 8010/tcp   # primary web UI (matches lab sample)
  - 80/tcp     # optional
  - 443/tcp    # optional TLS
http:
  title: Site Supervisor
  favicon_path: ./images/favicon-DPD4Tvk1.ico
  favicon_hash_mmh3: 290468447
  shodan_query: 'http.favicon.hash:290468447'
  paths:
    - /
    - /summary
    - /spa
    - /cgi-bin/mgw.cgi
    - /cgi-bin/dl.cgi
    - /cgi-bin/lpolling.cgi
    - /cgi-bin/tm.cgi
    - /cgi-bin/G4upl.cgi
    - /stream
    - /images/favicon-DPD4Tvk1.ico
    - /js/index-BVxYcbwd.js
    - /js/preload.js
capture:
  - All JSON-RPC methods + params on mgw.cgi (especially SetPointValues, Login, GetSystemInventory)
  - WebSocket /stream messages
  - Upload attempts on G4upl.cgi
  - Source IP, sid, username, classification → attacks.jsonl
identity:
  SiteName: Riverside Market
  platform: E3
  unitmodel: CXe
  unitversion: 2.30F01
  desc: C-Store Expansion (CXe)
notes: >
  No login gate on System Summary. SetPointValues works unauthenticated
  so attackers believe they changed Case Temp setpoints. Temps drift
  toward new setpoints over ~10-30 seconds.
```

## JSON-RPC methods implemented

`GetSessionID`, `TouchSession`, `Login`, `Logout`, `GetSystemInformation`, `GetSystemInventory`, `GetAlarms`, `GetPointValues`, `GetRealTimePointsData`, `GetPointsDescription`, `GetUserSelectedTilePoints`, `GetDashboardSummaryProps`, `GetGroups`, `GetHomeScreenState`, `GetProfile`, `SetPointValues`. Unknown → `-32601 Method not found` (logged).

## Layout

```
site_supervisor_honeypot/
  server.py           # aiohttp honeypot
  summary.html        # open System Summary UI
  test_honeypot.py
  requirements.txt
  Dockerfile
  docker-compose.yml
  README.md
  deploy/nginx.conf
  static/images/favicon-DPD4Tvk1.ico
  static/js/...       # real SPA assets from sample
  logs/attacks.jsonl
```

## Safety

Synthetic identity only. Do not point this at or scrape live Copeland controllers. For research / GreyNoise sensor use.
