import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="credential.env")

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="", 
        database="Netra"
    )

def update_schema_phase4():
    conn = get_db()
    cur = conn.cursor()

    try:
        # Create CV Reviews Table
        print("Creating cv_reviews table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cv_reviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                evidence_id INT NOT NULL,
                reviewer_id INT NOT NULL,
                feedback_type VARCHAR(50), -- 'False Positive', 'Missed Object', 'Correct'
                comments TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (evidence_id) REFERENCES evidence(id),
                FOREIGN KEY (reviewer_id) REFERENCES users(id)
            )
        """)
        
        conn.commit()
        print("Phase 4 Schema update completed!")

    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    update_schema_phase4()
