import os
import json
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Assuming the app is run from the root of the project or inside dashboard/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEMETRY_FILE = os.path.join(BASE_DIR, "mission_telemetry.jsonl")
JAMMER_TELEMETRY_FILE = os.path.join(BASE_DIR, "jammer_telemetry.jsonl")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/telemetry')
def get_telemetry():
    data = []
    if os.path.exists(TELEMETRY_FILE):
        try:
            with open(TELEMETRY_FILE, 'r') as f:
                lines = f.readlines()
                for line in lines[-500:]:
                    try:
                        event = json.loads(line.strip())
                        event['source'] = 'blue_team'
                        data.append(event)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading telemetry: {e}")
            
    if os.path.exists(JAMMER_TELEMETRY_FILE):
        try:
            with open(JAMMER_TELEMETRY_FILE, 'r') as f:
                lines = f.readlines()
                for line in lines[-500:]:
                    try:
                        event = json.loads(line.strip())
                        event['source'] = 'red_team'
                        data.append(event)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading jammer telemetry: {e}")
            
    # Sort combined telemetry by timestamp
    data.sort(key=lambda x: x.get('timestamp', 0))
    return jsonify(data)

@app.route('/api/clear', methods=['POST'])
def clear_telemetry():
    try:
        if os.path.exists(TELEMETRY_FILE):
            os.remove(TELEMETRY_FILE)
        if os.path.exists(JAMMER_TELEMETRY_FILE):
            os.remove(JAMMER_TELEMETRY_FILE)
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    print("=======================================================")
    print(" OPAL VANGUARD - COMMANDER DASHBOARD ONLINE")
    print("=======================================================")
    print(" Access the dashboard at: http://localhost:5000")
    print("=======================================================")
    app.run(host='0.0.0.0', port=5000, debug=False)
