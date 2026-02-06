#!/usr/bin/env python3
"""
Test: VFD Fault Scenario
Tests VFD fault on blower and alarm
"""

import time
import requests
import sys

SIMULATOR_URL = 'http://localhost:8080'

def test_vfd_fault_scenario():
    """Test VFD fault scenario"""
    print("=== Test: VFD Fault Scenario ===")
    
    # Reset
    print("1. Resetting system...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(2)
    
    # Get initial state
    print("2. Getting initial state...")
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    initial_blw_fb = snapshot.get('WWTP01:AERATION:BLW201.FB', {}).get('value', 0)
    initial_blw_fault = snapshot.get('WWTP01:AERATION:BLW201.FAULT', {}).get('value', 0)
    print(f"   Initial BLW201_FB: {initial_blw_fb}")
    print(f"   Initial BLW201_FAULT: {initial_blw_fault}")
    
    assert initial_blw_fault == 0, "Blower should not be in fault initially"
    
    # Start VFD fault scenario
    print("3. Starting VFD fault scenario...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/scenario/start",
        json={'name': 'vfd_fault'}
    )
    assert response.status_code == 200, "Failed to start scenario"
    
    # Wait for effects
    print("4. Waiting for fault effects...")
    time.sleep(5)
    
    # Check fault state
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    fault_blw_fb = snapshot.get('WWTP01:AERATION:BLW201.FB', {}).get('value', 0)
    fault_blw_fault = snapshot.get('WWTP01:AERATION:BLW201.FAULT', {}).get('value', 0)
    fault_blw_cmd = snapshot.get('WWTP01:AERATION:BLW201.CMD', {}).get('value', 0)
    
    print(f"   Fault BLW201_FB: {fault_blw_fb}")
    print(f"   Fault BLW201_FAULT: {fault_blw_fault}")
    print(f"   Fault BLW201_CMD: {fault_blw_cmd}")
    
    assert fault_blw_fault == 1, f"Blower should be in fault: {fault_blw_fault} != 1"
    assert fault_blw_fb == 0, f"Blower feedback should be 0: {fault_blw_fb} != 0"
    assert fault_blw_cmd == 0, f"Blower command should be 0: {fault_blw_cmd} != 0"
    
    # Check alarms
    print("5. Checking alarms...")
    alarms = requests.get(f"{SIMULATOR_URL}/api/alarms").json()
    vfd_alarm = [a for a in alarms if 'VFD' in a.get('text', '')]
    
    if vfd_alarm:
        print(f"   ✓ VFD alarm triggered: {vfd_alarm[0]['text']}")
    else:
        print("   ⚠ VFD alarm not found (should be immediate)")
    
    # Check DO decrease
    time.sleep(10)
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    do_value = snapshot.get('WWTP01:AERATION:DO301.PV', {}).get('value', 0)
    print(f"   DO after fault: {do_value:.2f} mg/L")
    assert do_value < 2.5, "DO should decrease without blower"
    
    # Stop scenario
    print("6. Stopping VFD fault scenario...")
    requests.post(
        f"{SIMULATOR_URL}/api/scenario/stop",
        json={'name': 'vfd_fault'}
    )
    time.sleep(5)
    
    # Verify return to normal
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    final_blw_fault = snapshot.get('WWTP01:AERATION:BLW201.FAULT', {}).get('value', 0)
    print(f"   Final BLW201_FAULT: {final_blw_fault}")
    assert final_blw_fault == 0, "Blower fault should be cleared"
    
    print("✓ Test passed!")
    return True

if __name__ == '__main__':
    try:
        test_vfd_fault_scenario()
        sys.exit(0)
    except AssertionError as e:
        print(f"✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Test error: {e}")
        sys.exit(1)


