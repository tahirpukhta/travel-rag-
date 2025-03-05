from flask_sqlalchemy import SQLAlchemy #Enables ORM operations with Flask
from flask_login import UserMixin # helper methods for user authentication
from werkzeug.security import generate_password_hash, check_password_hash # provides functions to hash and check passwords
from sqlalchemy import Enum # allows usage of a generic ENUM type across different databases
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
    contact_number = db.Column(db.String(20), nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False) #renamed from password.
    role = db.Column(user_role_enum, default='customer') #this added role will also help for RAG differentiation.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    #Relationships
    hotels=db.relationship('Hotel', backref='owner', lazy=True) # One user can own multiple hotels
    reviews=db.relationship('Review', backref='author', lazy=True) # One user can write multiple reviews
    
    def set_password(self, password):
        if len(password)<8:
            raise ValueError("Password must be at least 8 characters")
        self.password_hash=generate_password_hash(password) #using werkzeug method.
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Hotel(db.Model):
    __tablename__ = 'hotels'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)#FK linking hotel to its owner.
    name = db.Column(db.String(100), nullable=False, index=True)
    location = db.Column(db.String(100), nullable=False, index=True)
    latitude = db.Column(db.Numeric(10, 8))
    longitude = db.Column(db.Numeric(11, 8))
    price = db.Column(db.Numeric(10,2), nullable=False)
    description = db.Column(db.Text)
    check_in_time = db.Column(db.Time)  # Check-in time for guests
    check_out_time = db.Column(db.Time)  # Check-out time for guests
    #Relationships
    faqs = db.relationship('FAQ', backref='hotel', lazy=True)  # A hotel can have multiple FAQs
    reviews = db.relationship('Review', backref='hotel', lazy=True)  # A hotel can have multiple reviews

class FAQ(db.Model):
    __tablename__ = 'faqs'
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False) #Links the FAQ to a specific hotel.
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.LargeBinary)#store vector embedding for RAG search.

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False) # review content provided by the user.
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) #links review to the user.
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False) #links review to the hotel being reviewed
    embedding = db.Column(db.LargeBinary)#store vector embedding for RAG.
    sentiment= db.Column(db.String(20)) # field to store sentiment analysis result(positive, negative, neutral)
    rating = db.Column(db.Numeric(2,1)) # Numeric rating by user.
    created_at = db.Column(db.DateTime, default=datetime.utcnow) #timestamp when the review was created