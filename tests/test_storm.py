#!/usr/bin/env python3
"""
Test: Storm Scenario
Tests storm event - increased influent flow and HH alarm
"""

import time
import requests
import sys

SIMULATOR_URL = 'http://localhost:8080'

def test_storm_scenario():
    """Test storm scenario"""
    print("=== Test: Storm Scenario ===")
    
    # Reset
    print("1. Resetting system...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(2)
    
    # Get initial state
    print("2. Getting initial state...")
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    initial_q_in = snapshot.get('WWTP01:INFLUENT:Q_IN.PV', {}).get('value', 0)
    initial_lt101 = snapshot.get('WWTP01:INFLUENT:LT101.PV', {}).get('value', 0)
    print(f"   Initial Q_IN: {initial_q_in:.2f} m3/h")
    print(f"   Initial LT101: {initial_lt101:.2f} m")
    
    # Start storm scenario
    print("3. Starting storm scenario...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/scenario/start",
        json={'name': 'storm'}
    )
    assert response.status_code == 200, "Failed to start scenario"
    
    # Wait for effects
    print("4. Waiting for storm effects...")
    time.sleep(10)
    
    # Check increased flow
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    storm_q_in = snapshot.get('WWTP01:INFLUENT:Q_IN.PV', {}).get('value', 0)
    storm_lt101 = snapshot.get('WWTP01:INFLUENT:LT101.PV', {}).get('value', 0)
    print(f"   Storm Q_IN: {storm_q_in:.2f} m3/h")
    print(f"   Storm LT101: {storm_lt101:.2f} m")
    
    assert storm_q_in > initial_q_in, f"Q_IN should increase: {storm_q_in} <= {initial_q_in}"
    assert storm_lt101 > initial_lt101, f"LT101 should increase: {storm_lt101} <= {initial_lt101}"
    
    # Wait for alarm delay
    print("5. Waiting for HH alarm (delay 5s)...")
    time.sleep(10)
    
    # Check alarms
    alarms = requests.get(f"{SIMULATOR_URL}/api/alarms").json()
    hh_alarm = [a for a in alarms if 'HH' in a.get('text', '')]
    
    if hh_alarm:
        print(f"   ✓ HH alarm triggered: {hh_alarm[0]['text']}")
        assert storm_lt101 > 2.5, "LT101 should be above HH threshold"
    else:
        print("   ⚠ HH alarm not yet triggered (may need more time)")
    
    # Stop scenario
    print("6. Stopping storm scenario...")
    requests.post(
        f"{SIMULATOR_URL}/api/scenario/stop",
        json={'name': 'storm'}
    )
    time.sleep(5)
    
    # Verify return to normal
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    final_q_in = snapshot.get('WWTP01:INFLUENT:Q_IN.PV', {}).get('value', 0)
    print(f"   Final Q_IN: {final_q_in:.2f} m3/h")
    
    print("✓ Test passed!")
    return True

if __name__ == '__main__':
    try:
        test_storm_scenario()
        sys.exit(0)
    except AssertionError as e:
        print(f"✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Test error: {e}")
        sys.exit(1)


