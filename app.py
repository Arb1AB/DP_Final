from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, login_required, logout_user
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # We'll improve this later

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Login page route
@app.route('/')
@app.route('/login')
def login():
    return render_template('login.html')

# Dashboard route (protected)
@app.route('/dashboard')
@login_required
def dashboard():
    return "<h1>Welcome to Dashboard!</h1><p>You are logged in!</p><a href='/logout'>Logout</a>"

# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# User loader function (required by Flask-Login)
@login_manager.user_loader
def load_user(user_id):
    # We'll implement this properly later
    return None

# Run the app
if __name__ == '__main__':
    app.run(debug=True)