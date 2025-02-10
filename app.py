#import the necessary moduloes for web routing, form handling, database hyandling, and secure password handling
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import secrets
from rag_handler import RAGSystem
#Flask app intialization
app=Flask(__name__)
#Configure database settings
app.config['SQLALCHEMY_DATABASE_URI']= os.getenv('DATABASE_URL','mysql+pymysql://root:my%40sql%40data%40000@localhost/travel_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
#Secure secret key handling
secret_key=os.getenv('SECRET_KEY') or secrets.token_urlsafe(32)
app.secret_key = secret_key
#initialize sqlalchemy(database ORM)
db = SQLAlchemy(app)
login_manager=LoginManager(app)
login_manager.login_view='login'
#Initialize RAG system.
rag=RAGSystem(db)
#Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False) #renamed from password.
    role = db.Column(db.String(20), default='customer') #this added role will also help for RAG differentiation.
    #Relationships
    hotels=db.relationship('Hotel', backref='owner', lazy=True)
    reviews=db.relationship('Review', backref='author', lazy=True)
    
    def set_password(self, password):
        if len(password)<8:
            raise ValueError("Password must be at least 8 characters")
        self.password_hash=generate_password_hash(password) #using werkzeug method.
    #def check_password(self, password):
        #return check_password_hash(self.password_hash, password)

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

#Flask login loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#Initialize vector store once.
with app.app_context():
    try:
        rag._load_faqs_into_vectorstore()
        print("Successfully loaded FAQs into ChromaDB")
    except Exception as e:
        print(f"Error initializing vector store:{str(e)}")

#Routes-lets go!
@app.route('/')
def home():
    hotels = Hotel.query.all() 
    return render_template('index.html', hotels=hotels)

@app.route('/query', methods=['POST'])
@login_required
def handle_query():
    question = request.form.get('query')
    try:
        result = rag.query_system(question=question, role=current_user.role)
        return render_template('query_results.html', answer=result['answer'], sources=result['souirces'], query=question)
    except Exception as e:
        flash(f"Error processing query: {str(e)}", 'danger')
        return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        #verify the password
        if user and user.check_password(password):
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method=='POST':
        username=request.form.get('username')
        email=request.form.get('email')
        password=request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists!','danger')
            return redirect(url_for('register'))
        
        new_user=User(username=username, email=email)
        new_user.set_password(password) #use secure hashing
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


#Initialize Database
with app.app_context():
    db.create_all()
#run the app
if __name__ == '__main__':
    app.run(debug=True)
