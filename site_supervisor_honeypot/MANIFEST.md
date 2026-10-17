# Site Supervisor honeypot — file manifest

Start here when taking over the project. Paths are relative to the project root
(`/workspace/site_supervisor_honeypot` or the unzipped package).

**Legend:** ✅ safe / expected to edit for plant behavior & bait · ⚠️ edit carefully ·
🔒 mirrored SPA asset — prefer not to hand-edit (re-mirror if you must refresh UI)

Hard rule: **never** pull live values or JSON-RPC from `206.40.119.142`.

---

## Top-level entrypoints

### `MANIFEST.md` (this file)
Inventory of every meaningful path and what to edit. Keep it updated when you add modules.

### `README.md` ✅
Operator docs: quick start, credentials, fingerprint notes, novel decoy overview
(SS-HONEY-2026-01). Update when ports, creds, or bait behavior change.

### `server.py` ✅
aiohttp app: JSON-RPC `cgi-bin/mgw.cgi`, WebSocket `/stream`, static SPA serving,
session/login, inventory mutation (AddApp/RemoveApp), alarms, setpoints, alert
webhook. **Primary backend.** Wire new RPCs into `HANDLERS` here; keep novel bait
thin and delegate to `novel_vulns.py`.

### `plant_data.py` ✅
Synthetic maplewood site identity (`SITE`, including `unit_serial`), inventory
builders, dashboard tile point defs (`DASHBOARD`), apptype metadata
(`APPTYPE_META` / `APPDESC`), seed values. Edit to rename the store, change
circuits/AHUs, or retune Status-tile points. Serial here feeds the SERVICE
day-token formula.

### `log_history.py` ✅
In-memory Base Log time-series + binary `GetLogData` packing. Edit for sample
cadence, history length, or how new apps get seeded (`seed_log_history_for_app`).

### `app_descriptions.py` ✅
ADF-like `GetAppDescription` builders (Status groups, setpoints, tabs) per
apptype. Edit to make device pages richer or match a new apptype after AddApp.

### `novel_vulns.py` ✅
**Intentional decoys only (SS-HONEY-2026-01).** SERVICE day-token auth +
`GetHelpFile` path-probe blob. Change formula, serial default, username, or fake
file content here in one place. Not real Frostbyte CVE behavior.

### `summary.html` ⚠️
Legacy/alternate summary page (not the main mirrored SPA home). Safe to tweak for
experiments; production UI is `mirror/index.html`.

### `test_honeypot.py` ✅
Smoke test against a running instance (session → login → info → setpoint). Extend
for SERVICE token / GetHelpFile checks if desired.

### `requirements.txt` ✅
Python deps (`aiohttp`). Bump versions carefully; keep the image slim.

### `Dockerfile` ✅
Image build: copies Python modules (including `novel_vulns.py`), `mirror/`,
`static/`, `deploy/`, `MANIFEST.md`, `README.md`. Update `COPY` lines when you add
modules.

### `docker-compose.yml` ✅
Compose service on port 8010, logs volume, optional `ALERT_WEBHOOK_*` env.
Change port mapping or webhook here for Swarm/sensor deploy.

---

## Deploy / ops

### `deploy/` ✅
Optional front-door configs.

### `deploy/nginx.conf` ✅
Nginx reverse-proxy example: strip/hide `Server`, multi-port 80/8010/443, proxy to
the Python honeypot. Use when you want a closer HTTP fingerprint than bare aiohttp.

### `logs/` ✅ (runtime)
Attack / recon JSONL and access log. **Do not** ship real attack logs in the zip;
keep `logs/.gitkeep` so the directory exists.

### `logs/.gitkeep` ✅
Placeholder so empty `logs/` is preserved in git/zip.

### `logs/attacks.jsonl` / `logs/access.log` (runtime only)
Generated at runtime. Safe to truncate; excluded from release zips.

### `docs/` ⚠️
Optional local reference PDFs/text. **Excluded from zip** (`docs/*.pdf`). Do not
rely on them at runtime.

### `images/` ⚠️
Top-level favicon / small assets sometimes referenced outside `mirror/`. Prefer
editing branding in `mirror/images/` if the SPA is the UI in use.

---

## Mirrored SPA (`mirror/`) — 🔒

Full wget-style capture of the real Site Supervisor web UI. Served as the main
front-end. **Do not** re-spider production aggressively. Hand-edits are brittle
(hashed filenames); prefer server-side behavior changes.

### `mirror/index.html` 🔒
SPA shell; loads hashed JS/CSS and injects honeypot helpers. Change script tags
only if you add a new helper (e.g. autologin).

### `mirror/js/` 🔒
Bundled application + vendor JS.

### `mirror/js/index-BVxYcbwd.js` 🔒
Main Vue/Pinia SPA bundle (inventory, device pages, Login, AddApp). Treat as
read-only reference when debugging RPC shapes (`addApp`, `Fs()` password wrap).

### `mirror/js/vendor-OZELTil7.js` 🔒
Third-party vendor bundle. Do not edit.

### `mirror/js/honeypot-autologin.js` ✅ (honeypot-owned)
Not from the OEM mirror logic — auto-logs in as Admin after boot so the UI looks
authenticated. Edit username/password here for demo preference.

### `mirror/js/preload.js` / `mirror/js/ping.js` / `mirror/js/qrcode.js` / `mirror/js/file-analyzer.js` 🔒
OEM helpers. Leave alone unless debugging load order.

### `mirror/js/i18n/` 🔒
Locale packs.

### `mirror/js/i18n/en-US/` 🔒
English strings for menus, confirms (“Add Application”), errors. Edit only if you
need bait copy changes and accept merge pain on re-mirror.

### `mirror/css/` 🔒
Themed CSS (default/light/dark) + reboot/preload. Branding tweaks possible but
hashed names make diffs noisy.

### `mirror/images/` 🔒
Logos, favicon, ionicons. Replace logos here for a different “site” look.

### `mirror/fonts/` 🔒
Web fonts for the SPA.

### `mirror/static-json/` 🔒
Static JSON fragments (e.g. flexible-combiner / OSS notices) the SPA may fetch.

---

## Alternate static tree (`static/`) ⚠️

Secondary/older copy of UI assets (`static/index.html`, `static/js/`, …). The
live server prefers **`mirror/`**. Keep in sync only if something still points
here; otherwise favor `mirror/`. `static/js/honeypot-autologin.js` may duplicate
the mirror helper — edit the one your `index.html` actually loads (mirror).

---

## Python caches / backups (ignore)

### `__pycache__/` · `.venv/`
Local only — **excluded from zip**. Never commit secrets into the venv.

### `server.py.bak_*` · `summary.html.bak`
Local backups from earlier edits. Safe to delete; excluded from release zips.

---

## Quick “I want to…” map

| Goal | Edit |
|------|------|
| Change store name / serial / version | `plant_data.py` → `SITE` |
| Change SERVICE day-token formula | `novel_vulns.py` |
| Add/change JSON-RPC method | `server.py` `HANDLERS` (+ optional module) |
| Richer device tabs | `app_descriptions.py` |
| Tile gauges / circuit list | `plant_data.py` `DASHBOARD` / inventory |
| Auto-login user | `mirror/js/honeypot-autologin.js` |
| Webhook alerts | env in `docker-compose.yml` / `ALERT_*` in `server.py` |
| HTTP fingerprint | `deploy/nginx.conf` |
| Understand layout | this `MANIFEST.md` |

---

*Honeypot decoys are intentional. Novel auth and GetHelpFile probes are bait, not
copies of real CVE exploit code.*
