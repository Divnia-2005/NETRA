import json
from datetime import datetime

# Mimic the DB user record with non-serializable datetime objects
db_user = {
    "id": 1,
    "name": "Divinia M. Antony",
    "email": "divinia@example.com",
    "role": "officer",
    "status": "approved",
    "created_at": datetime.now(),
    "otp_expiry": datetime.now()
}

# 1. Test original (failing) approach
try:
    print("Testing original approach (storing full dict)...")
    json.dumps(db_user)
    print("SUCCESS (Unexpectedly!)")
except TypeError as e:
    print(f"FAILED as expected: {e}")

# 2. Test fixed approach
fixed_session_user = {
    "id": db_user["id"],
    "name": db_user["name"],
    "email": db_user["email"],
    "role": db_user["role"],
    "status": db_user["status"]
}

try:
    print("\nTesting fixed approach (storing serializable fields)...")
    json.dumps(fixed_session_user)
    print("SUCCESS!")
except TypeError as e:
    print(f"FAILED: {e}")

# 3. Test name validation logic
import re
def validate_name(name):
    return bool(re.match(r"^[a-zA-Z\s.-]+$", name))

test_names = ["John Doe", "J. Doe", "John-Doe", "John Doe 123"]
print("\nTesting name validation:")
for name in test_names:
    print(f"'{name}': {'Valid' if validate_name(name) else 'Invalid'}")
