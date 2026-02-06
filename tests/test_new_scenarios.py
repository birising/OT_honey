#!/usr/bin/env python3
"""
Test: New Scenarios (screen_blockage, do_sensor_failure, chemical_overdose)
"""

import time
import requests
import sys

SIMULATOR_URL = 'http://localhost:8080'


def test_screen_blockage():
    """Test screen blockage scenario"""
    print("=== Test: Screen Blockage Scenario ===")

    # Reset
    print("1. Resetting system...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(2)

    # Get initial state
    print("2. Getting initial state...")
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    initial_dp = snapshot.get('WWTP01:SCREENING:SCR101.DP', {}).get('value', 0)
    initial_fault = snapshot.get('WWTP01:SCREENING:SCR101.FAULT', {}).get('value', 0)
    print(f"   Initial SCR101.DP: {initial_dp:.3f} bar")
    print(f"   Initial SCR101.FAULT: {initial_fault}")

    assert initial_fault == 0, "Screen should not be in fault initially"

    # Start screen_blockage scenario
    print("3. Starting screen_blockage scenario...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/scenario/start",
        json={'name': 'screen_blockage'}
    )
    assert response.status_code == 200, "Failed to start scenario"

    # Wait for effects
    print("4. Waiting for blockage effects...")
    time.sleep(5)

    # Check state
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    blocked_dp = snapshot.get('WWTP01:SCREENING:SCR101.DP', {}).get('value', 0)
    blocked_fault = snapshot.get('WWTP01:SCREENING:SCR101.FAULT', {}).get('value', 0)
    print(f"   Blocked SCR101.DP: {blocked_dp:.3f} bar")
    print(f"   Blocked SCR101.FAULT: {blocked_fault}")

    assert blocked_dp > 0.5, f"DP should be high during blockage: {blocked_dp}"
    assert blocked_fault == 1, f"Screen should be in fault: {blocked_fault}"

    # Check alarms
    print("5. Checking alarms...")
    time.sleep(15)
    alarms_resp = requests.get(f"{SIMULATOR_URL}/api/alarms").json()
    screen_alarms = [a for a in alarms_resp if 'SCR101' in a.get('tag', '') or 'screen' in a.get('text', '').lower()]
    if screen_alarms:
        print(f"   Screen alarm triggered: {screen_alarms[0]['text']}")
    else:
        print("   Warning: Screen alarm not yet triggered")

    # Stop scenario
    print("6. Stopping scenario...")
    requests.post(
        f"{SIMULATOR_URL}/api/scenario/stop",
        json={'name': 'screen_blockage'}
    )
    time.sleep(5)

    # Verify return to normal
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    final_dp = snapshot.get('WWTP01:SCREENING:SCR101.DP', {}).get('value', 0)
    final_fault = snapshot.get('WWTP01:SCREENING:SCR101.FAULT', {}).get('value', 0)
    print(f"   Final SCR101.DP: {final_dp:.3f} bar")
    print(f"   Final SCR101.FAULT: {final_fault}")
    assert final_fault == 0, "Screen fault should be cleared"

    print("   Test passed!")
    return True


def test_do_sensor_failure():
    """Test DO sensor failure scenario"""
    print("\n=== Test: DO Sensor Failure Scenario ===")

    # Reset
    print("1. Resetting system...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(2)

    # Get initial state
    print("2. Getting initial state...")
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    initial_do = snapshot.get('WWTP01:AERATION:DO301.PV', {}).get('value', 0)
    initial_blw_sp = snapshot.get('WWTP01:AERATION:BLW201.SP', {}).get('value', 0)
    print(f"   Initial DO301.PV: {initial_do:.2f} mg/L")
    print(f"   Initial BLW201.SP: {initial_blw_sp:.1f}%")

    # Start do_sensor_failure scenario
    print("3. Starting do_sensor_failure scenario...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/scenario/start",
        json={'name': 'do_sensor_failure'}
    )
    assert response.status_code == 200, "Failed to start scenario"

    # Wait for effects
    print("4. Waiting for sensor failure effects...")
    time.sleep(5)

    # Check state - DO should be low, blower overdriving
    # Note: PID controller fights the scenario each cycle, so SP won't always
    # be exactly 100%, but should be elevated above normal (~50%)
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    fault_do = snapshot.get('WWTP01:AERATION:DO301.PV', {}).get('value', 0)
    fault_blw_sp = snapshot.get('WWTP01:AERATION:BLW201.SP', {}).get('value', 0)
    fault_blw_cmd = snapshot.get('WWTP01:AERATION:BLW201.CMD', {}).get('value', 0)
    print(f"   Fault DO301.PV: {fault_do:.2f} mg/L")
    print(f"   Fault BLW201.SP: {fault_blw_sp:.1f}%")
    print(f"   Fault BLW201.CMD: {fault_blw_cmd}")

    assert fault_blw_sp >= 95.0, f"Blower SP should be near max: {fault_blw_sp}"
    assert fault_blw_cmd == 1, f"Blower should be commanded ON: {fault_blw_cmd}"

    # Stop scenario
    print("5. Stopping scenario...")
    requests.post(
        f"{SIMULATOR_URL}/api/scenario/stop",
        json={'name': 'do_sensor_failure'}
    )
    time.sleep(5)

    # Verify recovery
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    final_do = snapshot.get('WWTP01:AERATION:DO301.PV', {}).get('value', 0)
    final_blw_sp = snapshot.get('WWTP01:AERATION:BLW201.SP', {}).get('value', 0)
    print(f"   Final DO301.PV: {final_do:.2f} mg/L")
    print(f"   Final BLW201.SP: {final_blw_sp:.1f}%")

    print("   Test passed!")
    return True


def test_chemical_overdose():
    """Test chemical overdose scenario"""
    print("\n=== Test: Chemical Overdose Scenario ===")

    # Reset
    print("1. Resetting system...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(2)

    # Get initial state
    print("2. Getting initial state...")
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    initial_rate = snapshot.get('WWTP01:CHEMICAL:DOSE_FECL3.PV', {}).get('value', 0)
    initial_sp = snapshot.get('WWTP01:CHEMICAL:DOSE_FECL3.SP', {}).get('value', 0)
    initial_tank = snapshot.get('WWTP01:CHEMICAL:TANK501.LEVEL', {}).get('value', 0)
    print(f"   Initial DOSE_FECL3.PV: {initial_rate:.2f} L/h")
    print(f"   Initial DOSE_FECL3.SP: {initial_sp:.2f} L/h")
    print(f"   Initial TANK501.LEVEL: {initial_tank:.1f}%")

    # Start chemical_overdose scenario
    print("3. Starting chemical_overdose scenario...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/scenario/start",
        json={'name': 'chemical_overdose'}
    )
    assert response.status_code == 200, "Failed to start scenario"

    # Wait for effects
    print("4. Waiting for overdose effects...")
    time.sleep(5)

    # Check state
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    overdose_rate = snapshot.get('WWTP01:CHEMICAL:DOSE_FECL3.PV', {}).get('value', 0)
    overdose_sp = snapshot.get('WWTP01:CHEMICAL:DOSE_FECL3.SP', {}).get('value', 0)
    pmp501_auto = snapshot.get('WWTP01:CHEMICAL:PMP501.AUTO', {}).get('value', 0)
    pmp501_cmd = snapshot.get('WWTP01:CHEMICAL:PMP501.CMD', {}).get('value', 0)
    print(f"   Overdose DOSE_FECL3.PV: {overdose_rate:.2f} L/h")
    print(f"   Overdose DOSE_FECL3.SP: {overdose_sp:.2f} L/h")
    print(f"   PMP501.AUTO: {pmp501_auto}")
    print(f"   PMP501.CMD: {pmp501_cmd}")

    assert overdose_sp > 8.0, f"Dosing SP should be very high: {overdose_sp}"
    assert pmp501_auto == 0, f"PMP501 should be in manual: {pmp501_auto}"
    assert pmp501_cmd == 1, f"PMP501 should be commanded ON: {pmp501_cmd}"

    # Check alarms after delay
    print("5. Checking alarms...")
    time.sleep(20)
    alarms_resp = requests.get(f"{SIMULATOR_URL}/api/alarms").json()
    chem_alarms = [a for a in alarms_resp if 'overdose' in a.get('text', '').lower() or 'DOSE' in a.get('tag', '')]
    if chem_alarms:
        print(f"   Chemical alarm triggered: {chem_alarms[0]['text']}")
    else:
        print("   Warning: Chemical overdose alarm not yet triggered")

    # Stop scenario
    print("6. Stopping scenario...")
    requests.post(
        f"{SIMULATOR_URL}/api/scenario/stop",
        json={'name': 'chemical_overdose'}
    )
    time.sleep(5)

    # Verify recovery
    snapshot = requests.get(f"{SIMULATOR_URL}/api/snapshot").json()
    final_rate = snapshot.get('WWTP01:CHEMICAL:DOSE_FECL3.PV', {}).get('value', 0)
    final_auto = snapshot.get('WWTP01:CHEMICAL:PMP501.AUTO', {}).get('value', 0)
    print(f"   Final DOSE_FECL3.PV: {final_rate:.2f} L/h")
    print(f"   Final PMP501.AUTO: {final_auto}")
    assert final_auto == 1, "PMP501 should return to AUTO"

    print("   Test passed!")
    return True


if __name__ == '__main__':
    try:
        test_screen_blockage()
        test_do_sensor_failure()
        test_chemical_overdose()
        print("\nAll new scenario tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest error: {e}")
        sys.exit(1)
