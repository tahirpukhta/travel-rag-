from flask_sqlalchemy import SQLAlchemy #Enables ORM operations with Flask
from flask_login import UserMixin # helper methods for user authentication
from werkzeug.security import generate_password_hash, check_password_hash # provides functions to hash and check passwords
from sqlalchemy import Enum # allows usage of a generic ENUM type across different databases
from datetime import datetime

#Create an instance of sqlalchemy for interacting with the database.
db=SQLAlchemy()

#Define custom ENUM types for various model fields using the generic Enum
# ENUM for user roles with possible values 'customer' or 'property_owner'
user_role_enum = Enum('customer', 'property_owner', name='user_role_enum')

# ENUM for home types offered by hotels
home_type_enum = Enum('Apartment', 'Villa', 'Hotel Room', name='home_type_enum')

# ENUM for room types available within a hotel
room_type_enum = Enum('Private', 'Shared', 'Entire Place', name='room_type_enum')

# ENUM for booking statuses with possible states 'Pending', 'Confirmed', or 'Cancelled'
booking_status_enum = Enum('Pending', 'Confirmed', 'Cancelled', name='booking_status_enum')

# ENUM for types of places associated with a hotel (e.g., nearby attractions)
place_type_enum = Enum('monument', 'restaurant', 'museum', 'park', name='place_type_enum')

# ENUM for customer preference categories (e.g., food, budget, etc.)
preference_type_enum = Enum('food', 'budget', 'activities', 'amenities', name='preference_type_enum')

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
    bookings = db.relationship('Booking', backref='guest', lazy=True) #one user can have multiple bookings.
    itineraries = db.relationship('Itinerary', backref='creator', lazy=True) #one user can create severral itineraries.
    preferences = db.relationship('CustomerPreference', backref='customer', lazy=True) #one user can have multiple customer preferences.

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
    rooms = db.relationship('Room', backref='hotel', lazy=True) #A hotel can have multiple rooms.
    places = db.relationship('Place', backref='hotel', lazy=True) #A hotel may be associated with multiple places of interest.
    amenities = db.relationship('HotelAmenity', backref='hotel', lazy=True) #A hotel can offer various amenities.

class HotelAmenity(db.Model):
    __tablename__= 'hotel_amenities'
    id = db.Column(db.integer, primary_key=True) # Unique identifier for each amenity
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False)  # Links the amenity to a specific hotel
    amenity = db.Column(db.String(50), nullable=False)  # Name of the amenity (e.g., pool, gym)

class Room(db.Model):
    __tablename__='rooms'
    id = db.Column(db.Integer, primary_key=True)
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'), nullable=False) #FK linking the room to its hotel
    price = db.Column(db.Numeric(10,2), nullable=False) #price for booking the room
    home_type = db.Column(home_type_enum, nullable=False) #type of home
    bed_count = db.Column(db.Integer, nullable=False)
    summary=db.Column(db.Text) #description of the room.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Timestamp when the room was added
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Timestamp updated on each modification

class RoomAmenity(db.Model):
    __tablename__='room_amenities'
    id = db.Column(db.Integer, primary_key=True) #unique id for each room amenity.
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False) #Links the amenity to a specific room
    amenity_name = db.Column(db.String(100), nullable=False)

class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True) #uniqe idnetifier for each booking
    guest_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) #links the booking to the guest
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)  # Total price for the booking period
    status = db.Column(booking_status_enum, default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class BookingDetail(db.Model):
    __tablename__='booking_details'
    id = db.Column(db.Integer, primary_key=True) #unique identifier for each booking detail record
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False) #links detail top a specific booking.
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False) # links detail to a specific room
    quantity = db.Column(db.Integer, nullable=False, default=1) #number of rooms booked in this detaail.
    price_per_room = db.Column(db.Numeric(10,2), nullable=False)
    subtotal = db.Column(db.Numeric(10,2), nullable=False) #subtotal cost for this booking detail.

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow) #timestamp when the review was created.

class Itinerary(db.Model):
    __tablename__ = 'itineraries'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Place(db.Model):
    __tablename__='places' 
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    type = db.Column(place_type_enum)
    location = db.Column(db.String(150))
    latitude = db.Column(db.Numeric(10,8))
    longitude = db.Column(db.Numeric(11,8))
    description = db.Column(db.Text) #detailed description of the place.
    hotel_id = db.Column(db.Integer, db.ForeignKey('hotels.id'))
    api_source = db.Column(db.String(50)) #source api for the place data
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CustomerPreference(db.Model):
    __tablename__ = 'customer_preferences'
    id = db.Column(db.Integer, primary_key=True) # Unique identifier for each preference entry
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    preference_type = db.Column(preference_type_enum)
    preference_value = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.SmallInteger, default=1)

class APICache(db.Model):
    __tablename__='api_cache'
    id = db.Column(db.Integer, primary_key=True) #unique identifier for each cache record.
    api_name = db.Column(db.String(50), nullable=False) #name of the API whose response is being cached.
    parameters = db.Column(db.Text, nullable=False) #parameters used in the API request(stored as text)
    response = db.Column(db.JSON, nullable=False) #the JSON response from the API stored for caching
    expires_at = db.Column(db.DateTime, nullable=False)  # Expiration timestamp for the cached API response
    created_at = db.Column(db.DateTime, default=datetime.utcnow) #Timestamp when the cache record was created
















