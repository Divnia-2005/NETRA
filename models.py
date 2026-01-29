"""
Database models for NETRA Surveillance System.
Uses SQLAlchemy with MySQL backend.
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    """User model for local and OAuth authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)  # Null for OAuth users
    google_id = db.Column(db.String(255), unique=True, nullable=True)  # Google sub
    picture = db.Column(db.String(512), nullable=True)
    role = db.Column(db.String(20), default='officer')  # 'admin' or 'officer'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_password(self, password):
        """Hash and store password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against stored hash."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """Return user as dictionary."""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'picture': self.picture,
            'role': self.role,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<User {self.email} ({self.role})>'

class Alert(db.Model):
    """Alert/Log model for surveillance incidents."""
    __tablename__ = 'alerts'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    location = db.Column(db.String(255), nullable=False)
    alert_type = db.Column(db.String(100), nullable=False)  # 'overcrowding', 'suspicious', etc.
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='pending')  # 'pending', 'investigating', 'resolved'
    severity = db.Column(db.String(20), default='low')  # 'low', 'medium', 'high'
    snapshot_path = db.Column(db.String(512), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'location': self.location,
            'alert_type': self.alert_type,
            'description': self.description,
            'status': self.status,
            'severity': self.severity,
            'snapshot_path': self.snapshot_path
        }
    
    def __repr__(self):
        return f'<Alert {self.alert_type} @ {self.location}>'

class Challan(db.Model):
    """Model for traffic fines/challans."""
    __tablename__ = 'challans'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='Pending') # 'Pending', 'Paid'
    payment_id = db.Column(db.String(100), nullable=True) # Razorpay Payment ID
    issued_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    violator_name = db.Column(db.String(100), nullable=True)
    violator_email = db.Column(db.String(120), nullable=True) # To send link
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'reason': self.reason,
            'status': self.status,
            'payment_id': self.payment_id,
            'violator_name': self.violator_name,
            'created_at': self.created_at.isoformat(),
            'paid_at': self.paid_at.isoformat() if self.paid_at else None
        }
