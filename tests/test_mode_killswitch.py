#!/usr/bin/env python3
"""
Test: Operating Mode and Kill Switch
Tests global operating mode changes and emergency stop behavior
"""

import time
import requests
import sys

SIMULATOR_URL = 'http://localhost:8080'


def test_mode_changes():
    """Test operating mode transitions"""
    print("=== Test: Operating Mode Changes ===")

    # Reset
    print("1. Resetting system...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(2)

    # Verify initial mode is AUTO
    print("2. Checking initial mode...")
    response = requests.get(f"{SIMULATOR_URL}/api/mode")
    assert response.status_code == 200
    mode_data = response.json()
    assert mode_data['mode'] == 'AUTO', f"Expected AUTO, got {mode_data['mode']}"
    print(f"   Initial mode: {mode_data['mode']}")

    # Switch to MANUAL
    print("3. Switching to MANUAL...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/mode",
        json={'mode': 'MANUAL'}
    )
    assert response.status_code == 200
    result = response.json()
    assert result['mode'] == 'MANUAL', f"Expected MANUAL, got {result['mode']}"
    print(f"   Mode set to: {result['mode']}")

    # Verify mode persists
    time.sleep(2)
    response = requests.get(f"{SIMULATOR_URL}/api/mode")
    assert response.json()['mode'] == 'MANUAL', "Mode should persist as MANUAL"

    # In MANUAL mode, equipment should still run but not auto-control
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    global_mode = snapshot.get('WWTP01:SYSTEM:GLOBAL_MODE.PV', {}).get('value', -1)
    assert global_mode == 1, f"GLOBAL_MODE tag should be 1 (MANUAL), got {global_mode}"
    print(f"   GLOBAL_MODE.PV tag: {global_mode}")

    # Switch to MAINTENANCE
    print("4. Switching to MAINTENANCE...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/mode",
        json={'mode': 'MAINTENANCE'}
    )
    assert response.status_code == 200
    assert response.json()['mode'] == 'MAINTENANCE'
    print(f"   Mode set to: MAINTENANCE")

    time.sleep(3)

    # In MAINTENANCE, all equipment should be stopped
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    pmp101_cmd = snapshot.get('WWTP01:INFLUENT:PMP101.CMD', {}).get('value', -1)
    blw201_cmd = snapshot.get('WWTP01:AERATION:BLW201.CMD', {}).get('value', -1)
    pmp301_cmd = snapshot.get('WWTP01:PRIMARY:PMP301.CMD', {}).get('value', -1)
    pmp501_cmd = snapshot.get('WWTP01:CHEMICAL:PMP501.CMD', {}).get('value', -1)
    print(f"   PMP101.CMD: {pmp101_cmd}")
    print(f"   BLW201.CMD: {blw201_cmd}")
    print(f"   PMP301.CMD: {pmp301_cmd}")
    print(f"   PMP501.CMD: {pmp501_cmd}")

    assert pmp101_cmd == 0, f"PMP101 should be stopped in MAINTENANCE: {pmp101_cmd}"
    assert blw201_cmd == 0, f"BLW201 should be stopped in MAINTENANCE: {blw201_cmd}"
    assert pmp301_cmd == 0, f"PMP301 should be stopped in MAINTENANCE: {pmp301_cmd}"
    assert pmp501_cmd == 0, f"PMP501 should be stopped in MAINTENANCE: {pmp501_cmd}"

    # Switch back to AUTO
    print("5. Switching back to AUTO...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/mode",
        json={'mode': 'AUTO'}
    )
    assert response.status_code == 200
    assert response.json()['mode'] == 'AUTO'
    print(f"   Mode set to: AUTO")

    # Test invalid mode
    print("6. Testing invalid mode...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/mode",
        json={'mode': 'INVALID'}
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    print(f"   Invalid mode correctly rejected")

    # Test missing mode
    print("7. Testing missing mode field...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/mode",
        json={}
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    print(f"   Missing mode correctly rejected")

    print("   Mode change tests passed!")
    return True


def test_kill_switch():
    """Test emergency kill switch"""
    print("\n=== Test: Kill Switch ===")

    # Reset
    print("1. Resetting system...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(2)

    # Verify kill switch is inactive
    response = requests.get(f"{SIMULATOR_URL}/health")
    health = response.json()
    assert health['kill_switch'] == False, "Kill switch should be inactive after reset"
    print(f"   Kill switch: {health['kill_switch']}")

    # Activate kill switch
    print("2. Activating kill switch...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/killswitch",
        json={'activate': True}
    )
    assert response.status_code == 200
    result = response.json()
    assert result['kill_switch'] == True, f"Kill switch should be active: {result}"
    print(f"   Kill switch activated")

    time.sleep(3)

    # Verify mode is MAINTENANCE
    response = requests.get(f"{SIMULATOR_URL}/api/mode")
    mode = response.json()['mode']
    assert mode == 'MAINTENANCE', f"Mode should be MAINTENANCE with kill switch: {mode}"
    print(f"   Mode: {mode}")

    # Verify all equipment stopped
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    kill_switch_tag = snapshot.get('WWTP01:SYSTEM:KILL_SWITCH.PV', {}).get('value', -1)
    assert kill_switch_tag == 1, f"KILL_SWITCH tag should be 1: {kill_switch_tag}"

    pmp101_cmd = snapshot.get('WWTP01:INFLUENT:PMP101.CMD', {}).get('value', -1)
    blw201_cmd = snapshot.get('WWTP01:AERATION:BLW201.CMD', {}).get('value', -1)
    scr101_cmd = snapshot.get('WWTP01:SCREENING:SCR101.CMD', {}).get('value', -1)
    print(f"   KILL_SWITCH.PV: {kill_switch_tag}")
    print(f"   PMP101.CMD: {pmp101_cmd}")
    print(f"   BLW201.CMD: {blw201_cmd}")
    print(f"   SCR101.CMD: {scr101_cmd}")

    assert pmp101_cmd == 0, "PMP101 should be stopped with kill switch"
    assert blw201_cmd == 0, "BLW201 should be stopped with kill switch"
    assert scr101_cmd == 0, "SCR101 should be stopped with kill switch"

    # Deactivate kill switch
    print("3. Deactivating kill switch...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/killswitch",
        json={'activate': False}
    )
    assert response.status_code == 200
    assert response.json()['kill_switch'] == False
    print(f"   Kill switch deactivated")

    # Set back to AUTO
    requests.post(f"{SIMULATOR_URL}/api/mode", json={'mode': 'AUTO'})
    time.sleep(2)

    # Verify health endpoint
    response = requests.get(f"{SIMULATOR_URL}/health")
    health = response.json()
    assert health['kill_switch'] == False, "Kill switch should be inactive"
    assert health['mode'] == 'AUTO', f"Mode should be AUTO: {health['mode']}"
    print(f"   Health: mode={health['mode']}, kill_switch={health['kill_switch']}")

    # Test invalid killswitch request
    print("4. Testing invalid kill switch request...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/killswitch",
        json={}
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    print(f"   Invalid request correctly rejected")

    print("   Kill switch tests passed!")
    return True


if __name__ == '__main__':
    try:
        test_mode_changes()
        test_kill_switch()
        print("\nAll mode/killswitch tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest error: {e}")
        sys.exit(1)
