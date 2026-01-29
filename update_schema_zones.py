import mysql.connector

def update_schema():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="Netra"
        )
        cur = conn.cursor()

        # 1. Create Restricted Zones Table
        print("Creating restricted_zones table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS restricted_zones (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                coordinates TEXT, -- Storing JSON string or simple description for now
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                violation_type VARCHAR(100) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 2. Update Evidence Table (Add columns if they don't exist)
        print("Updating evidence table...")
        try:
            cur.execute("ALTER TABLE evidence ADD COLUMN source_type VARCHAR(50) DEFAULT 'Manual'")
        except:
            print("Column source_type might already exist.")
        
        try:
            cur.execute("ALTER TABLE evidence ADD COLUMN review_status VARCHAR(50) DEFAULT 'Verified'") 
            # Default 'Verified' for manual uploads, Auto will be 'Pending'
        except:
            print("Column review_status might already exist.")

        try:
             cur.execute("ALTER TABLE evidence ADD COLUMN zone_id INT DEFAULT NULL")
        except:
             print("Column zone_id might already exist.")
        
        try:
             cur.execute("ALTER TABLE evidence ADD COLUMN confidence_score FLOAT DEFAULT 0.0")
        except:
             print("Column confidence_score might already exist.")


        conn.commit()
        print("Schema updated successfully!")
        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_schema()
