#!/usr/bin/env python3
"""
Virtual Duepi EVO Pellet Stove Emulator
Emulates the TCP protocol used by the duepi_evo Home Assistant integration.

Usage:
  python3 virtual_stove.py [--host 0.0.0.0] [--port 2000] [--ui-port 8080]

Then open http://localhost:8080 in your browser to control the virtual stove.
Configure Home Assistant to connect to host: <your-ip>, port: 2000
"""

import argparse
import asyncio
import json
import logging
import math
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("virtual_stove")

# ---------------------------------------------------------------------------
# Stove state (shared between TCP server and HTTP UI)
# ---------------------------------------------------------------------------

class StoveState:
    """Mutable state of the virtual stove."""

    STATUS_CODES = {
        "off":      0x00000020,
        "starting": 0x01000000,
        "on":       0x02000000,
        "cleaning": 0x04000000,
        "eco":      0x10000000,
        "cooling":  0x08000000,
    }

    ERROR_CODES = {
        0: "All OK",
        1: "Ignition failure",
        2: "Defective suction",
        5: "Out of pellets",
        14: "Overheating",
    }

    def __init__(self):
        self.lock = threading.Lock()
        self.status = "off"          # off | starting | on | eco | cleaning | cooling
        self.ambient_temp = 210      # raw (×10 °C), so 21.0 °C
        self.flugas_temp = 80        # °C
        self.exh_fan_speed = 120     # ×10 rpm → stored as final value
        self.pellet_speed = 30
        self.power_level = 0         # 0-5
        self.setpoint = 20           # °C
        self.error_code = 0
        self._ignition_task = None
        self._sim_task = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _status_hex(self) -> int:
        return self.STATUS_CODES.get(self.status, 0x00000020)

    def encode_response(self, value: int, width: int = 4) -> bytes:
        """Build a response frame: space + hex value zero-padded + padding to 10 bytes."""
        hex_val = f"{value:0{width}X}"
        frame = f" {hex_val}    \r\n"   # 1 + width + filler to reach 9 chars + \n
        # HA reads response[1:9] as 8-hex or response[1:5] as 4-hex
        # For status (8 hex chars): " XXXXXXXX\r\n"
        # For others (4 hex chars): " XXXX    \r\n"
        return frame[:10].encode()

    def status_response(self) -> bytes:
        return self.encode_response(self._status_hex(), width=8)

    def ack_response(self) -> bytes:
        """ACK response has bit 0x20 set."""
        return self.encode_response(0x00000020, width=8)

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    def handle_command(self, cmd: str) -> bytes:
        log.debug("CMD: %r", cmd)
        c = cmd.strip()

        if c == "D9000":   # GET_STATUS
            return self.status_response()

        elif c == "D3000": # GET_POWERLEVEL
            with self.lock:
                return self.encode_response(self.power_level)

        elif c == "D1000": # GET_TEMPERATURE
            with self.lock:
                return self.encode_response(self.ambient_temp)

        elif c == "D0000": # GET_FLUGASTEMP
            with self.lock:
                return self.encode_response(self.flugas_temp)

        elif c == "EF000": # GET_EXHFANSPEED  (stored /10 in raw)
            with self.lock:
                return self.encode_response(self.exh_fan_speed // 10)

        elif c == "D4000": # GET_PELLETSPEED
            with self.lock:
                return self.encode_response(self.pellet_speed)

        elif c == "DA000": # GET_ERRORSTATE
            with self.lock:
                return self.encode_response(self.error_code)

        elif c == "C6000": # GET_SETPOINT
            with self.lock:
                return self.encode_response(self.setpoint)

        elif c == "D6000": # REMOTE_RESET
            with self.lock:
                self.status = "off"
                self.power_level = 0
                self.error_code = 0
            log.info("Remote reset received – stove powered off")
            return self.ack_response()

        elif c == "DC000": # GET_INITCOMMAND
            return self.ack_response()

        elif c.startswith("F00") and c.endswith("0") and len(c) == 5:
            # SET_POWERLEVEL  F00x0
            try:
                level = int(c[3], 16)
            except ValueError:
                return self.ack_response()
            with self.lock:
                self.power_level = level
                if level == 0:
                    if self.status not in ("off", "cooling"):
                        self.status = "cooling"
                        log.info("Power level → 0, stove cooling down")
                else:
                    if self.status == "off":
                        self.status = "starting"
                        log.info("Power level → %d, stove starting", level)
                    elif self.status == "cooling":
                        self.status = "on"
                    self.status = "on" if self.status not in ("starting", "cleaning") else self.status
            return self.ack_response()

        elif c.startswith("F2") and c.endswith("0") and len(c) == 5:
            # SET_TEMPERATURE  F2xx0
            try:
                temp = int(c[2:4], 16)
            except ValueError:
                return self.ack_response()
            with self.lock:
                self.setpoint = temp
                log.info("Setpoint → %d°C", temp)
            return self.ack_response()

        else:
            log.warning("Unknown command: %r", c)
            return self.ack_response()

    # ------------------------------------------------------------------
    # Background simulation (gradually change temps while on)
    # ------------------------------------------------------------------

    def start_simulation(self):
        t = threading.Thread(target=self._simulate, daemon=True)
        t.start()

    def _simulate(self):
        """Slowly update temps to make the stove feel alive."""
        tick = 0
        while True:
            time.sleep(5)
            tick += 1
            with self.lock:
                if self.status in ("on", "eco"):
                    # Warm up toward setpoint
                    target_raw = self.setpoint * 10
                    if self.ambient_temp < target_raw:
                        self.ambient_temp = min(self.ambient_temp + 5, target_raw)
                    elif self.ambient_temp > target_raw + 20:
                        self.ambient_temp -= 3

                    self.flugas_temp = min(250, self.flugas_temp + (2 if self.power_level > 2 else 1))
                    self.exh_fan_speed = 800 + self.power_level * 200 + int(math.sin(tick) * 50)
                    self.pellet_speed = max(0, 20 + self.power_level * 8 + int(math.sin(tick * 0.7) * 5))

                elif self.status == "cooling":
                    self.flugas_temp = max(40, self.flugas_temp - 5)
                    self.exh_fan_speed = max(0, self.exh_fan_speed - 100)
                    self.pellet_speed = 0
                    if self.flugas_temp <= 50 and self.exh_fan_speed <= 100:
                        self.status = "off"
                        log.info("Stove cooled down → off")

                elif self.status == "starting":
                    # Simulate ignition sequence (takes ~30s)
                    self.flugas_temp = min(150, self.flugas_temp + 10)
                    if self.flugas_temp >= 150:
                        self.status = "on"
                        log.info("Stove ignition complete → on")

                elif self.status == "off":
                    self.ambient_temp = max(150, self.ambient_temp - 2)  # cool toward 15°C
                    self.flugas_temp = max(30, self.flugas_temp - 3)
                    self.exh_fan_speed = 0
                    self.pellet_speed = 0

    # ------------------------------------------------------------------
    # JSON snapshot for UI
    # ------------------------------------------------------------------

    def to_dict(self):
        with self.lock:
            return {
                "status": self.status,
                "ambient_temp": self.ambient_temp / 10.0,
                "flugas_temp": self.flugas_temp,
                "exh_fan_speed": self.exh_fan_speed,
                "pellet_speed": self.pellet_speed,
                "power_level": self.power_level,
                "setpoint": self.setpoint,
                "error_code": self.error_code,
                "error_label": self.ERROR_CODES.get(self.error_code, str(self.error_code)),
            }

    def apply_ui_command(self, action: str, value: str) -> str:
        with self.lock:
            if action == "set_status":
                if value in self.STATUS_CODES:
                    self.status = value
                    return f"Status set to {value}"
            elif action == "set_power":
                self.power_level = max(0, min(5, int(value)))
                return f"Power level set to {self.power_level}"
            elif action == "set_setpoint":
                self.setpoint = max(10, min(35, int(value)))
                return f"Setpoint set to {self.setpoint}°C"
            elif action == "set_ambient":
                self.ambient_temp = max(50, min(400, int(float(value) * 10)))
                return f"Ambient temp set to {float(value):.1f}°C"
            elif action == "set_flugas":
                self.flugas_temp = max(20, min(500, int(value)))
                return f"Flue gas temp set to {self.flugas_temp}°C"
            elif action == "set_error":
                self.error_code = int(value)
                return f"Error code set to {value}"
            elif action == "reset":
                self.status = "off"
                self.power_level = 0
                self.error_code = 0
                self.flugas_temp = 30
                self.exh_fan_speed = 0
                self.pellet_speed = 0
                return "Stove reset"
        return "Unknown action"


# ---------------------------------------------------------------------------
# Command frame parser
# ---------------------------------------------------------------------------

def parse_frame(data: bytes) -> str | None:
    """
    Expected frame: ESC 'R' <5-char-cmd> <2-hex-checksum> '&'
    Returns the 5-char command string or None if invalid.
    """
    try:
        s = data.decode("ascii", errors="replace")
    except Exception:
        return None

    # Find ESC
    esc = s.find("\x1b")
    if esc == -1:
        return None
    s = s[esc + 1:]  # strip ESC

    if not s.startswith("R"):
        return None
    body = s[1:]  # strip R
    if len(body) < 7:
        return None
    cmd = body[:5]
    return cmd


# ---------------------------------------------------------------------------
# TCP server
# ---------------------------------------------------------------------------

STOVE: StoveState = None


class StoveHandler(socketserver.BaseRequestHandler):
    def handle(self):
        peer = f"{self.client_address[0]}:{self.client_address[1]}"
        log.info("Connection from %s", peer)
        buf = b""
        self.request.settimeout(10.0)
        try:
            while True:
                try:
                    chunk = self.request.recv(64)
                except Exception:
                    break
                if not chunk:
                    break
                buf += chunk
                # Process complete frames (end with '&')
                while b"&" in buf:
                    idx = buf.index(b"&")
                    frame = buf[:idx + 1]
                    buf = buf[idx + 1:]
                    cmd = parse_frame(frame)
                    if cmd:
                        resp = STOVE.handle_command(cmd)
                        try:
                            self.request.sendall(resp)
                        except Exception as e:
                            log.warning("Send error: %s", e)
                            return
                    else:
                        log.warning("Bad frame: %r", frame)
        except Exception as e:
            log.debug("Handler exception: %s", e)
        finally:
            log.info("Disconnected %s", peer)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


# ---------------------------------------------------------------------------
# HTTP UI server
# ---------------------------------------------------------------------------

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Virtual Duepi EVO Stove</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Share+Tech+Mono&display=swap');

  :root {
    --bg: #0d0d0f;
    --panel: #141418;
    --border: #2a2a35;
    --accent: #ff6b2b;
    --accent2: #ff9f5a;
    --text: #e0ddd8;
    --dim: #7a7875;
    --green: #4ecb71;
    --red: #e83c3c;
    --blue: #4ab4e8;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Rajdhani', sans-serif;
    min-height: 100vh;
    padding: 2rem;
    background-image:
      radial-gradient(ellipse 60% 40% at 50% -10%, rgba(255,107,43,0.12) 0%, transparent 70%);
  }

  h1 {
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--accent);
    text-shadow: 0 0 30px rgba(255,107,43,0.5);
    margin-bottom: 0.25rem;
  }

  .subtitle {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.75rem;
    color: var(--dim);
    letter-spacing: 0.2em;
    margin-bottom: 2rem;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.25rem;
    max-width: 1100px;
  }

  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 1.25rem;
    position: relative;
    overflow: hidden;
  }
  .card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), transparent);
  }

  .card-title {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    color: var(--dim);
    margin-bottom: 1rem;
  }

  /* Status badge */
  .status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.9rem;
    border-radius: 2px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 1rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    border: 1px solid currentColor;
  }
  .status-off     { color: var(--dim);   border-color: var(--dim); }
  .status-on      { color: var(--green); border-color: var(--green); text-shadow: 0 0 12px var(--green); }
  .status-starting{ color: var(--accent2); border-color: var(--accent2); }
  .status-cooling { color: var(--blue);  border-color: var(--blue); }
  .status-eco     { color: #8de88d;      border-color: #8de88d; }
  .status-cleaning{ color: var(--accent2); border-color: var(--accent2); }

  .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 6px currentColor;
    animation: pulse 2s infinite;
  }
  .status-off .dot { animation: none; }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }

  /* Metrics */
  .metrics {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }

  .metric {
    background: rgba(0,0,0,0.3);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 0.6rem 0.75rem;
  }
  .metric-label {
    font-size: 0.65rem;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: var(--dim);
    margin-bottom: 0.2rem;
  }
  .metric-value {
    font-family: 'Share Tech Mono', monospace;
    font-size: 1.3rem;
    color: var(--accent2);
  }
  .metric-unit {
    font-size: 0.65rem;
    color: var(--dim);
    margin-left: 2px;
  }

  /* Controls */
  .control-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.75rem;
  }
  .control-row label {
    font-size: 0.75rem;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--dim);
    min-width: 90px;
  }

  select, input[type=range], input[type=number] {
    background: rgba(0,0,0,0.4);
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 2px;
    padding: 0.35rem 0.5rem;
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.85rem;
    outline: none;
    flex: 1;
  }
  select:focus, input:focus {
    border-color: var(--accent);
  }

  input[type=range] {
    padding: 0;
    cursor: pointer;
    accent-color: var(--accent);
  }

  .range-val {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.9rem;
    color: var(--accent2);
    min-width: 40px;
    text-align: right;
  }

  button {
    background: transparent;
    border: 1px solid var(--accent);
    color: var(--accent);
    padding: 0.5rem 1.25rem;
    border-radius: 2px;
    font-family: 'Rajdhani', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    cursor: pointer;
    transition: all 0.15s;
  }
  button:hover {
    background: var(--accent);
    color: #000;
    box-shadow: 0 0 20px rgba(255,107,43,0.4);
  }
  button.danger {
    border-color: var(--red);
    color: var(--red);
  }
  button.danger:hover {
    background: var(--red);
    color: #fff;
  }

  /* Log */
  #log {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.72rem;
    color: var(--dim);
    line-height: 1.6;
    max-height: 160px;
    overflow-y: auto;
    background: rgba(0,0,0,0.4);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 0.75rem;
  }
  #log .entry { color: var(--accent2); }
  #log .entry.ok { color: var(--green); }

  .error-indicator {
    color: var(--red);
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.85rem;
  }
  .error-ok { color: var(--green); }

  .power-bar {
    display: flex;
    gap: 4px;
    margin-top: 0.5rem;
  }
  .power-pip {
    flex: 1;
    height: 8px;
    border-radius: 1px;
    background: var(--border);
    transition: background 0.3s;
  }
  .power-pip.active {
    background: var(--accent);
    box-shadow: 0 0 6px rgba(255,107,43,0.6);
  }
</style>
</head>
<body>

<h1>&#x1F525; Duepi EVO Emulator</h1>
<p class="subtitle">TCP STOVE EMULATOR &mdash; VIRTUAL DEVICE CONTROL PANEL</p>

<div class="grid">

  <!-- Status card -->
  <div class="card">
    <div class="card-title">Burner Status</div>
    <div id="status-badge" class="status-badge status-off">
      <div class="dot"></div>
      <span id="status-text">OFF</span>
    </div>
    <div class="power-bar" style="margin-top:1rem;">
      <div class="power-pip" id="pip0"></div>
      <div class="power-pip" id="pip1"></div>
      <div class="power-pip" id="pip2"></div>
      <div class="power-pip" id="pip3"></div>
      <div class="power-pip" id="pip4"></div>
    </div>
    <div style="margin-top:0.3rem;font-size:0.65rem;color:var(--dim);letter-spacing:0.15em;">POWER LEVEL</div>
  </div>

  <!-- Temperatures -->
  <div class="card">
    <div class="card-title">Temperatures</div>
    <div class="metrics">
      <div class="metric">
        <div class="metric-label">Ambient</div>
        <div class="metric-value" id="m-ambient">—<span class="metric-unit">°C</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Setpoint</div>
        <div class="metric-value" id="m-setpoint">—<span class="metric-unit">°C</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Flue Gas</div>
        <div class="metric-value" id="m-flugas">—<span class="metric-unit">°C</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Error</div>
        <div class="metric-value error-indicator" id="m-error">OK</div>
      </div>
    </div>
  </div>

  <!-- Mechanical -->
  <div class="card">
    <div class="card-title">Mechanical</div>
    <div class="metrics">
      <div class="metric">
        <div class="metric-label">Exh. Fan</div>
        <div class="metric-value" id="m-exhfan">—<span class="metric-unit">RPM</span></div>
      </div>
      <div class="metric">
        <div class="metric-label">Pellet Speed</div>
        <div class="metric-value" id="m-pellet">—</div>
      </div>
    </div>
  </div>

  <!-- Controls: Status -->
  <div class="card">
    <div class="card-title">Set State</div>
    <div class="control-row">
      <label>Status</label>
      <select id="ctrl-status">
        <option value="off">Off</option>
        <option value="starting">Starting</option>
        <option value="on">On (Flame)</option>
        <option value="eco">Eco Idle</option>
        <option value="cleaning">Cleaning</option>
        <option value="cooling">Cooling Down</option>
      </select>
    </div>
    <button onclick="sendCmd('set_status', document.getElementById('ctrl-status').value)">Apply State</button>
    &nbsp;
    <button class="danger" onclick="sendCmd('reset','')">Hard Reset</button>
  </div>

  <!-- Controls: Values -->
  <div class="card">
    <div class="card-title">Adjust Values</div>

    <div class="control-row">
      <label>Power</label>
      <input type="range" id="r-power" min="0" max="5" step="1" value="0"
             oninput="document.getElementById('v-power').textContent=this.value">
      <span class="range-val" id="v-power">0</span>
    </div>

    <div class="control-row">
      <label>Setpoint</label>
      <input type="range" id="r-setpoint" min="10" max="35" step="1" value="20"
             oninput="document.getElementById('v-setpoint').textContent=this.value+'°C'">
      <span class="range-val" id="v-setpoint">20°C</span>
    </div>

    <div class="control-row">
      <label>Ambient</label>
      <input type="range" id="r-ambient" min="5" max="40" step="0.5" value="21"
             oninput="document.getElementById('v-ambient').textContent=parseFloat(this.value).toFixed(1)+'°C'">
      <span class="range-val" id="v-ambient">21.0°C</span>
    </div>

    <div class="control-row">
      <label>Flue Gas</label>
      <input type="range" id="r-flugas" min="20" max="500" step="5" value="80"
             oninput="document.getElementById('v-flugas').textContent=this.value+'°C'">
      <span class="range-val" id="v-flugas">80°C</span>
    </div>

    <div style="display:flex;gap:0.5rem;flex-wrap:wrap;margin-top:0.5rem;">
      <button onclick="applyValues()">Apply</button>
    </div>
  </div>

  <!-- Error injection -->
  <div class="card">
    <div class="card-title">Error Injection</div>
    <div class="control-row">
      <label>Error</label>
      <select id="ctrl-error">
        <option value="0">0 — All OK</option>
        <option value="1">1 — Ignition failure</option>
        <option value="2">2 — Defective suction</option>
        <option value="5">5 — Out of pellets</option>
        <option value="14">14 — Overheating</option>
      </select>
    </div>
    <button onclick="sendCmd('set_error', document.getElementById('ctrl-error').value)">Inject Error</button>
  </div>

  <!-- Activity log -->
  <div class="card" style="grid-column: 1 / -1;">
    <div class="card-title">Activity Log</div>
    <div id="log"><span style="color:var(--dim)">Waiting for connections...</span></div>
  </div>

</div>

<script>
const LOG_MAX = 80;
let logEntries = [];

function addLog(msg, ok=false) {
  const ts = new Date().toLocaleTimeString('en', {hour12:false});
  logEntries.push(`<span class="entry${ok?' ok':''}">[${ts}] ${msg}</span>`);
  if (logEntries.length > LOG_MAX) logEntries.shift();
  document.getElementById('log').innerHTML = logEntries.slice().reverse().join('<br>');
}

async function sendCmd(action, value) {
  try {
    const r = await fetch(`/cmd?action=${encodeURIComponent(action)}&value=${encodeURIComponent(value)}`);
    const j = await r.json();
    addLog(j.result, j.ok);
  } catch(e) {
    addLog('Error: ' + e.message);
  }
}

function applyValues() {
  sendCmd('set_power',   document.getElementById('r-power').value);
  sendCmd('set_setpoint',document.getElementById('r-setpoint').value);
  sendCmd('set_ambient', document.getElementById('r-ambient').value);
  sendCmd('set_flugas',  document.getElementById('r-flugas').value);
}

const STATUS_CLASS = {
  off:'status-off', on:'status-on', starting:'status-starting',
  cooling:'status-cooling', eco:'status-eco', cleaning:'status-cleaning'
};

async function poll() {
  try {
    const r = await fetch('/state');
    const s = await r.json();

    // Status badge
    const badge = document.getElementById('status-badge');
    badge.className = 'status-badge ' + (STATUS_CLASS[s.status] || 'status-off');
    document.getElementById('status-text').textContent = s.status.toUpperCase().replace('_',' ');

    // Power pips
    for(let i=0;i<5;i++) {
      document.getElementById('pip'+i).className = 'power-pip' + (i < s.power_level ? ' active' : '');
    }

    // Metrics
    document.getElementById('m-ambient').innerHTML = s.ambient_temp.toFixed(1) + '<span class="metric-unit">°C</span>';
    document.getElementById('m-setpoint').innerHTML = s.setpoint + '<span class="metric-unit">°C</span>';
    document.getElementById('m-flugas').innerHTML = s.flugas_temp + '<span class="metric-unit">°C</span>';
    document.getElementById('m-exhfan').innerHTML = s.exh_fan_speed + '<span class="metric-unit">RPM</span>';
    document.getElementById('m-pellet').textContent = s.pellet_speed;

    const errEl = document.getElementById('m-error');
    if (s.error_code === 0) {
      errEl.textContent = 'OK';
      errEl.className = 'metric-value error-ok';
    } else {
      errEl.textContent = 'E' + s.error_code;
      errEl.className = 'metric-value error-indicator';
    }
  } catch(e) {}
}

setInterval(poll, 1500);
poll();
addLog('UI loaded — connect Home Assistant to the TCP port');
</script>
</body>
</html>
"""


class UIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # silence default HTTP logs

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode())

        elif parsed.path == "/state":
            data = json.dumps(STOVE.to_dict()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        elif parsed.path == "/cmd":
            action = qs.get("action", [""])[0]
            value  = qs.get("value",  [""])[0]
            result = STOVE.apply_ui_command(action, value)
            resp = json.dumps({"result": result, "ok": True}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp)

        else:
            self.send_response(404)
            self.end_headers()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global STOVE

    parser = argparse.ArgumentParser(description="Virtual Duepi EVO Stove Emulator")
    parser.add_argument("--host",    default="0.0.0.0",  help="TCP bind host (default: 0.0.0.0)")
    parser.add_argument("--port",    default=2000, type=int, help="TCP port for stove protocol (default: 2000)")
    parser.add_argument("--ui-port", default=8080, type=int, help="HTTP port for web UI (default: 8080)")
    args = parser.parse_args()

    STOVE = StoveState()
    STOVE.start_simulation()

    # TCP server thread
    tcp_server = ThreadedTCPServer((args.host, args.port), StoveHandler)
    tcp_thread = threading.Thread(target=tcp_server.serve_forever, daemon=True)
    tcp_thread.start()
    log.info("TCP stove emulator listening on %s:%d", args.host, args.port)

    # HTTP UI server thread
    ui_server = HTTPServer((args.host, args.ui_port), UIHandler)
    ui_thread = threading.Thread(target=ui_server.serve_forever, daemon=True)
    ui_thread.start()
    log.info("Web UI available at http://localhost:%d", args.ui_port)
    log.info("Configure Home Assistant: host=<this-machine-ip>, port=%d", args.port)
    log.info("Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down.")
        tcp_server.shutdown()
        ui_server.shutdown()


if __name__ == "__main__":
    main()