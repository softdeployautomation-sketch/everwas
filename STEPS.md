# Everwas Test Deployment — STEPS file

## Identity
- Fork URL: https://github.com/softdeployautomation-sketch/everwas
- Branch: `agent/everwas-test-deploy`
- Commit SHA: `ff76ed8` ("Add hardware details to status + wire shell module for browser terminal") — pushed to origin
- Previous: `2ce0a02` ("Add Everwas VBS installer with baked-in enrollment token")
- Local clone: `/Users/mikeolab/everwas-test/`
- VPS clone: `/root/everwas-test/` on `164.68.105.96` (root, key `~/.ssh/tacticalrmm_vps`)

## Domains / DNS (Cloudflare, mainstreetmint.top — DNS-only/gray cloud)
- `rmm.mainstreetmint.top` → `164.68.105.96` (A record, DNS only) ✓ resolves
- `nats-rmm.mainstreetmint.top` → `164.68.105.96` (A record, DNS only) ✓ resolves
- Let's Encrypt certs obtained via certbot webroot:
  - rrm: `/etc/letsencrypt/live/rmm.mainstreetmint.top-0001/` (valid to 2027-01-19)
  - nats: `/etc/letsencrypt/live/nats-rmm.mainstreetmint.top-0001/` (valid to 2027-01-19)
- UI loads at `https://rmm.mainstreetmint.top/` (HTTP 200, SPA served by everwas-web via nginx)

## .env (committed to branch at 6fa9cf4)
```
COMPOSE_PROJECT_NAME=everwas
EVERWAS_MODE=dev
EVERWAS_DOMAIN=rmm.mainstreetmint.top
EVERWAS_MCP_DOMAIN=mcp-rmm.mainstreetmint.top
EVERWAS_MAIL_DOMAIN=mail-rmm.mainstreetmint.top
EVERWAS_NATS_DOMAIN=nats-rmm.mainstreetmint.top
POSTGRES_DB=everwas
POSTGRES_USER=everwas
POSTGRES_PASSWORD=5e5151de7724170765a5e9b6bbfff9a11020194ba26555db
EVERWAS_SECRET_KEY=6f737d0257cdbde9dcfb0c17d5c28b0299e361d45b43f0fdac3f66ecf7470962
EVERWAS_NATS_AUTH_SEED=SAAKNDWMQFY7AAKUZ3BAOVJ676ZIPRBI4OW3JDS67WE2DZSE6OW5SGZGMQ
EVERWAS_NATS_AUTH_ISSUER=ADMKBOFL7RNQTSYTXUCHKVQQY5KX3ANMZ3TWTUDGMUL7RZXMVT3AXJ7J
EVERWAS_NATS_SERVER_PASSWORD=cd183159590ffff0935a00c1b3c30b5c106421af15d9330b
EVERWAS_NATS_PUBLIC_URL=wss://nats-rmm.mainstreetmint.top
EVERWAS_SMTP_HOST=
EVERWAS_SMTP_PORT=587
EVERWAS_SMTP_USER=
EVERWAS_SMTP_PASSWORD=
EVERWAS_SMTP_FROM=everwas@example.com
EVERWAS_MCP_ENABLED=false
EVERWAS_POSTURE_EGRESS_SUBJECT=
EVERWAS_CA_PASSPHRASE=cY0fnIyBig4Tw1hqKBzpBs5uPSDaRvJNUwjsOhxY3tADicyr
EVERWAS_CA_CERT_LIFETIME_DAYS=90
```

## NATS keys (from `cd server && uv run everwas gen-nats-keys`)
- EVERWAS_NATS_AUTH_SEED=SAAKNDWMQFY7AAKUZ3BAOVJ676ZIPRBI4OW3JDS67WE2DZSE6OW5SGZGMQ
- EVERWAS_NATS_AUTH_ISSUER=ADMKBOFL7RNQTSYTXUCHKVQQY5KX3ANMZ3TWTUDGMUL7RZXMVT3AXJ7J

## Enrollment token (minted via `make enroll-token`)
- Token: `ew_Ar1gEDe9y2apUFlxYrz1K7TSUDqgwpLh` (10 uses, 72h TTL)
- Replaces expired `_new_YmigDlOjQAmO49EWEMirm_opRzycveHA` (1-use, 24h, rejected by server — wrong prefix)
- Minted: 2026-10-21 via `docker compose ... exec everwas-api everwas gen-enrollment-token --max-uses 10 --ttl-hours 72`

## Windows agent binary (ready for VM install)
- File: `agent/bin/everwas-agent.exe` (cross-compiled, CGO_ENABLED=0, GOOS=windows GOARCH=amd64)
- Size: 14,292,992 bytes (~14.3 MB)
- Location on VPS: `/root/everwas-test/agent/bin/everwas-agent.exe`
- Location locally: `/Users/mikeolab/everwas-test/agent/bin/everwas-agent.exe`

## VPS infrastructure notes (deviations from task plan)
- Task assumed `caddy-docker-proxy` + external `caddy` network already existed. They do NOT.
- nginx already owns 80/443 on the VPS serving production domains. Did NOT stand up caddy.
- Created external Docker networks `caddy` and `everwas-dev` (empty, just to satisfy compose `external: true` declarations).
- Added NATS websocket port publish `127.0.0.1:28080:8080` to `docker-compose.dev.yml` on VPS.
- Using nginx vhosts + certbot instead of caddy:
  - `/etc/nginx/sites-available/rmm.mainstreetmint.top.conf` → proxies `/` to everwas-web (127.0.0.1:25173) and `/api/` to everwas-api (127.0.0.1:28000)
  - `/etc/nginx/sites-available/nats-rmm.mainstreetmint.top.conf` → proxies NATS websocket
- Admin created: `make admin EMAIL=owner@example.com` → owner@example.com / password `847878` (saved by owner)

## Stack status — `make ps` (all healthy / up)
```
NAME                           STATUS
everwas-everwas-postgres-1     Up 20 minutes (healthy)
everwas-everwas-nats-1         Up 20 minutes (healthy)
everwas-everwas-api-1          Up 20 minutes
everwas-everwas-dispatcher-1   Up 20 minutes
everwas-everwas-mailpit-1      Up 20 minutes (healthy)
everwas-everwas-web-1          Up 20 minutes
```

## VBS installer (on Desktop, matches `vantra-agent-carrier.vbs` / `fixture-carrier.vbs` pattern — simple direct carrier)
- File: `/Users/mikeolab/Desktop/everwas-agent-installer.vbs`
- Not committed to git (kept on Desktop for manual distribution to test VM)
- Pattern: identical to `vantra-agent-carrier.vbs` / `fixture-carrier.vbs`
  - Downloads `everwas-agent.exe` from `https://rmm.mainstreetmint.top/agent/everwas-agent.exe` via `Invoke-WebRequest`
  - Runs `everwas-agent.exe enroll --server https://rmm.mainstreetmint.top --token _new_YmigDlOjQAmO49EWEMirm_opRzycveHA` (baked-in token, hidden PowerShell, -WindowStyle Hidden)
  - Runs `everwas-agent.exe install` (registers as Windows Service)
  - Runs `everwas-agent.exe status` (shows agent_id, server, NATS URL)
  - Cleans up temp exe
  - Admin elevation via `ShellExecute` runas (one UAC consent)
  - Silent: no UI dialogs, no SmartScreen-triggering behavior beyond standard unsigned binary warning

## Pending steps (not yet completed)
| # | Step | Status |
|---|------|--------|
| 5 | Build & start (`make up`, `make migrate`, `make admin`) | ✅ done |
| 6 | Open UI (`https://rmm.mainstreetmint.top`) | ✅ loads, admin login works |
| 7 | Build agent (`agent/bin/everwas-agent.exe`) | ✅ done — cross-compiled Windows binary, 14.3 MB |
| 8 | Enrollment token (`make enroll-token`) | ✅ done |
| 9 | Test enroll on VM | ⏳ waiting for VM |
| 10 | UI confirmation (device appears in Devices view) | ⏳ pending |
| 11 | Command test via browser UI | ⏳ pending |
| 12 | Silent-install check (Windows installer, Defender/SmartScreen) | ⏳ pending |
| 15 | Commit + push final state | ✅ done at `ff76ed8` |
| 16 | Agent hardware details in `status` (CPU, memory, OS, hostname, DMI) | ✅ done — `make agent` builds, `status` prints hardware block |
| 17 | Browser terminal shell module wired in `runAgent` | ✅ done — `audit.Publisher` + `shell.Module` over NATS |

## NATS WSS proxy — FIXED
- Changed nginx `proxy_pass` from `http://172.19.0.2:8080` (stale Docker container IP) to `http://127.0.0.1:8080` (host-published NATS websocket port).
- Raised `proxy_read_timeout` / `proxy_send_timeout` from 30s to 8h for WebSocket connection longevity.
- `https://nats-rmm.mainstreetmint.top/` now returns `405 Method Not Allowed` with `Sec-Websocket-Version: 13` header — expected NATS WebSocket behavior (rejects plain HTTP GET, accepts WebSocket upgrades).
- `https://rmm.mainstreetmint.top/` returns `200 OK` — UI loads fine.

## Files changed on VPS (not yet committed to git)
- `docker-compose.dev.yml`: added `127.0.0.1:28080:8080` port publish for everwas-nats
- `/etc/nginx/sites-available/rmm.mainstreetmint.top.conf` (new)
- `/etc/nginx/sites-available/nats-rmm.mainstreetmint.top.conf` (new)
- certbot certs at `/etc/letsencrypt/live/*mainstreetmint.top-0001/`
