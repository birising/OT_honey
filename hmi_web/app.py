#!/usr/bin/env python3
"""
HMI Web Interface - SCADA-like web interface
"""

import os
import json
import logging
import warnings
from datetime import datetime
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests

warnings.filterwarnings('ignore', category=UserWarning, module='flask_limiter')

logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'change-me-in-production-wwtp-hmi-key')

SIMULATOR_URL = os.getenv('SIMULATOR_URL', 'http://simulator:8080')

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per hour", "50 per minute"],
    storage_uri="memory://"
)

# Users
USERS = {
    'operator': {'password': 'operator123', 'role': 'operator'},
    'maintenance': {'password': 'maint123', 'role': 'maintenance'},
    'engineering': {'password': 'eng123', 'role': 'engineering'},
}

# Whitelist for write operations
WRITE_WHITELIST = {
    'WWTP01:INFLUENT:PMP101.CMD',
    'WWTP01:INFLUENT:PMP101.AUTO',
    'WWTP01:AERATION:BLW201.CMD',
    'WWTP01:AERATION:BLW201.AUTO',
    'WWTP01:AERATION:BLW201.SP',
    'WWTP01:AERATION:DO301.SP',
    'WWTP01:AERATION:DO301.CTRL_EN',
    'WWTP01:AERATION:DO301.CTRL_MODE',
    'WWTP01:CLARIFIER:PMP401.CMD',
    'WWTP01:CLARIFIER:PMP401.AUTO',
    'WWTP01:CLARIFIER:PMP402.CMD',
    'WWTP01:CLARIFIER:PMP402.AUTO',
    'WWTP01:SCREENING:SCR101.CMD',
    'WWTP01:SCREENING:SCR101.AUTO',
    'WWTP01:PRIMARY:PMP301.CMD',
    'WWTP01:PRIMARY:PMP301.AUTO',
    'WWTP01:CHEMICAL:PMP501.CMD',
    'WWTP01:CHEMICAL:PMP501.AUTO',
    'WWTP01:CHEMICAL:DOSE_FECL3.SP',
    'WWTP01:INFLUENT:VLV101.CMD',
    'WWTP01:CHEMICAL:VLV501.CMD',
    'WWTP01:SYSTEM:GLOBAL_MODE.PV',
    'WWTP01:SYSTEM:KILL_SWITCH.PV',
}

def log_hmi_operation(operation, src_ip, action, result, details=None):
    """Log HMI operation"""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'src_ip': src_ip,
        'operation': operation,
        'action': action,
        'result': result,
        'user': session.get('username', 'anonymous'),
        'details': details or {}
    }

    log_dir = "/tmp/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{log_dir}/hmi_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
    try:
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.error(f"Failed to write log: {e}")

def get_snapshot():
    """Get snapshot from simulator"""
    try:
        response = requests.get(f"{SIMULATOR_URL}/api/snapshot", timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.error(f"Failed to get snapshot: {e}")
    return {}

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        src_ip = get_remote_address()

        if username in USERS and USERS[username]['password'] == password:
            session['username'] = username
            session['role'] = USERS[username]['role']
            log_hmi_operation('hmi', src_ip, 'login', 'success', {'username': username})
            return redirect(url_for('overview'))
        else:
            log_hmi_operation('hmi', src_ip, 'login', 'failed', {'username': username})
            return render_template('login.html', error='Invalid credentials')

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    src_ip = get_remote_address()
    username = session.get('username', 'unknown')
    session.clear()
    log_hmi_operation('hmi', src_ip, 'logout', 'success', {'username': username})
    return redirect(url_for('login'))

@app.route('/')
def index():
    """Redirect to overview"""
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('overview'))

@app.route('/overview')
def overview():
    """Process overview"""
    if 'username' not in session:
        return redirect(url_for('login'))

    snapshot = get_snapshot()

    key_tags = {
        # System
        'GLOBAL_MODE': snapshot.get('WWTP01:SYSTEM:GLOBAL_MODE.PV', {}).get('value', 0),
        'KILL_SWITCH': snapshot.get('WWTP01:SYSTEM:KILL_SWITCH.PV', {}).get('value', 0),
        # Influent
        'Q_IN': snapshot.get('WWTP01:INFLUENT:Q_IN.PV', {}).get('value', 0),
        'LT101': snapshot.get('WWTP01:INFLUENT:LT101.PV', {}).get('value', 0),
        'PMP101_FB': snapshot.get('WWTP01:INFLUENT:PMP101.FB', {}).get('value', 0),
        'PMP101_AUTO': snapshot.get('WWTP01:INFLUENT:PMP101.AUTO', {}).get('value', 0),
        'PMP101_FAULT': snapshot.get('WWTP01:INFLUENT:PMP101.FAULT', {}).get('value', 0),
        'PMP101_RUNTIME': snapshot.get('WWTP01:INFLUENT:PMP101.RUNTIME', {}).get('value', 0),
        'VLV101_POS': snapshot.get('WWTP01:INFLUENT:VLV101.POS', {}).get('value', 0),
        # Screening
        'SCR101_DP': snapshot.get('WWTP01:SCREENING:SCR101.DP', {}).get('value', 0),
        'SCR101_FB': snapshot.get('WWTP01:SCREENING:SCR101.FB', {}).get('value', 0),
        'SCR101_FAULT': snapshot.get('WWTP01:SCREENING:SCR101.FAULT', {}).get('value', 0),
        'SCR101_AUTO': snapshot.get('WWTP01:SCREENING:SCR101.AUTO', {}).get('value', 0),
        # Grit
        'GRT201_LEVEL': snapshot.get('WWTP01:GRIT:GRT201.LEVEL', {}).get('value', 0),
        'GRS201_SKIM': snapshot.get('WWTP01:GRIT:GRS201.SKIM', {}).get('value', 0),
        # Primary
        'LT301': snapshot.get('WWTP01:PRIMARY:LT301.PV', {}).get('value', 0),
        'PMP301_FB': snapshot.get('WWTP01:PRIMARY:PMP301.FB', {}).get('value', 0),
        'PMP301_AUTO': snapshot.get('WWTP01:PRIMARY:PMP301.AUTO', {}).get('value', 0),
        'PMP301_FAULT': snapshot.get('WWTP01:PRIMARY:PMP301.FAULT', {}).get('value', 0),
        'PMP301_RUNTIME': snapshot.get('WWTP01:PRIMARY:PMP301.RUNTIME', {}).get('value', 0),
        'COD_PRI': snapshot.get('WWTP01:PRIMARY:COD_PRI.PV', {}).get('value', 0),
        # Aeration
        'LT201': snapshot.get('WWTP01:AERATION:LT201.PV', {}).get('value', 0),
        'DO301': snapshot.get('WWTP01:AERATION:DO301.PV', {}).get('value', 0),
        'DO301_SP': snapshot.get('WWTP01:AERATION:DO301.SP', {}).get('value', 0),
        'pH302': snapshot.get('WWTP01:AERATION:pH302.PV', {}).get('value', 0),
        'TEMP303': snapshot.get('WWTP01:AERATION:TEMP303.PV', {}).get('value', 0),
        'BLW201_FB': snapshot.get('WWTP01:AERATION:BLW201.FB', {}).get('value', 0),
        'BLW201_FAULT': snapshot.get('WWTP01:AERATION:BLW201.FAULT', {}).get('value', 0),
        'BLW201_SP': snapshot.get('WWTP01:AERATION:BLW201.SP', {}).get('value', 0),
        'BLW201_PV': snapshot.get('WWTP01:AERATION:BLW201.PV', {}).get('value', 0),
        'BLW201_CURRENT': snapshot.get('WWTP01:AERATION:BLW201.CURRENT', {}).get('value', 0),
        'BLW201_RUNTIME': snapshot.get('WWTP01:AERATION:BLW201.RUNTIME', {}).get('value', 0),
        # Clarifier
        'LT401': snapshot.get('WWTP01:CLARIFIER:LT401.PV', {}).get('value', 0),
        'TUR501': snapshot.get('WWTP01:CLARIFIER:TUR501.PV', {}).get('value', 0),
        'PMP401_FB': snapshot.get('WWTP01:CLARIFIER:PMP401.FB', {}).get('value', 0),
        'PMP402_FB': snapshot.get('WWTP01:CLARIFIER:PMP402.FB', {}).get('value', 0),
        # Chemical
        'DOSE_FECL3': snapshot.get('WWTP01:CHEMICAL:DOSE_FECL3.PV', {}).get('value', 0),
        'DOSE_FECL3_SP': snapshot.get('WWTP01:CHEMICAL:DOSE_FECL3.SP', {}).get('value', 0),
        'PMP501_FB': snapshot.get('WWTP01:CHEMICAL:PMP501.FB', {}).get('value', 0),
        'TANK501_LEVEL': snapshot.get('WWTP01:CHEMICAL:TANK501.LEVEL', {}).get('value', 0),
        'VLV501_POS': snapshot.get('WWTP01:CHEMICAL:VLV501.POS', {}).get('value', 0),
        # Effluent
        'Q_OUT': snapshot.get('WWTP01:EFFLUENT:Q_OUT.PV', {}).get('value', 0),
        'pH501': snapshot.get('WWTP01:EFFLUENT:pH501.PV', {}).get('value', 0),
        'COD501': snapshot.get('WWTP01:EFFLUENT:COD501.PV', {}).get('value', 0),
    }

    # Map mode number to string
    mode_map = {0: 'AUTO', 1: 'MANUAL', 2: 'MAINTENANCE'}
    key_tags['GLOBAL_MODE_STR'] = mode_map.get(int(key_tags['GLOBAL_MODE']), 'AUTO')

    return render_template('overview.html', tags=key_tags, username=session.get('username'))

@app.route('/alarms')
def alarms_page():
    """Alarms page"""
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('alarms.html', username=session.get('username'))

@app.route('/trends')
def trends():
    """Trends page"""
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('trends.html', username=session.get('username'))

@app.route('/maintenance')
def maintenance():
    """Maintenance screen"""
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('maintenance.html', username=session.get('username'))

@app.route('/api/write', methods=['POST'])
@limiter.limit("10 per minute")
def api_write():
    """Write tag via API"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    src_ip = get_remote_address()
    data = request.get_json()

    if not data or 'tag' not in data or 'value' not in data:
        log_hmi_operation('hmi', src_ip, 'write', 'error', {'reason': 'invalid_request'})
        return jsonify({'error': 'Invalid request'}), 400

    tag = data['tag']
    value = data['value']

    if tag not in WRITE_WHITELIST:
        log_hmi_operation('hmi', src_ip, 'write', 'denied', {'tag': tag})
        return jsonify({'error': 'Tag not in whitelist'}), 403

    try:
        response = requests.post(
            f"{SIMULATOR_URL}/api/write",
            json={'tag': tag, 'value': value},
            timeout=2
        )
        if response.status_code == 200:
            log_hmi_operation('hmi', src_ip, 'write', 'success', {'tag': tag, 'value': value})
            return jsonify({'success': True})
        else:
            log_hmi_operation('hmi', src_ip, 'write', 'error', {'tag': tag, 'status': response.status_code})
            return jsonify({'error': 'Write failed'}), 500
    except Exception as e:
        log_hmi_operation('hmi', src_ip, 'write', 'error', {'tag': tag, 'error': str(e)})
        return jsonify({'error': str(e)}), 500

@app.route('/api/trends')
def api_trends():
    """Proxy trends from simulator"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    time_range = request.args.get('range', '1h')
    try:
        response = requests.get(
            f"{SIMULATOR_URL}/api/trends",
            params={'range': time_range},
            timeout=5
        )
        if response.status_code == 200:
            return jsonify(response.json())
    except Exception as e:
        logger.error(f"Failed to get trends: {e}")
    return jsonify({'data': [], 'points': 0, 'range': time_range, 'tags': []})

@app.route('/api/snapshot')
def api_snapshot():
    """Proxy snapshot from simulator for AJAX updates"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    return jsonify(get_snapshot())

@app.route('/api/alarms/list')
def api_alarms_list():
    """Proxy alarms list from simulator for AJAX updates"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    try:
        response = requests.get(f"{SIMULATOR_URL}/api/alarms", timeout=2)
        if response.status_code == 200:
            return jsonify(response.json())
    except Exception as e:
        logger.error(f"Failed to get alarms: {e}")
    return jsonify([])

@app.route('/api/alarm/acknowledge', methods=['POST'])
@limiter.limit("10 per minute")
def api_alarm_ack():
    """Acknowledge alarm via simulator"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    src_ip = get_remote_address()
    data = request.get_json()

    if not data or 'id' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    try:
        response = requests.post(
            f"{SIMULATOR_URL}/api/alarm/acknowledge",
            json=data,
            timeout=2
        )
        log_hmi_operation('hmi', src_ip, 'alarm_ack', 'success', {'alarm_id': data['id']})
        return jsonify(response.json()), response.status_code
    except Exception as e:
        log_hmi_operation('hmi', src_ip, 'alarm_ack', 'error', {'error': str(e)})
        return jsonify({'error': str(e)}), 500

@app.route('/api/mode', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def api_mode():
    """Proxy mode endpoint"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    src_ip = get_remote_address()

    if request.method == 'GET':
        try:
            response = requests.get(f"{SIMULATOR_URL}/api/mode", timeout=2)
            return jsonify(response.json()), response.status_code
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    data = request.get_json()
    try:
        response = requests.post(
            f"{SIMULATOR_URL}/api/mode",
            json=data,
            timeout=2
        )
        log_hmi_operation('hmi', src_ip, 'mode_set', 'success', data)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        log_hmi_operation('hmi', src_ip, 'mode_set', 'error', {'error': str(e)})
        return jsonify({'error': str(e)}), 500

@app.route('/api/killswitch', methods=['POST'])
@limiter.limit("5 per minute")
def api_killswitch():
    """Proxy killswitch endpoint"""
    if 'username' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    src_ip = get_remote_address()
    data = request.get_json()

    try:
        response = requests.post(
            f"{SIMULATOR_URL}/api/killswitch",
            json=data,
            timeout=2
        )
        log_hmi_operation('hmi', src_ip, 'killswitch', 'success', data)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        log_hmi_operation('hmi', src_ip, 'killswitch', 'error', {'error': str(e)})
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    warnings.filterwarnings('ignore', message='.*development server.*')
    app.run(host='0.0.0.0', port=80, debug=False)
