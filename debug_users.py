import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv("credential.env")

def debug_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="Netra"
        )
        cur = conn.cursor(dictionary=True)
        
        # Check Columns in users table
        cur.execute("DESCRIBE users")
        columns = cur.fetchall()
        print("--- User Table Schema ---")
        for col in columns:
            print(f"{col['Field']} - {col['Type']}")
            
        # Check Users
        cur.execute("SELECT id, name, email, password, role, status FROM users")
        users = cur.fetchall()
        print("\n--- Existing Users ---")
        for u in users:
            pwd_display = u['password'] if u.get('password') else "NULL"
            print(f"ID: {u['id']}, Name: {u['name']}, Email: {u['email']}, Pass: {pwd_display}, Role: {u['role']}, Status: {u['status']}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_db()
