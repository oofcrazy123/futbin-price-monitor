@app.route('/reliability')
def reliability_dashboard():
    """Show card reliability and market intelligence dashboard"""
    try:
        conn = sqlite3.connect('futbin_cards.db')
        cursor = conn.cursor()
        
        # Get reliability statistics
        cursor.execute('''
            SELECT 
                COUNT(*) as total_tracked,
                AVG(reliability_score) as avg_score,
                COUNT(CASE WHEN blacklisted = 1 THEN 1 END) as blacklisted_count,
                COUNT(CASE WHEN reliability_score < 30 THEN 1 END) as low_reliability_count
            FROM card_reliability
        ''')
        
        stats = cursor.fetchone()
        total_tracked, avg_score, blacklisted, low_reliability = stats or (0, 0, 0, 0)
        
        # Get top suspicious patterns
        cursor.execute('''
            SELECT pattern_type, COUNT(*) as count
            FROM price_pattern_history 
            WHERE flagged_as_suspicious = 1
            GROUP BY pattern_type
            ORDER BY count DESC
            LIMIT 5
        ''')
        
        suspicious_patterns = cursor.fetchall()
        
        # Get worst performing cards
        cursor.execute('''
            SELECT c.name, cr.reliability_score, cr.fake_alert_count, cr.valid_alert_count, cr.blacklisted
            FROM card_reliability cr
            JOIN cards c ON cr.card_id = c.id
            WHERE cr.fake_alert_count + cr.valid_alert_count >= 3
            ORDER BY cr.reliability_score ASC
            LIMIT 10
        ''')
        
        worst_cards = cursor.fetchall()
        
        conn.close()
        
        return f'''
        <html>
        <head><title>Market Intelligence Dashboard</title></head>
        <body style="font-family: Arial; max-width: 1000px; margin: 50px auto; padding: 20px;">
            <h1>🧠 Market Intelligence Dashboard</h1>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0;">
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center;">
                    <h3>Cards Tracked</h3>
                    <div style="font-size: 2em; font-weight: bold; color: #007cba;">{total_tracked}</div>
                </div>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center;">
                    <h3>Avg Reliability</h3>
                    <div style="font-size: 2em; font-weight: bold; color: #28a745;">{avg_score:.1f}%</div>
                </div>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center;">
                    <h3>Blacklisted</h3>
                    <div style="font-size: 2em; font-weight: bold; color: #dc3545;">{blacklisted}</div>
                </div>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center;">
                    <h3>Low Reliability</h3>
                    <div style="font-size: 2em; font-weight: bold; color: #ffc107;">{low# app.py (Web interface + background worker)
from flask import Flask, render_template, jsonify, send_file, request
import threading
import time
import os
from datetime import datetime
import sqlite3

app = Flask(__name__)

# Global monitor instance
monitor = None
monitor_thread = None
is_running = False

def start_monitor():
    """Start the price monitor in background"""
    global monitor, is_running
    
    print("🔄 Attempting to start monitor...")
    print(f"📁 Current directory: {os.getcwd()}")
    print(f"📋 Files in directory: {os.listdir('.')}")
    
    try:
        # Add delay to let Flask start properly
        print("⏳ Waiting 3 seconds for Flask to stabilize...")
        time.sleep(3)
        
        print("📦 Attempting to import FutbinPriceMonitor...")
        
        # Try to import step by step
        try:
            import futbin_monitor
            print("✅ Successfully imported futbin_monitor module")
        except ImportError as e:
            print(f"❌ Failed to import futbin_monitor: {e}")
            return
        
        try:
            from futbin_monitor import FutbinPriceMonitor
            print("✅ Successfully imported FutbinPriceMonitor class")
        except ImportError as e:
            print(f"❌ Failed to import FutbinPriceMonitor class: {e}")
            return
        
        print("🔧 Creating monitor instance...")
        try:
            monitor = FutbinPriceMonitor()
            print("✅ Monitor instance created successfully")
        except Exception as e:
            print(f"❌ Failed to create monitor instance: {e}")
            import traceback
            traceback.print_exc()
            return
        
        print("✅ Monitor initialized, starting complete system...")
        is_running = True
        
        print("🚀 Starting scraping and monitoring...")
        try:
            monitor.run_complete_system()
        except Exception as e:
            print(f"❌ Error in run_complete_system: {e}")
            import traceback
            traceback.print_exc()
            is_running = False
        
    except Exception as e:
        print(f"❌ Unexpected monitor error: {e}")
        is_running = False
        import traceback
        print("📋 Full error traceback:")
        traceback.print_exc()

@app.route('/')
def home():
    """Simple web interface to check status"""
    return '''
    <html>
    <head><title>Futbin Price Monitor</title></head>
    <body style="font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px;">
        <h1>&#129302; Futbin Price Gap Monitor</h1>
        <p>Your bot is running in the background!</p>
        
        <div style="background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 8px;">
            <h3>&#128202; Status</h3>
            <p id="status">Loading...</p>
            <button onclick="checkStatus()" style="padding: 10px 20px; background: #007cba; color: white; border: none; border-radius: 4px; cursor: pointer;">
                Refresh Status
            </button>
        </div>
        
        <div style="background: #e8f4f8; padding: 20px; margin: 20px 0; border-radius: 8px;">
            <h3>&#128295; Configuration</h3>
            <p><strong>Price Gap Threshold:</strong> 1,000+ coins & 5%+</p>
            <p><strong>Minimum Card Value:</strong> 5,000 coins</p>
            <p><strong>Check Interval:</strong> Every 45 minutes</p>
        </div>
        
        <div style="background: #f0f8e8; padding: 20px; margin: 20px 0; border-radius: 8px;">
            <h3>&#128241; Alerts</h3>
            <p>Trading opportunities are sent to your Telegram!</p>
            <p>Recent alerts will appear in your Telegram chat.</p>
        </div>
        
        <div style="background: #e8f0ff; padding: 20px; margin: 20px 0; border-radius: 8px;">
            <h3>&#128190; Database Backup</h3>
            <p><strong>Cards in Database:</strong> <span id="card-count">Loading...</span></p>
            <div style="margin: 15px 0;">
                <a href="/download-db" style="padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 4px; margin-right: 10px;">
                    Download Database Backup
                </a>
                <a href="/upload-db" style="padding: 10px 20px; background: #007cba; color: white; text-decoration: none; border-radius: 4px;">
                    Upload Database
                </a>
            </div>
            <p style="font-size: 0.9em; color: #666;">
                Download your database before making script changes to preserve card data.
            </p>
        </div>
        
        <div style="background: #fff3cd; padding: 20px; margin: 20px 0; border-radius: 8px; border: 1px solid #ffeaa7;">
            <h3>&#128269; Debug Info</h3>
            <p><strong>Monitor Thread Running:</strong> <span id="thread-status">Unknown</span></p>
            <p><strong>Environment Check:</strong> <span id="env-status">Checking...</span></p>
        </div>
        
        <div style="background: #f0f8ff; padding: 20px; margin: 20px 0; border-radius: 8px;">
            <h3>&#129504; Market Intelligence</h3>
            <p>Advanced pattern recognition and reliability scoring system</p>
            <a href="/reliability" style="padding: 10px 20px; background: #6f42c1; color: white; text-decoration: none; border-radius: 4px;">
                View Intelligence Dashboard
            </a>
        </div>
        
        <script>
            function checkStatus() {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('status').innerHTML = 
                            '<strong>Monitor Status:</strong> ' + (data.running ? '🟢 Running' : '🔴 Stopped') + '<br>' +
                            '<strong>Cards in Database:</strong> ' + data.card_count + '<br>' +
                            '<strong>Last Update:</strong> ' + data.last_update;
                        
                        document.getElementById('card-count').innerHTML = data.card_count.toLocaleString();
                        document.getElementById('thread-status').innerHTML = data.running ? '🟢 Yes' : '🔴 No';
                        document.getElementById('env-status').innerHTML = data.env_check;
                    });
            }
            
            // Auto-refresh every 30 seconds
            setInterval(checkStatus, 30000);
            checkStatus(); // Initial load
        </script>
    </body>
    </html>
    '''

@app.route('/download-db')
def download_db():
    """Download the current database file"""
    try:
        # Check if database exists and has data
        if not os.path.exists('futbin_cards.db'):
            return "No database file found", 404
        
        # Check if database has cards
        conn = sqlite3.connect('futbin_cards.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM cards')
        card_count = cursor.fetchone()[0]
        conn.close()
        
        if card_count == 0:
            return "Database is empty - no cards to download", 400
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'futbin_cards_backup_{timestamp}.db'
        
        return send_file('futbin_cards.db', 
                        as_attachment=True, 
                        download_name=filename,
                        mimetype='application/octet-stream')
    
    except Exception as e:
        return f"Error downloading database: {str(e)}", 500

@app.route('/upload-db', methods=['GET', 'POST'])
def upload_db():
    """Upload a database file to restore data"""    
    if request.method == 'GET':
        return '''
        <html>
        <head><title>Upload Database</title></head>
        <body style="font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px;">
            <h1>Upload Database Backup</h1>
            <p>Upload a previously downloaded database file to restore your card data.</p>
            
            <form method="POST" enctype="multipart/form-data">
                <div style="margin: 20px 0;">
                    <label for="database">Select Database File (.db):</label><br>
                    <input type="file" name="database" accept=".db" required style="margin: 10px 0;">
                </div>
                <div style="margin: 20px 0;">
                    <input type="submit" value="Upload Database" 
                           style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer;">
                </div>
            </form>
            
            <div style="background: #fff3cd; padding: 15px; margin: 20px 0; border-radius: 5px;">
                <strong>Warning:</strong> This will replace your current database. Make sure to download a backup first if needed.
            </div>
            
            <a href="/">← Back to Dashboard</a>
        </body>
        </html>
        '''
    
    try:
        if 'database' not in request.files:
            return "No file uploaded", 400
        
        file = request.files['database']
        if file.filename == '':
            return "No file selected", 400
        
        if file and file.filename.endswith('.db'):
            # Save uploaded file as the main database
            file.save('futbin_cards.db')
            
            # Verify the uploaded database
            conn = sqlite3.connect('futbin_cards.db')
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM cards')
            card_count = cursor.fetchone()[0]
            conn.close()
            
            return f'''
            <html>
            <head><title>Upload Success</title></head>
            <body style="font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px;">
                <h1>✅ Database Uploaded Successfully!</h1>
                <p>Restored database with <strong>{card_count:,}</strong> cards.</p>
                <p>The bot will now use this data for price monitoring.</p>
                <a href="/">← Back to Dashboard</a>
            </body>
            </html>
            '''
        else:
            return "Invalid file type. Please upload a .db file.", 400
            
    except Exception as e:
        return f"Error uploading database: {str(e)}", 500

@app.route('/reliability')
def reliability_dashboard():
    """Show card reliability and market intelligence dashboard"""
    try:
        conn = sqlite3.connect('futbin_cards.db')
        cursor = conn.cursor()
        
        # Get reliability statistics
        cursor.execute('''
            SELECT 
                COUNT(*) as total_tracked,
                AVG(reliability_score) as avg_score,
                COUNT(CASE WHEN blacklisted = 1 THEN 1 END) as blacklisted_count,
                COUNT(CASE WHEN reliability_score < 30 THEN 1 END) as low_reliability_count
            FROM card_reliability
        ''')
        
        stats = cursor.fetchone()
        total_tracked, avg_score, blacklisted, low_reliability = stats or (0, 0, 0, 0)
        
        # Get top suspicious patterns
        cursor.execute('''
            SELECT pattern_type, COUNT(*) as count
            FROM price_pattern_history 
            WHERE flagged_as_suspicious = 1
            GROUP BY pattern_type
            ORDER BY count DESC
            LIMIT 5
        ''')
        
        suspicious_patterns = cursor.fetchall()
        
        # Get worst performing cards
        cursor.execute('''
            SELECT c.name, cr.reliability_score, cr.fake_alert_count, cr.valid_alert_count, cr.blacklisted
            FROM card_reliability cr
            JOIN cards c ON cr.card_id = c.id
            WHERE cr.fake_alert_count + cr.valid_alert_count >= 3
            ORDER BY cr.reliability_score ASC
            LIMIT 10
        ''')
        
        worst_cards = cursor.fetchall()
        
        conn.close()
        
        return f'''
        <html>
        <head><title>Market Intelligence Dashboard</title></head>
        <body style="font-family: Arial; max-width: 1000px; margin: 50px auto; padding: 20px;">
            <h1>🧠 Market Intelligence Dashboard</h1>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0;">
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center;">
                    <h3>Cards Tracked</h3>
                    <div style="font-size: 2em; font-weight: bold; color: #007cba;">{total_tracked}</div>
                </div>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center;">
                    <h3>Avg Reliability</h3>
                    <div style="font-size: 2em; font-weight: bold; color: #28a745;">{avg_score:.1f}%</div>
                </div>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center;">
                    <h3>Blacklisted</h3>
                    <div style="font-size: 2em; font-weight: bold; color: #dc3545;">{blacklisted}</div>
                </div>
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center;">
                    <h3>Low Reliability</h3>
                    <div style="font-size: 2em; font-weight: bold; color: #ffc107;">{low_reliability}</div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin: 30px 0;">
                <div style="background: #fff; padding: 20px; border-radius: 8px; border: 1px solid #dee2e6;">
                    <h3>🚨 Suspicious Patterns Detected</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="background: #f8f9fa;">
                            <th style="padding: 10px; text-align: left; border-bottom: 1px solid #dee2e6;">Pattern Type</th>
                            <th style="padding: 10px; text-align: right; border-bottom: 1px solid #dee2e6;">Count</th>
                        </tr>
                        {''.join(f'<tr><td style="padding: 8px; border-bottom: 1px solid #f1f3f4;">{pattern}</td><td style="padding: 8px; text-align: right; border-bottom: 1px solid #f1f3f4;">{count}</td></tr>' for pattern, count in suspicious_patterns)}
                    </table>
                </div>
                
                <div style="background: #fff; padding: 20px; border-radius: 8px; border: 1px solid #dee2e6;">
                    <h3>⚠️ Worst Performing Cards</h3>
                    <table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">
                        <tr style="background: #f8f9fa;">
                            <th style="padding: 8px; text-align: left; border-bottom: 1px solid #dee2e6;">Player</th>
                            <th style="padding: 8px; text-align: right; border-bottom: 1px solid #dee2e6;">Score</th>
                            <th style="padding: 8px; text-align: center; border-bottom: 1px solid #dee2e6;">Status</th>
                        </tr>
                        {''.join(f'<tr><td style="padding: 6px; border-bottom: 1px solid #f1f3f4;">{name[:15]}...</td><td style="padding: 6px; text-align: right; border-bottom: 1px solid #f1f3f4;">{score:.0f}%</td><td style="padding: 6px; text-align: center; border-bottom: 1px solid #f1f3f4;">{"🚫" if blacklisted else "⚠️"}</td></tr>' for name, score, fake, valid, blacklisted in worst_cards)}
                    </table>
                </div>
            </div>
            
            <div style="background: #e7f3ff; padding: 20px; border-radius: 8px; margin: 30px 0;">
                <h3>📊 How Market Intelligence Works</h3>
                <p><strong>Pattern Recognition:</strong> Detects suspicious price patterns like extreme outliers, round number clustering, isolated low prices, and bot-like sequential pricing.</p>
                <p><strong>Reliability Scoring:</strong> Each card gets a score (0-100) based on how often its alerts are legitimate vs fake. Low-scoring cards get filtered out.</p>
                <p><strong>Auto-Blacklisting:</strong> Cards with reliability scores below 20% and multiple failed alerts are automatically blocked from generating future alerts.</p>
                <p><strong>Learning System:</strong> The bot continuously learns which cards produce genuine opportunities vs market manipulation attempts.</p>
            </div>
            
            <a href="/">← Back to Dashboard</a>
        </body>
        </html>
        '''
        
    except Exception as e:
        return f"Error loading reliability dashboard: {str(e)}", 500

@app.route('/status')
def status():
    """API endpoint to check bot status"""
    try:
        # Check database
        try:
            conn = sqlite3.connect('futbin_cards.db')
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM cards')
            card_count = cursor.fetchone()[0]
            conn.close()
        except:
            card_count = 0
        
        # Check environment variables
        telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        telegram_chat = os.getenv('TELEGRAM_CHAT_ID')
        
        env_check = "✅ OK" if telegram_token and telegram_chat else "❌ Missing tokens"
        
        return jsonify({
            'running': is_running,
            'card_count': card_count,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC'),
            'env_check': env_check,
            'has_token': bool(telegram_token),
            'has_chat_id': bool(telegram_chat)
        })
    except Exception as e:
        return jsonify({
            'running': False,
            'card_count': 0,
            'last_update': 'Error: ' + str(e),
            'env_check': '❌ Error',
            'has_token': False,
            'has_chat_id': False
        })

@app.route('/health')
def health():
    """Health check for uptime monitoring"""
    return "OK", 200

@app.route('/logs')  
def logs():
    """Simple logs viewer"""
    return f"""
    <h1>Recent Activity</h1>
    <p>Monitor Running: {'🟢 Yes' if is_running else '🔴 No'}</p>
    <p>Check the Render logs for detailed information.</p>
    <a href="/">← Back to Dashboard</a>
    """

def keep_alive():
    """Ping self to prevent Render from sleeping"""
    while True:
        try:
            import requests
            hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')
            if hostname != 'localhost':
                requests.get(f"https://{hostname}/health", timeout=10)
                print("🏓 Keep-alive ping sent")
        except Exception as e:
            print(f"Keep-alive error: {e}")
        time.sleep(600)  # Ping every 10 minutes

if __name__ == '__main__':
    print("🚀 Starting Flask app with background monitor...")
    
    # Start monitor in background thread
    print("🔄 Starting monitor thread...")
    monitor_thread = threading.Thread(target=start_monitor, daemon=True)
    monitor_thread.start()
    
    # Start keep-alive thread
    print("🔄 Starting keep-alive thread...")
    keepalive_thread = threading.Thread(target=keep_alive, daemon=True)
    keepalive_thread.start()
    
    # Start Flask web interface
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Starting web server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)