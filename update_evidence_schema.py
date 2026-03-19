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
