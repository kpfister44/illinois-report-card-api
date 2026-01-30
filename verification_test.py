#!/usr/bin/env python3
"""Quick verification script to test core functionality before implementing new features."""

import requests
import sys

BASE_URL = "http://localhost:8000"
TEST_API_KEY = "test_key_verification_12345"

def test_api_key_authentication():
    """Test #2: Valid API key authentication allows access to protected endpoints"""
    print("Testing: Valid API key authentication...")

    # Test authenticated request to /years
    headers = {"Authorization": f"Bearer {TEST_API_KEY}"}
    response = requests.get(f"{BASE_URL}/years", headers=headers)

    if response.status_code != 200:
        print(f"❌ Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False

    print(f"✅ Authentication works - got {len(response.json())} years")
    return True

def test_schools_endpoint():
    """Test #23: GET /schools/{year} returns list of schools with pagination"""
    print("\nTesting: GET /schools/{year} with pagination...")

    headers = {"Authorization": f"Bearer {TEST_API_KEY}"}

    # Test getting schools for 2025
    response = requests.get(
        f"{BASE_URL}/schools/2025",
        headers=headers,
        params={"limit": 10, "offset": 0}
    )

    if response.status_code != 200:
        print(f"❌ Expected 200, got {response.status_code}")
        print(f"Response: {response.text}")
        return False

    data = response.json()

    if "data" not in data:
        print(f"❌ Response missing 'data' field")
        print(f"Response: {data}")
        return False

    if "meta" not in data:
        print(f"❌ Response missing 'meta' field")
        return False

    # Check for required meta fields
    meta = data['meta']
    required_fields = ['total', 'limit', 'offset']
    missing_fields = [f for f in required_fields if f not in meta]

    if missing_fields:
        print(f"❌ Meta missing required fields: {missing_fields}")
        print(f"   Actual meta: {meta}")
        return False

    print(f"✅ Schools endpoint works - got {len(data['data'])} schools")
    print(f"   Meta: total={meta['total']}, limit={meta['limit']}, offset={meta['offset']}")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("VERIFICATION TESTS - Checking core functionality")
    print("=" * 60)

    results = []
    results.append(("API Key Authentication", test_api_key_authentication()))
    results.append(("Schools Endpoint", test_schools_endpoint()))

    print("\n" + "=" * 60)
    print("RESULTS:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("✅ All verification tests passed - safe to proceed with new work")
        sys.exit(0)
    else:
        print("❌ Some tests failed - must fix before implementing new features")
        sys.exit(1)
