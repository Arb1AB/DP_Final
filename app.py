from flask import Flask, render_template, redirect, url_for, session, request
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from authlib.integrations.flask_client import OAuth
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

# Initialize OAuth
oauth = OAuth(app)

# Configure Google OAuth
google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID'),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
    authorization_endpoint='https://accounts.google.com/o/oauth2/auth',
    token_endpoint='https://oauth2.googleapis.com/token',
    userinfo_endpoint='https://www.googleapis.com/oauth2/v1/userinfo',
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Simple User class
class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name

# Store users in memory (in production, use a database)
users = {}

# User loader function
@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

# Login page route
@app.route('/')
@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard_courses'))
    return render_template('login.html')

# Google OAuth login
@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

# Google OAuth callback
@app.route('/callback')
def google_callback():
    token = google.authorize_access_token()
    
    # Get user info from Google
    resp = google.get('https://www.googleapis.com/oauth2/v1/userinfo', token=token)
    user_info = resp.json()
    
    if user_info:
        user_id = user_info['id']
        email = user_info['email']
        name = user_info['name']
        
        # Create or get user
        user = User(user_id, email, name)
        users[user_id] = user
        
        # Log in user
        login_user(user)
        return redirect(url_for('dashboard_courses'))
    
    return redirect(url_for('login'))

# Redirect /dashboard to courses by default
@app.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('dashboard_courses'))

# Dashboard - courses view
@app.route('/dashboard/courses')
@login_required
def dashboard_courses():
    # Optionally load courses data here
    return render_template('dashboard.html', user=current_user, section='courses')

# Dashboard - presence view
@app.route('/dashboard/presence')
@login_required
def dashboard_presence():
    # Optionally load presence/attendance data here
    return render_template('dashboard.html', user=current_user, section='presence')

# New route: Subject attendance page
@app.route('/subject_attendance')
@login_required
def subject_attendance():
    subject = request.args.get('subject')
    if not subject:
        return "Subject not specified", 400

    # Dummy attendance data for demo purposes
    # In production, replace with DB query filtered by user and subject
    attendance_data = [
        {'date': '2025-01-20', 'status': 'Present'},
        {'date': '2025-01-22', 'status': 'Absent'},
        {'date': '2025-01-25', 'status': 'Present'},
    ]

    return render_template('subject_attendance.html', subject=subject, attendance=attendance_data, user=current_user)

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Run the app
if __name__ == '__main__':
    app.run(debug=True)
