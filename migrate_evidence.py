import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv("credential.env")

def migrate_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="Netra"
        )
        cur = conn.cursor()
        
        # Add column if not exists
        try:
            cur.execute("ALTER TABLE challans ADD COLUMN evidence_path VARCHAR(500) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci DEFAULT NULL")
            conn.commit()
            print("Added evidence_path column.")
        except mysql.connector.Error as err:
            if err.errno == 1060:
                print("Column evidence_path already exists.")
            else:
                print(f"Error adding column: {err}")

        conn.close()
    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    migrate_db()
