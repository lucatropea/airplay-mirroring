# Mirror

Display your **iPad screen on a Windows PC** on the same Wi‑Fi network.

Two ways to connect:

| Mode | Best for | Start on PC |
|------|----------|-------------|
| **AirPlay** (recommended) | Native **Screen Mirroring** from Control Center | `start-airplay.bat` |
| **Web** | Safari + QR link, no AirPlay install | `start-web.bat` |

No app install on the iPad for web mode. AirPlay mode installs [uxplay-windows](https://github.com/leapbtw/uxplay-windows) on the PC automatically via `winget` on first run.

## Requirements

- **Windows 10/11**
- **Python 3.10+** ([python.org](https://www.python.org/downloads/))
- **iPad** and PC on the **same Wi‑Fi**
- For AirPlay: **winget** (included in current Windows builds)

## Quick start — AirPlay

1. Clone or download this repo.
2. Double‑click **`start-airplay.bat`**.
3. On first run, approve the **uxplay-windows** install (~90 MB) if Windows asks.
4. On iPad: **Control Center → Screen Mirroring** → select this PC.
5. The iPad appears in the **uxplay-windows** window (tray icon near the clock).

## Quick start — Web (Safari)

1. Double‑click **`start-web.bat`** (installs `qrcode` once).
2. A browser tab opens on the PC with a **QR code** and link.
3. On iPad, open the link in **Safari** (or scan the QR).
4. Tap **Start sharing** → choose **Entire screen**.
5. Watch the stream on the PC host page.

Do **not** use Control Center Screen Mirroring for web mode — that is AirPlay, not this server.

## Command line

```bash
# AirPlay receiver (uxplay-windows)
python airplay.py

# Web server (default port 8765)
pip install -r requirements.txt
python app.py --port 8765
```

## How it works

### AirPlay mode

`airplay.py` ensures **uxplay-windows** is installed (`winget install leapbtw.uxplay`) and launches it. That project implements an AirPlay 2 mirror receiver. Mirror does not embed uxplay source code; it is a small launcher.

### Web mode

- **`app.py`** — HTTP server on `0.0.0.0`.
- **iPad** — `getDisplayMedia()` → JPEG frames → `POST /push/{token}`.
- **PC** — `/host` shows a live canvas fed by a chunked binary stream (`/live/{token}`).
- **Session token** — random hex in the URL; rotate each server start.

```
iPad (Safari)                    Windows PC
     |  JPEG POST /push/token  -->  FrameHub
     |                               |
     |                          /host (viewer)
```

## Project layout

```
mirror/           Python package (server, hub, network, uxplay helper)
web/              Static UI (host + sender pages)
app.py            Web mode entry point
airplay.py        AirPlay mode entry point
start-web.bat     Windows launcher (web)
start-airplay.bat Windows launcher (AirPlay)
requirements.txt  qrcode (web mode only)
```

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| iPad does not list the PC (AirPlay) | Same Wi‑Fi; wait 10s; restart `start-airplay.bat`; allow uxplay in firewall |
| `winget` install fails | Run `winget install --id leapbtw.uxplay -e` in PowerShell as admin |
| Web: iPad cannot connect | Allow **Python** on private networks; check PC LAN IP is not `127.0.0.1` |
| Web: no “Entire screen” option | Update iPadOS; use AirPlay mode instead |
| Port in use | `python app.py --port 8770` |

## Security

- Web mode binds to all interfaces on your LAN. Anyone with the **token URL** can send or view until you stop the server.
- Use only on trusted home/office Wi‑Fi.
- AirPlay uses uxplay-windows’ own pairing and discovery.

## Third‑party software

- **[uxplay-windows](https://github.com/leapbtw/uxplay-windows)** — GPL‑3.0, installed via winget for AirPlay mode.
- **[UxPlay](https://github.com/FDH2/UxPlay)** — upstream AirPlay implementation.

## License

MIT — see [LICENSE](LICENSE) for this repository’s launcher and web server code. uxplay-windows remains under its own license when installed separately.
