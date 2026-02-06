#!/usr/bin/env python3
"""
Replay Mode - Replay saved trace
"""

import json
import time
import requests
import sys
from datetime import datetime

SIMULATOR_URL = 'http://localhost:8080'

def replay_trace(trace_file):
    """Replay a saved trace"""
    print(f"Loading trace from {trace_file}...")
    
    with open(trace_file, 'r') as f:
        trace_data = json.load(f)
    
    print(f"Trace contains {len(trace_data)} entries")
    print(f"Time range: {trace_data[0]['timestamp']} to {trace_data[-1]['timestamp']}")
    
    # Reset simulator
    print("Resetting simulator...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(2)
    
    # Replay
    print("Replaying trace...")
    start_time = time.time()
    trace_start = datetime.fromisoformat(trace_data[0]['timestamp']).timestamp()
    
    for entry in trace_data:
        # Calculate delay
        entry_time = datetime.fromisoformat(entry['timestamp']).timestamp()
        delay = entry_time - trace_start
        
        # Wait until it's time
        elapsed = time.time() - start_time
        if delay > elapsed:
            time.sleep(delay - elapsed)
        
        # Replay action
        if entry['operation'] == 'write':
            tag = entry['details']['tag']
            value = entry['details']['value']
            print(f"[{entry['timestamp']}] Write {tag} = {value}")
            requests.post(
                f"{SIMULATOR_URL}/api/write",
                json={'tag': tag, 'value': value}
            )
        elif entry['operation'] == 'scenario_start':
            scenario = entry['details']['scenario']
            print(f"[{entry['timestamp']}] Start scenario: {scenario}")
            requests.post(
                f"{SIMULATOR_URL}/api/scenario/start",
                json={'name': scenario}
            )
    
    print("Replay complete!")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python replay_trace.py <trace_file.json>")
        sys.exit(1)
    
    replay_trace(sys.argv[1])


