import os
import json
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Assuming the app is run from the root of the project or inside dashboard/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEMETRY_FILE = os.path.join(BASE_DIR, "mission_telemetry.jsonl")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/telemetry')
def get_telemetry():
    data = []
    if os.path.exists(TELEMETRY_FILE):
        try:
            with open(TELEMETRY_FILE, 'r') as f:
                # Read the last 500 lines to keep the payload manageable
                lines = f.readlines()
                for line in lines[-500:]:
                    try:
                        event = json.loads(line.strip())
                        data.append(event)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error reading telemetry: {e}")
    return jsonify(data)

if __name__ == '__main__':
    print("=======================================================")
    print(" OPAL VANGUARD - COMMANDER DASHBOARD ONLINE")
    print("=======================================================")
    print(" Access the dashboard at: http://localhost:5000")
    print("=======================================================")
    app.run(host='0.0.0.0', port=5000, debug=False)
