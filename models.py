from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Enum
from datetime import datetime

#Create an instance of sqlalchemy for interacting with the database.
db=SQLAlchemy()

#Define custom ENUM types for various model fields using the generic Enum
user_role_enum = Enum('customer', 'property_owner', name='user_role_enum')

#Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False) #renamed from password.
    role = db.Column(user_role_enum, default='customer') #this added role will also help for RAG differentiation.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    #Relationships
    hotels=db.relationship('Hotel', backref='owner', lazy=True)
    reviews=db.relationship('Review', backref='author', lazy=True)
    
    def set_password(self, password):
        if len(password)<8:
            raise ValueError("Password must be at least 8 characters")
        self.password_hash=generate_password_hash(password) #using werkzeug method.
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Hotel(db.Model):
    __tablename__ = 'hotels'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)#Links hotel to a user(owner)
    name = db.Column(db.String(100), nullable=False, index=True)
    location = db.Column(db.String(100), nullable=False, index=True)
    price = db.Column(db.Numeric(10,2), nullable=False)
    description = db.Column(db.Text)
    #owner = db.relationship('User', backref='hotels')#establishing relationship, one user can own multiple hotels.
    amenities= db.Column(db.String(200))

class FAQ(db.Model):
    __tablename__ = 'faqs'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.LargeBinary)#store vector embedding for RAG.

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)
    embedding = db.Column(db.LargeBinary)#store vector embedding for RAG.
    sentiment= db.Column(db.String(20))