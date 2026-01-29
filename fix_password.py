import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv("credential.env")

def fix_user():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="Netra"
        )
        cur = conn.cursor()
        
        # Update TestCop password
        # Using plaintext 'password123' as per app.py's current insecurity
        cur.execute("UPDATE users SET password='password123' WHERE email='testcop@netra.com'")
        conn.commit()
        print("Updated TestCop password to 'password123'")
        
        # Verify
        cur.execute("SELECT email, password FROM users WHERE email='testcop@netra.com'")
        print(cur.fetchone())

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_user()
