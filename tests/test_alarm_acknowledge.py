#!/usr/bin/env python3
"""
Test: Alarm Acknowledgement
Tests alarm acknowledgement flow via /api/alarm/acknowledge
"""

import time
import requests
import sys

SIMULATOR_URL = 'http://localhost:8080'


def test_alarm_acknowledge():
    """Test alarm acknowledgement flow"""
    print("=== Test: Alarm Acknowledgement ===")

    # Reset
    print("1. Resetting system...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(2)

    # Trigger an alarm by starting VFD fault scenario (immediate alarm)
    print("2. Starting vfd_fault scenario to trigger alarm...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/scenario/start",
        json={'name': 'vfd_fault'}
    )
    assert response.status_code == 200, "Failed to start scenario"

    # Wait for alarm to appear
    print("3. Waiting for alarm...")
    time.sleep(5)

    alarms_resp = requests.get(f"{SIMULATOR_URL}/api/alarms").json()
    print(f"   Active alarms: {len(alarms_resp)}")

    # Find unacknowledged alarm
    unacked = [a for a in alarms_resp if not a.get('acknowledged', True)]
    if not unacked:
        # Any alarm will do
        unacked = alarms_resp

    assert len(unacked) > 0, "Expected at least one alarm"

    alarm = unacked[0]
    alarm_id = alarm['id']
    print(f"   Alarm to acknowledge: id={alarm_id}, text={alarm.get('text', 'N/A')}")
    print(f"   Acknowledged: {alarm.get('acknowledged', 'N/A')}")

    # Acknowledge the alarm
    print("4. Acknowledging alarm...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/alarm/acknowledge",
        json={'id': alarm_id}
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    result = response.json()
    assert result.get('success') == True, f"Expected success: {result}"
    print(f"   Acknowledged: {result}")

    # Verify alarm is now acknowledged
    print("5. Verifying acknowledgement...")
    alarms_resp = requests.get(f"{SIMULATOR_URL}/api/alarms").json()
    acked_alarm = [a for a in alarms_resp if a['id'] == alarm_id]
    if acked_alarm:
        assert acked_alarm[0].get('acknowledged') == True, "Alarm should be acknowledged"
        print(f"   Alarm {alarm_id} is now acknowledged")
    else:
        print(f"   Alarm {alarm_id} no longer in active list (may have cleared)")

    # Test acknowledge non-existent alarm
    print("6. Testing acknowledge of non-existent alarm...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/alarm/acknowledge",
        json={'id': 'nonexistent-alarm-id-12345'}
    )
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"
    print(f"   Non-existent alarm correctly returned 404")

    # Test invalid request (missing id)
    print("7. Testing invalid request (missing id)...")
    response = requests.post(
        f"{SIMULATOR_URL}/api/alarm/acknowledge",
        json={}
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}"
    print(f"   Missing id correctly returned 400")

    # Clean up - stop scenario
    requests.post(
        f"{SIMULATOR_URL}/api/scenario/stop",
        json={'name': 'vfd_fault'}
    )

    print("Test passed!")
    return True


if __name__ == '__main__':
    try:
        test_alarm_acknowledge()
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Test error: {e}")
        sys.exit(1)
