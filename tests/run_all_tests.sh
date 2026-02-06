#!/bin/bash
# Run all WWTP Honeypot tests

set -e

echo "Running all WWTP Honeypot tests..."
echo ""

# Check if simulator is running
if ! curl -s http://localhost:8080/health > /dev/null; then
    echo "Error: Simulator not running on http://localhost:8080"
    echo "Please start with: docker-compose up -d"
    exit 1
fi

# Run tests
echo "=== Test 1: Storm Scenario ==="
python3 test_storm.py
echo ""

echo "=== Test 2: VFD Fault Scenario ==="
python3 test_vfd_fault.py
echo ""

echo "=== Test 3: Modbus Write Whitelist ==="
python3 test_modbus_write_whitelist.py
echo ""

echo "=== Test 4: New Scenarios (Screen Blockage, DO Sensor Failure, Chemical Overdose) ==="
python3 test_new_scenarios.py
echo ""

echo "=== Test 5: Trends API ==="
python3 test_trends_api.py
echo ""

echo "=== Test 6: Operating Mode & Kill Switch ==="
python3 test_mode_killswitch.py
echo ""

echo "=== Test 7: Alarm Acknowledgement ==="
python3 test_alarm_acknowledge.py
echo ""

echo "All tests completed!"
