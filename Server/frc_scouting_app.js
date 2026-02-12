"""
FRC 2026 MASTER SERVER
Supports: L1-L3 Climbing in BOTH Auto and Endgame
"""
import sqlite3
import json
import csv
import os
from io import StringIO
from flask import Flask, render_template_string, request, jsonify, Response

app = Flask(__name__)
DB_FILE = 'frc_scouting.db'

# --- DATABASE SETUP ---
def init_db():
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('''
CREATE TABLE IF NOT EXISTS matches (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  match_number INTEGER,
  team_number INTEGER,
  scout_name TEXT,
  data_json TEXT,
  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(match_number, team_number)
)
''')
conn.commit()
conn.close()

# --- SCANNER INTERFACE ---
SCANNER_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>FRC Scanner</title>
<script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>
<style>
body { background: #1a1a1a; color: white; font-family: sans-serif; text-align: center; padding: 10px; }
.nav { margin-bottom: 20px; }
.nav a { color: #00ccff; margin: 0 10px; text-decoration: none; font-size: 1.2rem; border-bottom: 1px solid #00ccff; }
#reader { width: 100%; max-width: 500px; margin: 0 auto; border: 4px solid #333; border-radius: 10px; }
.success-box { background: #004d26; border: 2px solid #00d968; padding: 20px; border-radius: 10px; margin-top: 20px; display: none; }
.btn { padding: 15px 30px; font-size: 1.2rem; border: none; border-radius: 6px; cursor: pointer; margin-top: 10px; width: 100%; max-width: 300px; }
.btn-primary { background: #0066cc; color: white; }
</style>
</head>
<body>
<div class="nav">
<a href="/">📷 Scanner</a>
<a href="/view">📊 View Data</a>
</div>

<div id="reader"></div>

<div id="successDisplay" class="success-box">
<h2 style="margin:0 0 10px 0;">✅ Scan Successful!</h2>
<div id="scanDetails" style="font-size: 1.2rem; margin-bottom: 15px; color: #ccffdd;"></div>
<button class="btn btn-primary" onclick="submitToDb()">💾 Save to Database</button>
</div>

<script>
let currentData = null;
let scanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });

function onScan(decodedText) {
  try {
    let raw = JSON.parse(decodedText);

    // --- UNPACKING ENGINE ---
    currentData = {
      matchNumber: raw.m,
      teamNumber: raw.t,
      scoutName: raw.s || 'Unknown',
      autoBalls: raw.ab || 0,
      autoClimb: raw.ac || 'None', // Will now be 'L1', 'L2', 'L3'
      teleBalls: raw.tb || 0,
      endClimb: raw.ec || 'None',  // 'L1', 'L2', 'L3'
      outcome: raw.o || 'None',
      defense: raw.df === 1 ? 'Yes' : 'No',
      broken: raw.br === 1 ? 'Yes' : 'No',
      notes: raw.n || ''
    };

    document.getElementById('scanDetails').innerHTML =
    `Match <strong>${currentData.matchNumber}</strong> - Team <strong>${currentData.teamNumber}</strong><br>` +
    `Auto Climb: ${currentData.autoClimb} | End Climb: ${currentData.endClimb}`;

    document.getElementById('successDisplay').style.display = 'block';
    document.getElementById('reader').style.display = 'none';
    new Audio('https://raw.githubusercontent.com/maykbrito/libs/main/scanner.mp3').play();
    scanner.pause();

  } catch(e) { console.error("Parse error", e); }
}

scanner.render(onScan);

async function submitToDb() {
  if(!currentData) return;
  try {
    const res = await fetch('/api/submit', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(currentData)
    });
    if(res.ok) {
      alert("✅ Saved!");
      location.reload();
    } else {
      alert("❌ Error saving");
    }
  } catch(e) { alert("❌ Network Error"); }
}
</script>
</body>
</html>
"""

# --- DASHBOARD HTML ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>FRC Data</title>
<style>
body { background: #1a1a1a; color: white; font-family: sans-serif; padding: 20px; }
.nav { margin-bottom: 30px; text-align: center; }
.nav a { color: #00ccff; margin: 0 15px; text-decoration: none; font-size: 1.2rem; border-bottom: 1px solid #00ccff; }
table { width: 100%; border-collapse: collapse; background: #2a2a2a; }
th, td { padding: 10px; text-align: left; border-bottom: 1px solid #444; }
th { background: #333; color: #00ccff; }
.btn-csv { background: #00a854; color: white; padding: 10px; text-decoration: none; border-radius: 5px; display:inline-block; margin-bottom:20px;}
.btn-del { background: #ff3333; color: white; border: none; padding: 5px; cursor: pointer; }
</style>
</head>
<body>
<div class="nav">
<a href="/">📷 Scanner</a>
<a href="/view">📊 View Data</a>
</div>

<a href="/api/export_csv" class="btn-csv">📥 Download CSV (Excel)</a>

<table>
<thead>
<tr>
<th>Match</th>
<th>Team</th>
<th>Auto Balls</th>
<th>Auto Climb</th>
<th>Teleop</th>
<th>End Climb</th>
<th>Status</th>
<th>Action</th>
</tr>
</thead>
<tbody>
{% for r in matches %}
<tr>
<td>{{ r.matchNumber }}</td>
<td>{{ r.teamNumber }}</td>
<td>{{ r.autoBalls }}</td>
<td>{{ r.autoClimb }}</td> <td>{{ r.teleBalls }}</td>
<td>{{ r.endClimb }}</td> <td>
{% if r.broken == 'Yes' %}💀{% endif %}
{% if r.defense == 'Yes' %}🛡️{% endif %}
</td>
<td><button class="btn-del" onclick="del({{ r.id }})">X</button></td>
</tr>
{% endfor %}
</tbody>
</table>
<script>
async function del(id) {
  if(confirm("Delete match?")) {
    await fetch('/api/delete/' + id, { method: 'POST' });
    location.reload();
  }
}
</script>
</body>
</html>
"""

# --- ROUTES ---
@app.route('/')
def home():
return render_template_string(SCANNER_HTML)

@app.route('/view')
def view_data():
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute("SELECT id, data_json FROM matches ORDER BY match_number DESC")
rows = c.fetchall()
conn.close()

clean_data = []
for r in rows:
  try:
  d = json.loads(r[1])
  d['id'] = r[0]
  clean_data.append(d)
  except: pass

  return render_template_string(DASHBOARD_HTML, matches=clean_data)

  @app.route('/api/submit', methods=['POST'])
  def submit():
  try:
  data = request.json
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute('''
  INSERT OR REPLACE INTO matches
  (match_number, team_number, scout_name, data_json)
  VALUES (?, ?, ?, ?)
  ''', (data['matchNumber'], data['teamNumber'], data['scoutName'], json.dumps(data)))
  conn.commit()
  conn.close()
  return jsonify({'success': True})
  except Exception as e:
  return jsonify({'error': str(e)}), 500

  @app.route('/api/delete/<int:match_id>', methods=['POST'])
  def delete_match(match_id):
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("DELETE FROM matches WHERE id = ?", (match_id,))
  conn.commit()
  conn.close()
  return jsonify({'success': True})

  @app.route('/api/export_csv')
  def export_csv():
  conn = sqlite3.connect(DB_FILE)
  c = conn.cursor()
  c.execute("SELECT data_json FROM matches ORDER BY match_number")
  rows = c.fetchall()
  conn.close()

  si = StringIO()
  writer = csv.writer(si)

  # EXCEL HEADERS
  writer.writerow([
    'Match', 'Team', 'Scout',
    'Auto Balls', 'Auto Climb',
    'Teleop Balls',
    'Endgame Climb', 'Outcome',
    'Defense', 'Robot Broke', 'Notes'
  ])

  for r in rows:
    d = json.loads(r[0])
    writer.writerow([
      d.get('matchNumber'), d.get('teamNumber'), d.get('scoutName'),
                    d.get('autoBalls'), d.get('autoClimb'), # Will save L1/L2/L3 in Excel
                    d.get('teleBalls'),
                    d.get('endClimb'), d.get('outcome'),
                    d.get('defense'), d.get('broken'), d.get('notes')
    ])

    return Response(
      si.getvalue(),
                    mimetype="text/csv",
                    headers={"Content-disposition": "attachment; filename=frc_data.csv"}
    )

    if __name__ == '__main__':
      init_db()
      print("🚀 SERVER RUNNING on http://localhost:5000")
      app.run(host='0.0.0.0', port=5000, debug=True)
