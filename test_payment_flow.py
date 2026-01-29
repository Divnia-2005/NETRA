import unittest
from app import app, get_db
import json

class PaymentTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.secret_key = 'test_secret'
        self.client = app.test_client()
        
        # Create a test officer user if not exists or ensure ID
        # For simplicity, we'll just mock the session in the test 
        # assuming the ID exists in the real DB or we use a dummy ID.
        # We need a valid user ID for foreign keys.
        # I'll query one first.
        with app.app_context():
            conn = get_db()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id FROM users WHERE role='officer' LIMIT 1")
            user = cur.fetchone()
            if not user:
                # Create one
                cur.execute("INSERT INTO users (name, email, role, status) VALUES ('TestCop', 'testcop@netra.com', 'officer', 'approved')")
                conn.commit()
                self.officer_id = cur.lastrowid
            else:
                self.officer_id = user['id']
            cur.close()
            conn.close()

    def test_flow(self):
        # 1. Login (Mock Session)
        with self.client.session_transaction() as sess:
            sess['user'] = {'id': self.officer_id, 'role': 'officer', 'name': 'TestCop'}
            
        # 2. Issue Challan
        print("Testing Issue Challan...")
        res = self.client.post('/api/issue_challan', json={
            'amount': 500,
            'reason': 'Test Violation',
            'violator_name': 'John Doe'
        })
        data = res.get_json()
        print("Issue Response:", data)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(data['success'])
        
        challan_id = data['challan_id']
        
        # 3. Pay Page
        print(f"Testing Pay Page for Challan {challan_id}...")
        res = self.client.get(f'/pay_challan/{challan_id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'NETRA', res.data)
        self.assertIn(b'John Doe', res.data)
        self.assertIn(b'500', res.data)
        print("Pay Page Loaded Successfully.")

if __name__ == '__main__':
    unittest.main()
