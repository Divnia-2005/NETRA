import mysql.connector
import os
from dotenv import load_dotenv

# Load env
load_dotenv("credential.env")

def init_db():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="Netra"
    )
    cur = conn.cursor()
    
    # Create Challans Table
    query = """
    CREATE TABLE IF NOT EXISTS challans (
        id INT AUTO_INCREMENT PRIMARY KEY,
        amount FLOAT NOT NULL,
        reason VARCHAR(255) NOT NULL,
        status VARCHAR(50) DEFAULT 'Pending',
        payment_id VARCHAR(100),
        issued_by INT NOT NULL,
        violator_name VARCHAR(100),
        violator_email VARCHAR(120),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        paid_at DATETIME,
        FOREIGN KEY (issued_by) REFERENCES users(id)
    );
    """
    
    cur.execute(query)
    conn.commit()
    print("Challans table created successfully.")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    init_db()
