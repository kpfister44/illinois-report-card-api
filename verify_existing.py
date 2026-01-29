#!/usr/bin/env python3
"""Quick verification script to test existing passing functionality"""

import requests
import sys

BASE_URL = "http://localhost:8000"

# Use the test API key
API_KEY = "test_key_verification_12345"
headers = {"Authorization": f"Bearer {API_KEY}"}

print("🔍 Verifying existing functionality...")
print()

# Test 1: Verify /years endpoint works (Test #5)
print("Test 1: GET /years endpoint")
response = requests.get(f"{BASE_URL}/years", headers=headers)
if response.status_code == 200:
    data = response.json()
    if "data" in data and isinstance(data["data"], list):
        print(f"✅ /years endpoint working - returns {len(data['data'])} years")
    else:
        print("❌ /years response format incorrect")
        sys.exit(1)
else:
    print(f"❌ /years returned {response.status_code}")
    sys.exit(1)

print()

# Test 2: Verify /districts/2025 endpoint with pagination (Test #36)
print("Test 2: GET /districts/2025 endpoint with pagination")
response = requests.get(f"{BASE_URL}/districts/2025?limit=5", headers=headers)
if response.status_code == 200:
    data = response.json()
    if "data" in data and isinstance(data["data"], list):
        print(f"✅ /districts/2025 endpoint working - returns {len(data['data'])} districts")
        if "pagination" in data:
            print(f"   Pagination: total={data['pagination'].get('total')}, limit={data['pagination'].get('limit')}")
    else:
        print("❌ /districts/2025 response format incorrect")
        sys.exit(1)
else:
    print(f"❌ /districts/2025 returned {response.status_code}")
    sys.exit(1)

print()
print("✅ All verification tests passed! Existing functionality is working.")
