#!/usr/bin/env python3
"""
Record Mode - Record trace for replay
"""

import json
import time
import requests
import sys
from datetime import datetime

SIMULATOR_URL = 'http://localhost:8080'
RECORD_DURATION = 1800  # 30 minutes

def record_trace(output_file):
    """Record trace"""
    print(f"Recording trace to {output_file}...")
    print(f"Duration: {RECORD_DURATION} seconds (30 minutes)")
    print("Press Ctrl+C to stop early")
    
    trace = []
    start_time = time.time()
    
    try:
        while time.time() - start_time < RECORD_DURATION:
            # Get snapshot
            snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
            
            # Record entry
            entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'operation': 'snapshot',
                'data': snapshot
            }
            trace.append(entry)
            
            time.sleep(1.0)  # 1 second intervals
            
            if len(trace) % 60 == 0:
                print(f"Recorded {len(trace)} entries...")
    
    except KeyboardInterrupt:
        print("\nRecording stopped by user")
    
    # Save trace
    print(f"Saving {len(trace)} entries to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(trace, f, indent=2)
    
    print("Trace saved!")

if __name__ == '__main__':
    output_file = sys.argv[1] if len(sys.argv) > 1 else 'trace.json'
    record_trace(output_file)


