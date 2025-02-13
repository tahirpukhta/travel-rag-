#import the necessary moduloes for web routing, form handling, database hyandling, and secure password handling
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import os
import secrets
from rag_handler import RAGSystem
from models import db, User, Hotel, FAQ, Review

#Flask app intialization
app=Flask(__name__)

#Configure database settings
app.config['SQLALCHEMY_DATABASE_URI']= os.getenv('DATABASE_URL','mysql+pymysql://root:my%40sql%40data%40000@localhost/travel_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#Secure secret key handling
secret_key=os.getenv('SECRET_KEY') or secrets.token_urlsafe(32)
app.secret_key = secret_key

#initialize the database with Flask app.
db.init_app(app)

login_manager=LoginManager(app)
login_manager.login_view='login'

#Initialize RAG system with db connection.
rag=RAGSystem(db)

#Flask login loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#Initialize vector store once(Load both FAQs and reviews into ChromaDB)
with app.app_context():
    try:
        rag._load_faqs_into_vectorstore()
        rag._load_reviews_into_vectorstore()
        print("Successfully loaded FAQs and reviews into ChromaDB")
    except Exception as e:
        print(f"Error initializing vector store:{str(e)}")

#Routes-lets go!
@app.route('/')
def home():
    hotels = Hotel.query.all() 
    return render_template('index.html', hotels=hotels)

@app.route('/hotel/<int:hotel_id>')
def hotel_details(hotel_id):
    hotel=Hotel.query.get_or_404(hotel_id)
    reviews=Review.query.filter_by(hotel_id=hotel_id).all()
    return render_template('hotel_details.html', hotel=hotel, reviews=reviews)

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

#Review submission handler
@app.route('/submit_review', methods=['POST'])
@login_required
def submit_review():
    hotel_id=request.form.get('hotel_id')
    content=request.form.get('content')

    new_review=Review(user_id=current_user.id, hotel_id=hotel_id, content=content)
    try:
        db.session.add(new_review)
        db.session.commit()
        rag._load_reviews_into_vectorstore() #update vectorstore with the new review.
        flash('Review submitted successfully!', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
    return redirect(url_for('hotel_details', hotel_id=hotel_id))

#Initialize Database
with app.app_context():
    db.create_all()
#run the app
if __name__ == '__main__':
    app.run(debug=True)
