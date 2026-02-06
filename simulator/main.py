#!/usr/bin/env python3
"""
WWTP Simulator - Core Process Simulator
Simulates a small wastewater treatment plant (2-8k EO)
"""

import os
import json
import time
import uuid
import logging
from collections import deque
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Deterministic mode
DETERMINISTIC = os.getenv('DETERMINISTIC', 'true').lower() == 'true'
RANDOM_SEED = int(os.getenv('RANDOM_SEED', '42'))
if DETERMINISTIC:
    np.random.seed(RANDOM_SEED)
    logger.info(f"Deterministic mode enabled with seed {RANDOM_SEED}")

# Import simulator modules
from process_model import ProcessModel
from tag_generator import TagGenerator
from alarm_engine import AlarmEngine
from scenario_manager import ScenarioManager

# Initialize components
tag_gen = TagGenerator(deterministic=DETERMINISTIC, seed=RANDOM_SEED)
process = ProcessModel(tag_gen, deterministic=DETERMINISTIC, seed=RANDOM_SEED)
alarms = AlarmEngine(tag_gen, deterministic=DETERMINISTIC, seed=RANDOM_SEED)
scenarios = ScenarioManager(process, alarms, deterministic=DETERMINISTIC, seed=RANDOM_SEED)

# Trend history buffer (24h at 1s intervals)
TREND_BUFFER_SIZE = 86400
trend_history = deque(maxlen=TREND_BUFFER_SIZE)

# Tags to record for trends
TREND_TAGS = [
    'WWTP01:INFLUENT:Q_IN.PV',
    'WWTP01:INFLUENT:LT101.PV',
    'WWTP01:AERATION:DO301.PV',
    'WWTP01:AERATION:DO301.SP',
    'WWTP01:AERATION:pH302.PV',
    'WWTP01:AERATION:TEMP303.PV',
    'WWTP01:AERATION:BLW201.PV',
    'WWTP01:CLARIFIER:LT401.PV',
    'WWTP01:CLARIFIER:TUR501.PV',
    'WWTP01:EFFLUENT:Q_OUT.PV',
    'WWTP01:EFFLUENT:COD501.PV',
    'WWTP01:EFFLUENT:pH501.PV',
    'WWTP01:SCREENING:SCR101.DP',
    'WWTP01:CHEMICAL:DOSE_FECL3.PV',
    'WWTP01:CHEMICAL:TANK501.LEVEL',
]

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

def log_operation(operation, src_ip, action, result, details=None):
    """Log structured JSON operation with correlation ID"""
    correlation_id = uuid.uuid4().hex[:8]
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'correlation_id': correlation_id,
        'src_ip': src_ip,
        'operation': operation,
        'action': action,
        'result': result,
        'details': details or {}
    }

    log_dir = "/tmp/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = f"{log_dir}/{operation}_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
    try:
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.error(f"Failed to write log: {e}")

@app.route('/api/snapshot', methods=['GET'])
def get_snapshot():
    """Get current process snapshot"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    snapshot = process.get_snapshot()
    log_operation('api', src_ip, 'snapshot', 'success', {'tags_count': len(snapshot)})
    return jsonify(snapshot)

@app.route('/api/alarms', methods=['GET'])
def get_alarms():
    """Get current alarms"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    alarm_list = alarms.get_active_alarms()
    log_operation('api', src_ip, 'alarms', 'success', {'alarms_count': len(alarm_list)})
    return jsonify(alarm_list)

@app.route('/api/alarm/acknowledge', methods=['POST'])
def acknowledge_alarm():
    """Acknowledge an alarm by ID"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    data = request.get_json()

    if not data or 'id' not in data:
        log_operation('api', src_ip, 'alarm_ack', 'error', {'reason': 'invalid_request'})
        return jsonify({'error': 'Invalid request - missing id'}), 400

    alarm_id = data['id']
    success = alarms.acknowledge_alarm(alarm_id)

    if success:
        log_operation('api', src_ip, 'alarm_ack', 'success', {'alarm_id': alarm_id})
        return jsonify({'success': True, 'alarm_id': alarm_id})
    else:
        log_operation('api', src_ip, 'alarm_ack', 'error', {'alarm_id': alarm_id, 'reason': 'not_found'})
        return jsonify({'error': 'Alarm not found or not active'}), 404

@app.route('/api/write', methods=['POST'])
def write_tag():
    """Write to tag (whitelist only)"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    data = request.get_json()

    if not data or 'tag' not in data or 'value' not in data:
        log_operation('api', src_ip, 'write', 'error', {'reason': 'invalid_request'})
        return jsonify({'error': 'Invalid request'}), 400

    tag = data['tag']
    value = data['value']

    if tag not in WRITE_WHITELIST:
        log_operation('api', src_ip, 'write', 'denied', {'tag': tag, 'value': value})
        return jsonify({'error': 'Tag not in whitelist'}), 403

    try:
        result = process.write_tag(tag, value)
        log_operation('api', src_ip, 'write', 'success', {'tag': tag, 'value': value})
        return jsonify({'success': True, 'tag': tag, 'value': result})
    except Exception as e:
        log_operation('api', src_ip, 'write', 'error', {'tag': tag, 'error': str(e)})
        return jsonify({'error': str(e)}), 500

@app.route('/api/trends', methods=['GET'])
def get_trends():
    """Get trend data"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    time_range = request.args.get('range', '1h')

    # Calculate number of points based on range
    range_map = {
        '1h': 3600,
        '8h': 28800,
        '24h': 86400,
    }
    max_points = range_map.get(time_range, 3600)

    # Get data from buffer
    data_points = list(trend_history)
    if len(data_points) > max_points:
        data_points = data_points[-max_points:]

    # Downsample if too many points (max 360 points for display)
    target_points = 360
    if len(data_points) > target_points:
        step = len(data_points) // target_points
        data_points = data_points[::step]

    log_operation('api', src_ip, 'trends', 'success', {
        'range': time_range,
        'points': len(data_points)
    })
    return jsonify({
        'range': time_range,
        'points': len(data_points),
        'data': data_points,
        'tags': TREND_TAGS,
    })

@app.route('/api/mode', methods=['GET', 'POST'])
def operating_mode():
    """Get or set global operating mode"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

    if request.method == 'GET':
        mode = process.state['GLOBAL_MODE']
        log_operation('api', src_ip, 'mode_get', 'success', {'mode': mode})
        return jsonify({'mode': mode})

    data = request.get_json()
    if not data or 'mode' not in data:
        return jsonify({'error': 'Invalid request - missing mode'}), 400

    mode = data['mode'].upper()
    if mode not in ('AUTO', 'MANUAL', 'MAINTENANCE'):
        return jsonify({'error': 'Invalid mode - must be AUTO, MANUAL, or MAINTENANCE'}), 400

    process.set_mode(mode)
    log_operation('api', src_ip, 'mode_set', 'success', {'mode': mode})
    return jsonify({'success': True, 'mode': mode})

@app.route('/api/killswitch', methods=['POST'])
def kill_switch():
    """Activate or deactivate emergency stop"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    data = request.get_json()

    if not data or 'activate' not in data:
        return jsonify({'error': 'Invalid request - missing activate'}), 400

    activate = bool(data['activate'])
    process.set_kill_switch(activate)

    log_operation('api', src_ip, 'killswitch', 'success', {'activate': activate})
    return jsonify({'success': True, 'kill_switch': activate})

@app.route('/api/scenario/start', methods=['POST'])
def start_scenario():
    """Start a scenario"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    data = request.get_json()

    if not data or 'name' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    scenario_name = data['name']
    try:
        scenarios.start_scenario(scenario_name)
        log_operation('api', src_ip, 'scenario_start', 'success', {'scenario': scenario_name})
        return jsonify({'success': True, 'scenario': scenario_name})
    except Exception as e:
        log_operation('api', src_ip, 'scenario_start', 'error', {'scenario': scenario_name, 'error': str(e)})
        return jsonify({'error': str(e)}), 500

@app.route('/api/scenario/stop', methods=['POST'])
def stop_scenario():
    """Stop a scenario"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    data = request.get_json()

    if not data or 'name' not in data:
        return jsonify({'error': 'Invalid request'}), 400

    scenario_name = data['name']
    try:
        scenarios.stop_scenario(scenario_name)
        log_operation('api', src_ip, 'scenario_stop', 'success', {'scenario': scenario_name})
        return jsonify({'success': True, 'scenario': scenario_name})
    except Exception as e:
        log_operation('api', src_ip, 'scenario_stop', 'error', {'scenario': scenario_name, 'error': str(e)})
        return jsonify({'error': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    """Reset to default state"""
    src_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    try:
        process.reset()
        alarms.reset()
        scenarios.reset_all()
        trend_history.clear()
        log_operation('api', src_ip, 'reset', 'success', {})
        return jsonify({'success': True})
    except Exception as e:
        log_operation('api', src_ip, 'reset', 'error', {'error': str(e)})
        return jsonify({'error': str(e)}), 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint - API information"""
    return jsonify({
        'service': 'WWTP Control System API',
        'facility': 'WWTP Nove Mesto nad Metuji (NMM-CZ-01)',
        'operator': 'Vodohospodarska spolecnost Vychodni Cechy, a.s.',
        'capacity': '4.5k EO',
        'version': '3.0.0',
        'endpoints': {
            'health': '/health',
            'snapshot': '/api/snapshot',
            'alarms': '/api/alarms',
            'alarm_acknowledge': '/api/alarm/acknowledge (POST)',
            'trends': '/api/trends?range=1h|8h|24h',
            'write': '/api/write (POST)',
            'mode': '/api/mode (GET/POST)',
            'killswitch': '/api/killswitch (POST)',
            'scenario_start': '/api/scenario/start (POST)',
            'scenario_stop': '/api/scenario/stop (POST)',
            'reset': '/api/reset (POST)'
        }
    })

@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'mode': process.state['GLOBAL_MODE'],
        'kill_switch': process.state['KILL_SWITCH'],
        'active_alarms': len(alarms.active_alarms),
        'trend_points': len(trend_history),
    })

def record_trends():
    """Record current values to trend buffer"""
    snapshot = process.get_snapshot()
    record = {'timestamp': time.time()}
    for tag in TREND_TAGS:
        if tag in snapshot:
            record[tag] = snapshot[tag]['value']
    trend_history.append(record)

def update_loop():
    """Background update loop"""
    while True:
        try:
            process.update(1.0)
            alarms.update(process.get_snapshot())
            scenarios.update()
            record_trends()
            time.sleep(1.0)
        except Exception as e:
            logger.error(f"Update loop error: {e}")
            time.sleep(1.0)

if __name__ == '__main__':
    import threading
    update_thread = threading.Thread(target=update_loop, daemon=True)
    update_thread.start()

    app.run(host='0.0.0.0', port=8080, debug=False)
