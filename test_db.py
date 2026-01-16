import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv("credential.env")

try:
    print("Attempting to connect to database...")
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="", # Assuming empty password from code
        database="Netra"
    )
    if conn.is_connected():
        print("SUCCESS: Connected to database 'Netra'")
        cur = conn.cursor()
        cur.execute("SHOW TABLES")
        tables = cur.fetchall()
        print("Tables:", tables)
        conn.close()
    else:
        print("FAILED: Could not connect (no exception raised but not connected?)")
except Exception as e:
    print(f"ERROR: {e}")
