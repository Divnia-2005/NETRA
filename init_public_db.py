import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv("credential.env")

def update_schema():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="Netra"
        )
        cursor = conn.cursor()

        # Create public_entries table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS public_entries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                phone VARCHAR(15) NOT NULL,
                role ENUM('attendee', 'volunteer', 'media') NOT NULL,
                count INT DEFAULT 1,
                amount FLOAT NOT NULL,
                status VARCHAR(50) DEFAULT 'Pending',
                payment_id VARCHAR(100),
                qr_code_path VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("Table 'public_entries' created or already exists.")

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_schema()
