import mysql.connector  # type: ignore

def check_users():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="Netra"
        )
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, name, email, google_id, role, status FROM users")
        users = cur.fetchall()
        print("Existing Users:")
        for user in users:
            print(user)
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error checking users: {e}")

if __name__ == "__main__":
    check_users()
