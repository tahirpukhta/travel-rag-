#import the necessary moduloes for web routing, form handling, database hyandling, and secure password handling
from flask import Flask, render_template, redirect, url_for, request, flash
#from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate 
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
import os
import secrets
from rag_handler import RAGSystem, analyze_sentiment, detect_emotion
from models import db # Import only the db instance first
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta, date
from flask_wtf.csrf import CSRFProtect
from flask_talisman import Talisman 
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
#initialize Migrate with our app and db.
migrate = Migrate(app,db)
# Now import the rest of our models
from models import User, Hotel, FAQ, Review, HotelAmenity, Room, RoomAmenity, Booking, BookingDetail, Itinerary, Place, CustomerPreference, APICache

login_manager=LoginManager(app)
login_manager.login_view='login'

#rate limiting setup
limiter=Limiter(app=app,
                key_func=get_remote_address,
                default_limits=["200 per day","50 per hour"])

#add csrf protection
csrf = CSRFProtect(app)

# add http security headers
Talisman(app, content_security_policy={
    'default-src': "'self'",
    'style-src': ["'self'", "cdn.jsdelivr.net"],
    'script-src': ["'self'", "cdn.jsdelivr.net"]})

#Initialize RAG system within app context
with app.app_context():
    rag=RAGSystem(db)

#Flask login loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#Routes-lets go!
@app.route('/')
def home():
    hotels = Hotel.query.all() 
    return render_template('index.html', hotels=hotels)

@app.route('/hotel/<int:hotel_id>')
def hotel_details(hotel_id):
    hotel=Hotel.query.get_or_404(hotel_id)
    reviews=Review.query.filter_by(hotel_id=hotel_id).order_by(Review.created_at.desc()).all()
    return render_template('hotel_details.html', hotel=hotel, reviews=reviews)

@app.route('/query', methods=['POST'])
@login_required
@limiter.limit("10/minute")
def handle_query():
    question = request.form.get('query')
    if not question or len(question.strip())<5:
        flash("Please enter a meaningful question of at least 5 characters","warning")
        return redirect(request.referrer or url_for('home')) #redirect back to where the query form was or home.
    try:
        result = rag.query_system(question=question.strip(), role=current_user.role)
        return render_template('query_results.html', answer=result.get('answer','No answer generated'), sources=result.get('sources',[]), query=question)
    except Exception as e:
        flash(f"Error processing query: {str(e)}", 'danger')
        app.logger.error(f"Query processing error for user{current_user.id}:{e}", exc_info=True) #log the error for debugging purposes.
        return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10/minute") #limit login attempts
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home')) #prevent already logged in users from accessing login page.
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        #verify the password
        if user and user.check_password(password):
            login_user(user, remember=request.form.get('remember')) #added remember me functionality.
            user.last_login=db.func.now() #update last login time.
            db.session.commit()
            flash('Login successful!', 'success')
            next_page=request.args.get('next') #for redirecting after login
            return redirect(next_page or url_for('home'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5/hour") #limit registration attempts 
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home')) #prevent logged in users from registering
    if request.method=='POST':
        username=request.form.get('username').strip()
        email=request.form.get('email').strip().lower() #normalize email
        password=request.form.get('password')
        contact_number=request.form.get('contact_number','').strip() #optional field
        
        #add more robust validation
        if not username or len(username)<3:
            flash('Username must be atleast 3 characters long.','warning')
            return redirect(url_for('register'))
        if not email or '@' not in email or '.' not in email.split('@')[-1]:
            flash('Please enter a valid email address.', 'warning')
            return redirect(url_for('register'))
        if not password or len(password)<8:
            flash('Password must be at least 8 characters long.','warning')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email address already registered. Please login','danger')
            return redirect(url_for('login'))
        if User.query.filter_by(username=username).first():
            flash('Username already taken. Please choose another.', 'warning')
            return redirect(url_for('register'))
        try:
            new_user=User(username=username, email=email, contact_number=contact_number)
            new_user.set_password(password) #use secure hashing
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed due to an error:{str(e)}','danger')
            app.logger.error(f"Registration error:{e}, exc_info=True")
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.','info')
    return redirect(url_for('home'))

#Review submission handler
@app.route('/submit_review', methods=['POST'])
@login_required
@limiter.limit("2/minute") #prevent spam
def submit_review():
    hotel_id=request.form.get('hotel_id')
    content=request.form.get('content', '').strip() #sanitize input by stripping whitespace.
    rating_str = request.form.get('rating') #get rating from form.

    #Role check: only customers may review
    if current_user.role != 'customer':
        flash('Only customers can submit reviews','danger')
        return redirect(request.referrer or url_for('home'))
    
    # hotel id and existence validation
    if not hotel_id:
        flash('Hotel ID is missing.','danger')
        return redirect(url_for('home'))
    
    hotel = Hotel.query.get(hotel_id)
    if not hotel:
        flash('Hotel not found.', 'danger')
        return redirect(url_for('home'))

    #prevent owners reviewing their own propeety
    if hotel.user_id == current_user.id:
        flash('You can not review your own propeerty,','warning')
        return redirect(url_for('hotel_details', hotel_id=hotel_id))
     
    #completed stay check
    today_date = date.today()
    booking = Booking.query.filter_by(
        guest_id=current_user.id, 
        hotel_id=hotel_id, status='Confirmed'
        ).filter(Booking.end_date<=today_date).first()
    
    if not booking:
        flash('You must cmplete a stay before reviewing.', 'warning')
        return redirect(url_for('hotel_details', hotel_id=hotel_id))
    
    #IP rate-limit check
    ip = request.remote_addr
    recent_count = Review.query.filter_by(hotel_id=hotel_id).filter(
        Review.created_at>=datetime.now()-timedelta(hours=1),
        Review.ip_address == ip
    ).count()
    if recent_count>3:
        flash('Too many reviews from this IP recently.', 'warning')
        return redirect(url_for('hotel_details', hotel_id=hotel_id))
    
    #content length validation
    if not content or len(content)<10:
        flash('Review must be at least 10 characrters long,', 'warning')
        return redirect(url_for('hotel_details', hotel_id=hotel_id))
    
    #prevent duplicate reviews from same user
    existing_review = Review.query.filter_by(user_id=current_user.id, hotel_id=hotel_id).first()
    if existing_review:
        flash('You have already reviewed this hotel.', 'info')
        return redirect(url_for('hotel_details', hotel_id=hotel_id))
    
    #process rating
    rating_value = None #feault to none(null in db) if no rating selected or invalid
    if rating_str:
        try:
            temp_rating = float(rating_str)
            if 1.0 <= temp_rating <= 5.0:
                rating_value = temp_rating
            else:
                app.logger.warning(f"Rating value out of range: {rating_str} for hotel{hotel_id}")
        except ValueError:
            app.logger.error(f"Invalid rating format received: {rating_str} for hotel{hotel_id}", exc_info=True)

    
    #Analyze sentiment and emotion
    sentiment = analyze_sentiment(content)
    emotion = detect_emotion(content)
    
    
    # create and save the new review
    new_review=Review(user_id=current_user.id, hotel_id=hotel_id, content=content, sentiment=sentiment, emotion=emotion, rating=rating_value, ip_address=request.remote_addr)
    try:
        db.session.add(new_review)
        db.session.commit()
        # incremental update for the new review
        rag.add_review_to_vectorstore(new_review) #update vectorstore with the new review.
        flash('Review submitted successfully! Thank you for your feedback', 'success')
    except Exception as e:
        db.session.rollback() #rollback in case of an error.
        flash(f'Error submitting review: {str(e)}', 'danger')
        app.logger.error(f"Review submission error for hotel{hotel_id} by user {current_user.id}: {e}", exc_info=True)
    return redirect(url_for('hotel_details', hotel_id=hotel_id))

#FAQ submission handler using incremental update method
@app.route('/submit_faq', methods=['POST'])
@login_required
def submit_faq():
    hotel_id=request.form.get('hotel_id')
    question = request.form.get('question', '').strip()
    answer=request.form.get('answer','').strip()

    #basic field validation
    if not hotel_id or not question or not answer:
        flash('All fields(Hotel ID, Question, Answer) are required.', 'warning')
        return redirect(request.referrer or url_for('home')) #redirect back or home.
    # hotel existence check
    hotel =  Hotel.query.get(hotel_id)
    if not hotel:
        flash('Hotel not found.', 'danger')
        return redirect(url_for('home'))
    
    #Permission check: onky the hotel owners may add FAQs
    if hotel.user_id != current_user.id and current_user.role != 'property_owner':
        flash('You do not have permission toadd FAQs for this hotel.', 'danger')
        return redirect(url_for('hotel_details', hotel_id=hotel_id))

    #content lemgth validation
    if len(question)<10 and len(answer)<10:
        flash('Question and Answer must be at least 10 characters long','warning')
        return redirect(url_for('hotel_details', hotel_id=hotel_id))
    
    #create and persist the new FAQ
    new_faq=FAQ(hotel_id=hotel_id, question=question, answer=answer)
    try:
        db.session.add(new_faq)
        db.session.commit()
        # incremental update for the new FAQ in the vector store.
        rag.add_faq_to_vectorstore(new_faq) #update vectorstore with the new faq.
        flash('FAQ submitted successfully!', 'success')
    except Exception as e:
        db .session.rollback()
        flash(f'Error submitting FAQ: {str(e)}', 'danger')
        app.logger.error(f"FAQ submission error for hotel{hotel_id} by user{current_user.id}:{e}", exc_info=True)
    return redirect(url_for('hotel_details', hotel_id=hotel_id))

#Initialize Database
#with app.app_context():
    #db.create_all()
#run the app
if __name__ == '__main__':
    app.run(debug=True)
