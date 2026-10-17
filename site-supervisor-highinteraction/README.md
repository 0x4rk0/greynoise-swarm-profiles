# Site Supervisor E3 — high-interaction web honeypot

This is an **offline, stateful simulation** assembled from a previously captured Copeland Site Supervisor/E3 browser interface. It **does not** run Copeland firmware, reproduce the controller's proprietary backend, or connect to the external device at `206.40.119.142`. It uses no physical equipment. The browser-facing UI contains no deliberate demonstration banners.

## Quick start on macOS — PHP only

1. Install PHP if missing: `brew install php`
2. Extract this ZIP: `unzip site-supervisor-highinteraction.zip -d site-supervisor-highinteraction`
3. Enter the folder: `cd site-supervisor-highinteraction`
4. Start the PHP server: `php -S 127.0.0.1:8010 router.php`
5. Open: `http://127.0.0.1:8010/#/`

Device application example: `http://127.0.0.1:8010/#/device/487988082`

To make it accessible from another host in an **isolated honeypot network**, bind the HTTP service to an explicitly permitted interface rather than `127.0.0.1`, and enforce egress restrictions and isolation externally. Never forward requests to a genuine building controller.

## Apache/LAMP or Docker Desktop on Mac

The same directory works with PHP 8.1+ and Apache 2.4 with `mod_rewrite` and `.htaccess` enabled, using the directory as the document root. Ensure the `private/` directory is writable by the Apache worker but **not** accessible over HTTP. The `.htaccess` rules block its contents.

Optional Docker Desktop (Apache + PHP):

```bash
docker compose up --build -d
```

Then browse `http://127.0.0.1:8010/#/`. The Compose example listens only on localhost by default. To shut it down: `docker compose down`. A named volume retains server-side simulated changes and request logs.

## What it simulates

- The captured Site Supervisor visual structure, navigation, and HTTP asset routes.
- Homepage/system summary groups matching the **101 applications indicated by category counts**: 36 Refrigeration, 2 HVAC, 36 Other, and 27 System.
- **49 application IDs and names** recovered from captured alarm history, including `487988082` (`+16 SUCTION EN`). **52 additional applications have synthetic names and synthetic IDs** to fill the remaining category counts; those are *not claimed to match the original controller*.
- The 719 captured alarm entries, plus locally generated simulated event records.
- `GET`/`POST /cgi-bin/mgw.cgi` JSON-RPC session creation, inventory, alarms, application-state queries, point values, and selected simulated command handling.
- Persistent per-application setpoints, output modes, defrost states, alarm acknowledgements, and simplified temperature/pressure trends. Commands change **simulated data only**.
- Browser page drilldowns such as `#/device/487988082`, device Points/Controls/Alarms/History/Configuration tabs, and other captured navigation destinations.

## Operator access and controls

Use the header login icon or **Users & Roles** to sign in with `admin` / `admin`. This default account is an intentional weak credential. Login now checks the password; writes require the administrator role. These changes apply only to the local application state.

- Open a temperature application and choose **Controls** to change its setpoint, measured temperature, output, or high-temperature limit. A measured-temperature override holds until **Resume automatic input** is selected.
- Temperature readings above the high limit generate a critical alarm. Default limits are 45°F, or 10°F for freezer applications. Alarms return to normal 2°F below the limit, retain their history, and generate a new event for a later excursion. Evaluation occurs on API requests; the browser polls every 10 seconds. An alarm with an active condition reappears within the next polling interval after suppression expires; a recovered condition remains in history.
- **Active Alarm**, individual alarm details, application controls, and **Alarm Communications** offer suppression for 1 minute to 24 hours. Suppression applies to an alarm, device, or the entire system. Suppressed alarms remain in history and in the **Suppressed** filter. Expiry restores reporting automatically; **Restore** restores the selected scope immediately. Global restore also clears narrower suppression settings.
- Submit persistent **Operator feedback** from **Help** or an application's **Configuration** tab. Feedback is stored as text, with its author, time, and application ID.

Runtime changes, suppression, alarm lifecycle, feedback, and control telemetry persist in `private/state.json`. The browser displays ordinary controller labels and does not disclose the default password.

Non-admin sessions see disabled, grey controls for temperature, setpoints, application status, output, defrost, acknowledgements, suppression, and feedback. The API independently enforces administrator access, including for direct requests. Login unlocks the current device tab; logout locks it again. An application enable/disable setting and **Analysis → Control Activity** are also available to administrators.

Run the isolated runtime checks with `php tests/controller.php`; they do not change the live state.

## Test API manually

```bash
curl -G --data-urlencode 'm={"jsonrpc":"2.0","method":"GetSessionID","id":"1"}' http://127.0.0.1:8010/cgi-bin/mgw.cgi
curl -G --data-urlencode 'm={"jsonrpc":"2.0","method":"GetDeviceState","params":{"deviceId":"487988082"},"id":"1"}' http://127.0.0.1:8010/cgi-bin/mgw.cgi
# Sign in first, retaining the session cookie:
curl -c /tmp/e3-cookie -H 'Content-Type: application/json' -d '{"method":"Login","params":{"username":"admin","password":"admin"},"id":1}' http://127.0.0.1:8010/cgi-bin/mgw.cgi
curl -b /tmp/e3-cookie -X POST -d 'm={"jsonrpc":"2.0","method":"SetPointValues","params":{"deviceId":"487988082","setpoint":424000},"id":"1"}' http://127.0.0.1:8010/cgi-bin/mgw.cgi
```

## Main menu and settings reference

The gear opens the main navigation drawer; click it again, click outside, or press Escape to close. The drawer works at desktop and mobile widths.

The settings structure follows Copeland's [026-1803 R22 Supervisory Control Platform Installation and Operation User Manual](https://media.copeland.com/24cdca41-8c5f-47f7-9ebb-b16d004f4492/Supervisory%20Control%20E3%20Manual.pdf), especially sections 4.1 (menus and General System Settings), 4.14 (user roles), page 1-5 (localization), and Appendix E (system values and peer configuration).

- **System → General System Settings**: System Values (site/unit/group identity, unit number, web port), Network Settings (DHCP, address, subnet, gateway, DNS, monitoring and legacy ports), COM Ports (protocol and baud rate), and Localization (locale, time zone, date/time formats). Values are readable without admin access; only admins can save changes. Basic view exposes an Advanced button for extra port settings.
- **System → My Profile**: home screen, Basic/Advanced view, language, and date/time preferences. Anonymous preferences belong to the browser session; signed-in users retain their own profiles. Advanced view reveals more fields and never grants control permissions.
- **System → Users & Roles**: admin account creation, editing, removal, and Viewer/System Admin assignment. Passwords for created accounts are hashed and never returned by the API. The built-in admin account remains available with the requested credential. Viewer users can log in and edit their profile but cannot change equipment, suppression, or controller settings.

The manual's broader role templates can permit some non-admin alarm actions. This implementation deliberately retains the user's stricter requirement: temperature changes and suppression require System Admin. Network, COM, and port settings persist in the application configuration; they do not reconfigure the host network or open external connections. Firmware installation and hardware-dependent operations remain outside this reconstruction's supported scope.

## Input endpoints

JSON-RPC requests go to `POST /cgi-bin/mgw.cgi` (also `/unit1/cgi-bin/mgw.cgi`), with a JSON body or form field `m`. GET requests with `m` are also accepted. Request attempts are captured in private telemetry; sensitive fields such as passwords are redacted.

| RPC method | Input fields | Behavior |
| --- | --- | --- |
| `Login` | `username`, `password` | Public login input; only the configured credential succeeds. |
| `SubmitFeedback` | `message`, optional `deviceId` | Admin only; persists arbitrary text up to 4000 bytes and renders it as text. |
| `SetTemperature`, `SetHighTemperatureLimit` | `deviceId`, `value` | Admin only; accepts finite numeric temperatures and rejects command or SQL strings. |
| `SuppressAlarms` | `uid` or `deviceId`, `minutes` | Admin only; timed alarm/device/global suppression. |

These are places where automated clients can submit injection probes. There is no SQL engine, shell execution, template evaluation, or executable feedback rendering behind these methods. Strings such as SQL syntax, HTML, and shell substitutions are rejected or stored literally. Unknown RPC methods are logged and return an empty result; they do not execute commands.

Browser validation uses a disposable copy of the application plus Chrome with remote debugging enabled: `node tests/browser.mjs http://127.0.0.1:18010 http://127.0.0.1:9225`. It verifies disabled controls, login/logout, a real one-minute suppression expiry, activity history, and literal feedback rendering. It intentionally changes the target copy's runtime state.

## Telemetry

- `private/events.jsonl`: JSON-lines access telemetry with timestamps, source IP, user agent, method, path, and redacted JSON-RPC payloads.
- `private/http-events.jsonl`: non-RPC HTTP requests when using the PHP development router. Apache access logs provide equivalent coverage on LAMP.
- `private/state.json`: persistent simulated application state, alarm acknowledgements, and control-event history.
- `private/generated-applications.txt`: generated/synthetic device IDs; keep this directory private.

To follow activity: `tail -f private/events.jsonl`. Stop the server before deleting `private/state.json` if you want to reset the simulated system. Rotate logs and consider immutable backups when exposed in a dedicated honeypot environment.

## Important limitations and deployment precautions

This is a reconstruction from an incomplete capture, **not an exact firmware clone or a byte-identical reproduction**. The original backend's API payload schemas, login semantics, application templates, point structures, and control algorithms were not fully captured. Unknown JSON-RPC methods are recorded and return an empty result; some settings pages have limited behavior. Sensor changes are algorithmic approximations, not model-derived thermodynamics. The original vendor JavaScript bundle is included as an artifact, but this build defaults to the reconstructed interface to avoid missing backend dependencies.

The PHP development server is for local testing only. For internet-facing research, use an isolated virtual machine or container with dedicated networking, a hardened HTTP gateway, egress filtering, no production credentials, and separate durable telemetry storage. Don't expose real industrial equipment. This package does not and cannot assign the third-party public IP address to your Mac.
