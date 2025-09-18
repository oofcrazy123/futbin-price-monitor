# app.py (Web interface + background worker)
from flask import Flask, render_template, jsonify
import threading
import time
import os
from datetime import datetime
import sqlite3
from futbin_monitor import FutbinPriceMonitor

app = Flask(__name__)

# Global monitor instance
monitor = None
monitor_thread = None
is_running = False

@app.route('/')
def home():
    """Simple web interface to check status"""
    return '''
    <html>
    <head><title>Futbin Price Monitor</title></head>
    <body style="font-family: Arial; max-width: 800px; margin: 50px auto; padding: 20px;">
        <h1>🤖 Futbin Price Gap Monitor</h1>
        <p>Your bot is running in the background!</p>
        
        <div style="background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 8px;">
            <h3>📊 Status</h3>
            <p id="status">Loading...</p>
            <button onclick="checkStatus()" style="padding: 10px 20px; background: #007cba; color: white; border: none; border-radius: 4px; cursor: pointer;">
                Refresh Status
            </button>
        </div>
        
        <div style="background: #e8f4f8; padding: 20px; margin: 20px 0; border-radius: 8px;">
            <h3>🔧 Configuration</h3>
            <p><strong>Price Gap Threshold:</strong> 1,000+ coins & 5%+</p>
            <p><strong>Minimum Card Value:</strong> 5,000 coins</p>
            <p><strong>Check Interval:</strong> Every 45 minutes</p>
        </div>
        
        <div style="background: #f0f8e8; padding: 20px; margin: 20px 0; border-radius: 8px;">
            <h3>📱 Alerts</h3>
            <p>Trading opportunities are sent to your Telegram!</p>
            <p>Recent alerts will appear in your Telegram chat.</p>
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
                    });
            }
            
            // Auto-refresh every 30 seconds
            setInterval(checkStatus, 30000);
            checkStatus(); // Initial load
        </script>
    </body>
    </html>
    '''

@app.route('/status')
def status():
    """API endpoint to check bot status"""
    try:
        conn = sqlite3.connect('futbin_cards.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM cards')
        card_count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'running': is_running,
            'card_count': card_count,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        })
    except Exception as e:
        return jsonify({
            'running': False,
            'card_count': 0,
            'last_update': 'Error: ' + str(e)
        })

@app.route('/health')
def health():
    """Health check for uptime monitoring"""
    return "OK", 200

def start_monitor():
    """Start the price monitor in background"""
    global monitor, is_running
    try:
        monitor = FutbinPriceMonitor()
        is_running = True
        monitor.run_complete_system()
    except Exception as e:
        print(f"Monitor error: {e}")
        is_running = False

def keep_alive():
    """Ping self to prevent Render from sleeping"""
    while True:
        try:
            import requests
            requests.get(f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME', 'localhost')}/health")
        except:
            pass
        time.sleep(600)  # Ping every 10 minutes

if __name__ == '__main__':
    # Start monitor in background thread
    monitor_thread = threading.Thread(target=start_monitor, daemon=True)
    monitor_thread.start()
    
    # Start keep-alive thread
    keepalive_thread = threading.Thread(target=keep_alive, daemon=True)
    keepalive_thread.start()
    
    # Start Flask web interface
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)