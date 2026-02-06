#!/usr/bin/env python3
"""
Test: Trends API
Tests that /api/trends returns data with expected structure
"""

import time
import requests
import sys

SIMULATOR_URL = 'http://localhost:8080'

EXPECTED_TAGS = [
    'WWTP01:INFLUENT:Q_IN.PV',
    'WWTP01:INFLUENT:LT101.PV',
    'WWTP01:AERATION:DO301.PV',
    'WWTP01:AERATION:DO301.SP',
    'WWTP01:EFFLUENT:Q_OUT.PV',
    'WWTP01:EFFLUENT:COD501.PV',
    'WWTP01:SCREENING:SCR101.DP',
    'WWTP01:CHEMICAL:DOSE_FECL3.PV',
    'WWTP01:CHEMICAL:TANK501.LEVEL',
]


def test_trends_api():
    """Test trends API endpoint"""
    print("=== Test: Trends API ===")

    # Reset and wait for some data to accumulate
    print("1. Resetting and waiting for trend data...")
    requests.post(f"{SIMULATOR_URL}/api/reset")
    time.sleep(5)  # Let a few data points accumulate

    # Test 1h range
    print("2. Testing GET /api/trends?range=1h ...")
    response = requests.get(f"{SIMULATOR_URL}/api/trends?range=1h")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    result = response.json()
    assert 'range' in result, "Response missing 'range' field"
    assert 'points' in result, "Response missing 'points' field"
    assert 'data' in result, "Response missing 'data' field"
    assert 'tags' in result, "Response missing 'tags' field"
    assert result['range'] == '1h', f"Expected range '1h', got '{result['range']}'"

    print(f"   Range: {result['range']}")
    print(f"   Points: {result['points']}")
    print(f"   Tags count: {len(result['tags'])}")

    # Check that data has expected structure
    data = result['data']
    assert isinstance(data, list), "Data should be a list"
    assert len(data) > 0, "Data should have at least 1 point after waiting"

    first_point = data[0]
    assert 'timestamp' in first_point, "Data point missing 'timestamp'"
    print(f"   First point has {len(first_point)} fields")

    # Check that expected tags appear in data
    for tag in EXPECTED_TAGS:
        if tag in first_point:
            print(f"   {tag}: {first_point[tag]}")

    # Test 8h range
    print("3. Testing GET /api/trends?range=8h ...")
    response = requests.get(f"{SIMULATOR_URL}/api/trends?range=8h")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    result_8h = response.json()
    assert result_8h['range'] == '8h'
    print(f"   Range: {result_8h['range']}, Points: {result_8h['points']}")

    # Test 24h range
    print("4. Testing GET /api/trends?range=24h ...")
    response = requests.get(f"{SIMULATOR_URL}/api/trends?range=24h")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    result_24h = response.json()
    assert result_24h['range'] == '24h'
    print(f"   Range: {result_24h['range']}, Points: {result_24h['points']}")

    # Test invalid range (should default to 1h)
    print("5. Testing invalid range (should default to 1h)...")
    response = requests.get(f"{SIMULATOR_URL}/api/trends?range=invalid")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Test tags list in response
    print("6. Verifying tags list...")
    tags = result['tags']
    assert len(tags) > 0, "Tags list should not be empty"
    for expected in EXPECTED_TAGS:
        assert expected in tags, f"Missing expected tag: {expected}"
    print(f"   All {len(EXPECTED_TAGS)} expected tags found in response")

    print("Test passed!")
    return True


if __name__ == '__main__':
    try:
        test_trends_api()
        sys.exit(0)
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Test error: {e}")
        sys.exit(1)
