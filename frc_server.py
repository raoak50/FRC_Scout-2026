"""
FRC 2026 REBUILT Scouting Server - IMPROVED QR SCANNER
Flask-based backend for QR code scanning and data management
"""

import csv
import json
import os
import sqlite3
from datetime import datetime
from io import BytesIO, StringIO

from flask import Flask, jsonify, render_template_string, request, send_file

app = Flask(__name__)

# Database initialization
def init_db():
    """Initialize SQLite database with improved schema"""
    conn = sqlite3.connect('frc_scouting.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_number INTEGER NOT NULL,
            team_number INTEGER NOT NULL,
            scout_name TEXT NOT NULL,
            auto_balls INTEGER DEFAULT 0,
            auto_climb TEXT DEFAULT 'None',
            teleop_balls INTEGER DEFAULT 0,
            endgame_climb TEXT DEFAULT 'None',
            match_outcome TEXT DEFAULT 'Unknown',
            played_defense BOOLEAN DEFAULT 0,
            robot_broke BOOLEAN DEFAULT 0,
            notes TEXT,
            timestamp TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(match_number, team_number)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            team_number INTEGER PRIMARY KEY,
            team_name TEXT,
            matches_scouted INTEGER DEFAULT 0,
            avg_auto_balls REAL,
            avg_teleop_balls REAL,
            auto_climb_distribution TEXT,
            endgame_climb_distribution TEXT,
            win_rate REAL,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_team_number ON matches(team_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_match_number ON matches(match_number)')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized with improved schema")

# QR Scanner Interface (HTML) - IMPROVED VERSION
SCANNER_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FRC QR Scanner Station</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #1a1a1a 0%, #0d0d0d 100%);
            color: white;
            padding: 2rem;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            text-align: center;
            margin-bottom: 2rem;
            padding: 2rem;
            background: #2a2a2a;
            border-radius: 12px;
            border: 2px solid #0066cc;
        }
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #0066cc, #00ccff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .scanner-section {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
            margin-bottom: 2rem;
        }
        .camera-container {
            background: #2a2a2a;
            border-radius: 12px;
            padding: 1.5rem;
            border: 2px solid #404040;
        }
        #video {
            width: 100%;
            border-radius: 8px;
            background: #000;
            max-height: 400px;
        }
        canvas { display: none; }
        .status {
            padding: 1rem;
            margin-top: 1rem;
            border-radius: 8px;
            font-weight: 600;
            text-align: center;
        }
        .status.ready { background: #004a99; color: #fff; }
        .status.success { background: #00a854; color: #fff; }
        .status.error { background: #e60000; color: #fff; }
        .status.scanning { background: #ff9500; color: #fff; }
        .data-preview {
            background: #2a2a2a;
            border-radius: 12px;
            padding: 1.5rem;
            border: 2px solid #404040;
            max-height: 600px;
            overflow-y: auto;
        }
        .data-preview h3 {
            color: #0066cc;
            margin-bottom: 1rem;
            font-size: 1.25rem;
        }
        .data-field {
            display: grid;
            grid-template-columns: 150px 1fr;
            padding: 0.75rem;
            background: #1a1a1a;
            margin-bottom: 0.5rem;
            border-radius: 6px;
        }
        .data-field strong { color: #00ccff; }
        .controls {
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
        }
        .btn {
            flex: 1;
            padding: 1rem;
            font-size: 1.125rem;
            font-weight: 700;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, #0066cc, #0088ff);
            color: white;
        }
        .btn-success {
            background: linear-gradient(135deg, #00a854, #00d968);
            color: white;
        }
        .btn-danger {
            background: linear-gradient(135deg, #cc0000, #ff3333);
            color: white;
        }
        .btn:hover { transform: translateY(-2px); }
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1rem;
        }
        .stat-card {
            background: #2a2a2a;
            border-radius: 12px;
            padding: 1.5rem;
            text-align: center;
            border: 2px solid #404040;
        }
        .stat-number {
            font-size: 2.5rem;
            font-weight: 900;
            color: #00ccff;
            margin-bottom: 0.5rem;
        }
        .stat-label {
            color: #b3b3b3;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .recent-matches {
            background: #2a2a2a;
            border-radius: 12px;
            padding: 1.5rem;
            border: 2px solid #404040;
            margin-top: 2rem;
        }
        .match-row {
            display: grid;
            grid-template-columns: 80px 100px 150px 100px 100px 100px 100px 1fr;
            padding: 0.75rem;
            background: #1a1a1a;
            margin-bottom: 0.5rem;
            border-radius: 6px;
            font-size: 0.875rem;
        }
        .match-row.header {
            background: #0066cc;
            font-weight: 700;
        }
        .debug-info {
            background: #1a1a1a;
            padding: 1rem;
            border-radius: 8px;
            margin-top: 1rem;
            font-family: monospace;
            font-size: 0.875rem;
            color: #00ff00;
        }
        @media (max-width: 968px) {
            .scanner-section {
                grid-template-columns: 1fr;
            }
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎥 FRC QR Scanner Station</h1>
            <p>Position QR code in camera view to scan</p>
        </div>

        <div class="scanner-section">
            <div class="camera-container">
                <video id="video" autoplay playsinline></video>
                <canvas id="canvas"></canvas>
                <div id="status" class="status ready">📷 Click "Start Scanning" to begin</div>
                <div class="controls">
                    <button class="btn btn-primary" id="startBtn" onclick="startScanning()">Start Scanning</button>
                    <button class="btn btn-danger" id="stopBtn" onclick="stopScanning()" disabled>Stop</button>
                </div>
                <div class="debug-info" id="debugInfo">Waiting to start...</div>
            </div>

            <div class="data-preview">
                <h3>Last Scanned Data</h3>
                <div id="preview">
                    <p style="color: #666; text-align: center; padding: 2rem;">
                        No data scanned yet
                    </p>
                </div>
                <button class="btn btn-success" id="submitBtn" onclick="submitData()" style="display:none; margin-top: 1rem;">
                    ✅ Submit to Database
                </button>
            </div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number" id="totalMatches">0</div>
                <div class="stat-label">Total Matches</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalTeams">0</div>
                <div class="stat-label">Teams Scouted</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="avgAuto">0.0</div>
                <div class="stat-label">Avg Auto Balls</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="avgTeleop">0.0</div>
                <div class="stat-label">Avg Teleop Balls</div>
            </div>
        </div>

        <div class="recent-matches">
            <h3 style="color: #0066cc; margin-bottom: 1rem;">Recent Scans</h3>
            <div class="match-row header">
                <div>Match</div>
                <div>Team</div>
                <div>Scout</div>
                <div>Auto</div>
                <div>Auto Climb</div>
                <div>Teleop</div>
                <div>Endgame</div>
                <div>Outcome</div>
            </div>
            <div id="recentScans"></div>
        </div>
    </div>

    <!-- Load jsQR from CDN -->
    <script src="https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.js"></script>
    
    <script>
        let video = document.getElementById('video');
        let canvas = document.getElementById('canvas');
        let ctx = canvas.getContext('2d');
        let scanning = false;
        let currentData = null;
        let recentScans = [];
        let scanCount = 0;

        function updateDebug(message) {
            const debugEl = document.getElementById('debugInfo');
            debugEl.textContent = message;
            console.log('[DEBUG]', message);
        }

        async function startScanning() {
            updateDebug('Requesting camera access...');
            
            try {
                // Try to get camera with different constraints
                let stream;
                try {
                    // First try with environment camera (back camera on mobile)
                    stream = await navigator.mediaDevices.getUserMedia({ 
                        video: { 
                            facingMode: 'environment',
                            width: { ideal: 1280 },
                            height: { ideal: 720 }
                        } 
                    });
                } catch (e) {
                    // If that fails, try any camera
                    updateDebug('Environment camera not found, trying default...');
                    stream = await navigator.mediaDevices.getUserMedia({ 
                        video: { 
                            width: { ideal: 1280 },
                            height: { ideal: 720 }
                        } 
                    });
                }
                
                video.srcObject = stream;
                scanning = true;
                
                document.getElementById('startBtn').disabled = true;
                document.getElementById('stopBtn').disabled = false;
                document.getElementById('status').textContent = '🔍 Scanning for QR codes...';
                document.getElementById('status').className = 'status scanning';
                
                updateDebug('Camera active! Waiting for video to load...');
                
                // Wait for video to be ready
                video.onloadedmetadata = () => {
                    updateDebug(`Video ready: ${video.videoWidth}x${video.videoHeight}`);
                    requestAnimationFrame(scan);
                };
                
            } catch (err) {
                document.getElementById('status').textContent = '❌ Camera access denied: ' + err.message;
                document.getElementById('status').className = 'status error';
                updateDebug('ERROR: ' + err.message);
                console.error(err);
            }
        }

        function stopScanning() {
            scanning = false;
            if (video.srcObject) {
                video.srcObject.getTracks().forEach(track => track.stop());
            }
            document.getElementById('startBtn').disabled = false;
            document.getElementById('stopBtn').disabled = true;
            document.getElementById('status').textContent = '⏸️ Scanning stopped';
            document.getElementById('status').className = 'status ready';
            updateDebug('Scanning stopped');
        }

        function scan() {
            if (!scanning) return;

            // Check if video is ready
            if (video.readyState !== video.HAVE_ENOUGH_DATA) {
                requestAnimationFrame(scan);
                return;
            }

            // Set canvas size to match video
            canvas.height = video.videoHeight;
            canvas.width = video.videoWidth;
            
            if (canvas.width === 0 || canvas.height === 0) {
                requestAnimationFrame(scan);
                return;
            }

            // Draw video frame to canvas
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            
            // Get image data
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            
            // Check if jsQR is loaded
            if (typeof jsQR === 'undefined') {
                updateDebug('ERROR: jsQR library not loaded!');
                document.getElementById('status').textContent = '❌ QR scanner library not loaded';
                document.getElementById('status').className = 'status error';
                return;
            }
            
            // Scan for QR code
            const code = jsQR(imageData.data, imageData.width, imageData.height, {
                inversionAttempts: "dontInvert",
            });

            scanCount++;
            if (scanCount % 30 === 0) { // Update debug every 30 frames
                updateDebug(`Scanning... (${scanCount} frames checked, ${canvas.width}x${canvas.height})`);
            }

            if (code) {
                updateDebug('QR Code detected! Data length: ' + code.data.length);
                try {
                    currentData = JSON.parse(code.data);
                    displayData(currentData);
                    document.getElementById('status').textContent = '✅ QR Code detected successfully!';
                    document.getElementById('status').className = 'status success';
                    document.getElementById('submitBtn').style.display = 'block';
                    updateDebug('QR parsed successfully: Match ' + currentData.matchNumber + ', Team ' + currentData.teamNumber);
                    
                    // Optional: Stop scanning after successful read
                    // stopScanning();
                } catch (e) {
                    document.getElementById('status').textContent = '❌ Invalid QR code format: ' + e.message;
                    document.getElementById('status').className = 'status error';
                    updateDebug('Parse error: ' + e.message);
                }
            }

            requestAnimationFrame(scan);
        }

        function displayData(data) {
            const preview = document.getElementById('preview');
            preview.innerHTML = `
                <div class="data-field">
                    <strong>Match:</strong>
                    <div>${data.matchNumber}</div>
                </div>
                <div class="data-field">
                    <strong>Team:</strong>
                    <div>${data.teamNumber}</div>
                </div>
                <div class="data-field">
                    <strong>Scout:</strong>
                    <div>${data.scoutName}</div>
                </div>
                <div class="data-field">
                    <strong>Auto Balls:</strong>
                    <div>${data.autonomous.ballsScored}</div>
                </div>
                <div class="data-field">
                    <strong>Auto Climb:</strong>
                    <div>${data.autonomous.climbLevel}</div>
                </div>
                <div class="data-field">
                    <strong>Teleop Balls:</strong>
                    <div>${data.teleop.ballsScored}</div>
                </div>
                <div class="data-field">
                    <strong>Endgame Climb:</strong>
                    <div>${data.endgame.climbLevel}</div>
                </div>
                <div class="data-field">
                    <strong>Match Outcome:</strong>
                    <div>${data.matchOutcome}</div>
                </div>
                <div class="data-field">
                    <strong>Played Defense:</strong>
                    <div>${data.robotStatus.playedDefense ? 'Yes' : 'No'}</div>
                </div>
                <div class="data-field">
                    <strong>Robot Broke:</strong>
                    <div>${data.robotStatus.robotBroke ? 'Yes' : 'No'}</div>
                </div>
                <div class="data-field">
                    <strong>Notes:</strong>
                    <div>${data.notes || 'None'}</div>
                </div>
            `;
        }

        async function submitData() {
            if (!currentData) return;

            updateDebug('Submitting data to server...');
            
            try {
                const response = await fetch('/api/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(currentData)
                });

                const result = await response.json();

                if (response.ok) {
                    document.getElementById('status').textContent = '✅ Data saved successfully!';
                    document.getElementById('status').className = 'status success';
                    updateDebug('Data saved to database!');
                    
                    recentScans.unshift(currentData);
                    if (recentScans.length > 5) recentScans.pop();
                    updateRecentScans();
                    
                    await updateStats();
                    
                    document.getElementById('submitBtn').style.display = 'none';
                    currentData = null;
                    
                    setTimeout(() => {
                        document.getElementById('preview').innerHTML = '<p style="color: #666; text-align: center; padding: 2rem;">Ready for next scan</p>';
                        document.getElementById('status').textContent = '🔍 Scanning for QR codes...';
                        document.getElementById('status').className = 'status scanning';
                    }, 2000);
                } else {
                    throw new Error(result.error || 'Submission failed');
                }
            } catch (err) {
                document.getElementById('status').textContent = '❌ ' + err.message;
                document.getElementById('status').className = 'status error';
                updateDebug('Submit error: ' + err.message);
                console.error(err);
            }
        }

        function updateRecentScans() {
            const container = document.getElementById('recentScans');
            container.innerHTML = recentScans.map(s => `
                <div class="match-row">
                    <div>${s.matchNumber}</div>
                    <div>${s.teamNumber}</div>
                    <div>${s.scoutName}</div>
                    <div>${s.autonomous.ballsScored}</div>
                    <div>${s.autonomous.climbLevel}</div>
                    <div>${s.teleop.ballsScored}</div>
                    <div>${s.endgame.climbLevel}</div>
                    <div>${s.matchOutcome}</div>
                </div>
            `).join('');
        }

        async function updateStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                document.getElementById('totalMatches').textContent = stats.total_matches;
                document.getElementById('totalTeams').textContent = stats.unique_teams;
                document.getElementById('avgAuto').textContent = stats.avg_auto.toFixed(1);
                document.getElementById('avgTeleop').textContent = stats.avg_teleop.toFixed(1);
            } catch (err) {
                console.error('Failed to update stats:', err);
            }
        }

        // Load stats on page load
        updateStats();
        
        // Check if jsQR loaded
        window.addEventListener('load', () => {
            if (typeof jsQR === 'undefined') {
                updateDebug('WARNING: jsQR library failed to load!');
                document.getElementById('status').textContent = '❌ QR scanner library not loaded. Check internet connection.';
                document.getElementById('status').className = 'status error';
            } else {
                updateDebug('jsQR library loaded successfully!');
            }
        });
    </script>
</body>
</html>
"""

# API Routes (same as before)
@app.route('/')
def scanner():
    """QR scanner interface"""
    return render_template_string(SCANNER_PAGE)

@app.route('/api/submit', methods=['POST'])
def submit_match():
    """Process scanned QR code data"""
    try:
        data = request.json
        
        # Validate required fields
        required = ['matchNumber', 'teamNumber', 'scoutName']
        if not all(k in data for k in required):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Insert into database
        conn = sqlite3.connect('frc_scouting.db')
        cursor = conn.cursor()
        
        # Check for duplicates
        cursor.execute('''
            SELECT id FROM matches 
            WHERE match_number = ? AND team_number = ?
        ''', (data['matchNumber'], data['teamNumber']))
        
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'Duplicate entry detected'}), 409
        
        # Insert match data with new schema
        cursor.execute('''
            INSERT INTO matches (
                match_number, team_number, scout_name,
                auto_balls, auto_climb,
                teleop_balls, endgame_climb,
                match_outcome, played_defense, robot_broke,
                notes, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['matchNumber'],
            data['teamNumber'],
            data['scoutName'],
            data['autonomous']['ballsScored'],
            data['autonomous'].get('climbLevel', 'None'),
            data['teleop']['ballsScored'],
            data['endgame']['climbLevel'],
            data.get('matchOutcome', 'Unknown'),
            data.get('robotStatus', {}).get('playedDefense', False),
            data.get('robotStatus', {}).get('robotBroke', False),
            data.get('notes', ''),
            data['timestamp']
        ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Saved: Match {data['matchNumber']}, Team {data['teamNumber']}")
        
        return jsonify({
            'success': True,
            'match': data['matchNumber'],
            'team': data['teamNumber']
        })
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get overall statistics"""
    conn = sqlite3.connect('frc_scouting.db')
    cursor = conn.cursor()
    
    # Total matches
    cursor.execute('SELECT COUNT(*) FROM matches')
    total_matches = cursor.fetchone()[0]
    
    # Unique teams
    cursor.execute('SELECT COUNT(DISTINCT team_number) FROM matches')
    unique_teams = cursor.fetchone()[0]
    
    # Average auto balls
    cursor.execute('SELECT AVG(auto_balls) FROM matches')
    avg_auto = cursor.fetchone()[0] or 0
    
    # Average teleop balls
    cursor.execute('SELECT AVG(teleop_balls) FROM matches')
    avg_teleop = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'total_matches': total_matches,
        'unique_teams': unique_teams,
        'avg_auto': avg_auto,
        'avg_teleop': avg_teleop
    })

@app.route('/api/export/csv')
def export_csv():
    """Export all data as CSV with improved fields"""
    conn = sqlite3.connect('frc_scouting.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT match_number, team_number, scout_name,
               auto_balls, auto_climb, teleop_balls,
               endgame_climb, match_outcome, played_defense, robot_broke,
               notes, timestamp
        FROM matches
        ORDER BY match_number, team_number
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Match', 'Team', 'Scout', 'Auto Balls', 'Auto Climb',
        'Teleop Balls', 'Endgame Climb', 'Match Outcome', 
        'Played Defense', 'Robot Broke', 'Notes', 'Timestamp'
    ])
    writer.writerows(rows)
    
    # Convert to BytesIO for file download
    mem = BytesIO()
    mem.write(output.getvalue().encode('utf-8'))
    mem.seek(0)
    output.close()
    
    return send_file(
        mem,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'frc_scouting_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@app.route('/api/team/<int:team_number>')
def get_team_stats(team_number):
    """Get statistics for a specific team"""
    conn = sqlite3.connect('frc_scouting.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT match_number, auto_balls, auto_climb,
               teleop_balls, endgame_climb, match_outcome,
               played_defense, robot_broke, notes
        FROM matches
        WHERE team_number = ?
        ORDER BY match_number
    ''', (team_number,))
    
    matches = cursor.fetchall()
    conn.close()
    
    if not matches:
        return jsonify({'error': 'Team not found'}), 404
    
    # Calculate stats
    auto_balls = [m[1] for m in matches]
    teleop_balls = [m[3] for m in matches]
    
    # Count climb distributions
    auto_climb_counts = {
        'None': 0, 'Level 1': 0, 'Level 2': 0, 'Level 3': 0
    }
    endgame_climb_counts = {
        'None': 0, 'Level 1': 0, 'Level 2': 0, 'Level 3': 0
    }
    
    for match in matches:
        auto_climb_counts[match[2]] = auto_climb_counts.get(match[2], 0) + 1
        endgame_climb_counts[match[4]] = endgame_climb_counts.get(match[4], 0) + 1
    
    # Calculate win rate
    wins = sum([1 for m in matches if m[5] == 'Won'])
    win_rate = wins / len(matches) if len(matches) > 0 else 0
    
    # Calculate defense and breakdown rates
    defense_count = sum([m[6] for m in matches])
    breakdown_count = sum([m[7] for m in matches])
    
    return jsonify({
        'team_number': team_number,
        'total_matches': len(matches),
        'avg_auto_balls': sum(auto_balls) / len(auto_balls) if auto_balls else 0,
        'avg_teleop_balls': sum(teleop_balls) / len(teleop_balls) if teleop_balls else 0,
        'auto_climb_distribution': auto_climb_counts,
        'endgame_climb_distribution': endgame_climb_counts,
        'win_rate': win_rate,
        'defense_rate': defense_count / len(matches) if len(matches) > 0 else 0,
        'breakdown_rate': breakdown_count / len(matches) if len(matches) > 0 else 0,
        'matches': [
            {
                'match': m[0],
                'auto_balls': m[1],
                'auto_climb': m[2],
                'teleop_balls': m[3],
                'endgame_climb': m[4],
                'outcome': m[5],
                'played_defense': bool(m[6]),
                'robot_broke': bool(m[7]),
                'notes': m[8]
            } for m in matches
        ]
    })

@app.route('/api/matches')
def get_all_matches():
    """Get all match data"""
    conn = sqlite3.connect('frc_scouting.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT match_number, team_number, scout_name,
               auto_balls, auto_climb, teleop_balls,
               endgame_climb, match_outcome, played_defense, 
               robot_broke, notes, timestamp
        FROM matches
        ORDER BY match_number DESC, team_number
    ''')
    
    matches = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'matches': [
            {
                'matchNumber': m[0],
                'teamNumber': m[1],
                'scoutName': m[2],
                'autonomous': {
                    'ballsScored': m[3],
                    'climbLevel': m[4]
                },
                'teleop': {
                    'ballsScored': m[5]
                },
                'endgame': {
                    'climbLevel': m[6]
                },
                'matchOutcome': m[7],
                'robotStatus': {
                    'playedDefense': bool(m[8]),
                    'robotBroke': bool(m[9])
                },
                'notes': m[10],
                'timestamp': m[11]
            } for m in matches
        ]
    })

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    print("=" * 60)
    print("🚀 FRC 2026 REBUILT Scouting Server Starting...")
    print("=" * 60)
    print(f"📊 Scanner Interface: http://localhost:5000")
    print(f"📈 Statistics API: http://localhost:5000/api/stats")
    print(f"📥 CSV Export: http://localhost:5000/api/export/csv")
    print(f"🤖 Team Stats: http://localhost:5000/api/team/<team_number>")
    print(f"📋 All Matches: http://localhost:5000/api/matches")
    print("=" * 60)
    print("✅ Server ready! Open the scanner interface in your browser.")
    print("🎥 Grant camera permissions when prompted.")
    print("=" * 60)
    
    # Run server
    app.run(host='0.0.0.0', port=5000, debug=True)
