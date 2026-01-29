import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="credential.env")

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="", # Assuming empty password as per app.py
        database="Netra"
    )

def update_schema():
    conn = get_db()
    cur = conn.cursor()

    try:
        # 1. Update Users Table
        print("Updating users table...")
        try:
            cur.execute("ALTER TABLE users ADD COLUMN sub_role VARCHAR(50) DEFAULT 'Investigator'")
        except mysql.connector.Error as err:
            print(f"Skipping sub_role add (probably exists): {err}")
        
        # 2. Create Cases Table
        print("Creating cases table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                id INT AUTO_INCREMENT PRIMARY KEY,
                case_id VARCHAR(50) UNIQUE NOT NULL, -- Custom format NETRA-202X-001
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) DEFAULT 'Open', -- Open, Closed, Pending Closure
                assigned_officer_id INT,
                created_by INT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                closed_at DATETIME,
                is_locked BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (assigned_officer_id) REFERENCES users(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            )
        """)

        # 3. Create Evidence Table
        print("Creating evidence table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS evidence (
                id INT AUTO_INCREMENT PRIMARY KEY,
                case_id INT NOT NULL,
                uploader_id INT NOT NULL,
                file_path VARCHAR(512) NOT NULL,
                file_type VARCHAR(50), -- image, video, document
                tags VARCHAR(255),
                status VARCHAR(50) DEFAULT 'Pending', -- Pending, Verified, Rejected
                is_draft BOOLEAN DEFAULT FALSE,
                cv_data JSON,
                ai_feedback VARCHAR(50), -- Useful, Not Useful
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(id),
                FOREIGN KEY (uploader_id) REFERENCES users(id)
            )
        """)

        # 4. Create Case Notes Table
        print("Creating case_notes table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS case_notes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                case_id INT NOT NULL,
                officer_id INT NOT NULL,
                note TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (case_id) REFERENCES cases(id),
                FOREIGN KEY (officer_id) REFERENCES users(id)
            )
        """)

        # 5. Create Audit Logs Table (Evidence Audit Trail)
        print("Creating audit_logs table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                action VARCHAR(100) NOT NULL, -- Uploaded, Viewed, Verified
                target_id INT, -- ID of the evidence or case
                target_type VARCHAR(50), -- 'evidence', 'case'
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 6. Create Notifications Table
        print("Creating notifications table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                message TEXT NOT NULL,
                is_read BOOLEAN DEFAULT FALSE,
                type VARCHAR(50), -- 'alert', 'info', 'payment'
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # 7. Create System Config Table
        print("Creating system_config table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                config_key VARCHAR(100) PRIMARY KEY,
                config_value TEXT
            )
        """)
        
        # Insert default configs if not exist
        cur.execute("INSERT IGNORE INTO system_config (config_key, config_value) VALUES ('cv_enabled', 'true')")
        cur.execute("INSERT IGNORE INTO system_config (config_key, config_value) VALUES ('password_policy', 'medium')")

        conn.commit()
        print("Schema update completed successfully!")

    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    update_schema()
