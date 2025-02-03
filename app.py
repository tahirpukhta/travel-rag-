#import the necessary moduloes for web routing, form handling, database hyandling, and secure password handling
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

#Flask app intialization
app=Flask(__name__)
#Configure database settings
app.config['SQLALCHEMY_DATABASE_URI']='mysql+pymysql://root:my%40sql%40data%40000@localhost/travel_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'supersecretkey' #secret key for session management.(replace in production(find some free tier cloud application platform :p)
#initialize sqlalchemy(database ORM)
db = SQLAlchemy(app)

#Database Models
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

class Hotel(db.Model):
    __tablename__ = 'hotels'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)#Links hotel to a user(owner)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Numeric(10,2), nullable=False)
    description = db.Column(db.Text)
    owner = db.relationship('User', backref='hotels')#establishing relationship, one user can own multiple hotels.

class FAQ(db.Model):
    __tablename__ = 'faqs'
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.BLOB)#store vector embedding for RAG.

class Review(db.Model):
    __tablename__ = 'reviews'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.BLOB)#store vector embedding for RAG.

#Routes-lets go!
@app.route('/')
def home():
    hotels = Hotel.query.all() 
    return render_template('index.html', hotels=hotels)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        #verify the password
        if user and check_password_hash(user.password, password):
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

#Initialize Database
with app.app_context():
    db.create_all()
#run the app
if __name__ == '__main__':
    app.run(debug=True)
