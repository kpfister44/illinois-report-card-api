#!/usr/bin/env python3
"""Create a test API key for verification"""

import sqlite3
import hashlib
from datetime import datetime

# Create a test API key
test_key = "test_key_verification_12345"
key_hash = hashlib.sha256(test_key.encode()).hexdigest()
key_prefix = test_key[:8]

conn = sqlite3.connect("data/reportcard.db")
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO api_keys (key_hash, key_prefix, owner_email, owner_name, created_at, is_active, rate_limit_tier, is_admin)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""", (key_hash, key_prefix, "test@example.com", "Test User", datetime.utcnow(), True, "free", False))

conn.commit()
conn.close()

print(f"✅ Created test API key: {test_key}")
