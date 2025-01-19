from flask import Blueprint, redirect, url_for, session, request, render_template, flash
from flask_login import login_user, logout_user, login_required, current_user
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.oauth2 import id_token
from google.auth.transport import requests
from ..config import Config
from ..models.user import User
from ..extensions import db
import os

auth = Blueprint('auth', __name__)

# Force SSL to be disabled for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

@auth.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('auth.timeframe'))
    return redirect(url_for('auth.login'))

@auth.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.timeframe'))
    return render_template('login.html')

@auth.route('/google-auth')
def google_auth():
    try:
        callback_url = url_for('auth.oauth2callback', _external=True, _scheme='http')
        
        flow = Flow.from_client_secrets_file(
            Config.CLIENT_SECRETS_FILE,
            scopes=Config.SCOPES,
            redirect_uri=callback_url
        )
        
        # Specify all the scopes we need
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            scopes=Config.SCOPES
        )
        
        session['state'] = state
        return redirect(authorization_url)
    except Exception as e:
        print(f"Login error: {str(e)}")
        flash("Error connecting to Google. Please try again.", "error")
        return redirect(url_for('auth.login'))

@auth.route('/oauth2callback')
def oauth2callback():
    try:
        callback_url = url_for('auth.oauth2callback', _external=True, _scheme='http')
        
        flow = Flow.from_client_secrets_file(
            Config.CLIENT_SECRETS_FILE,
            scopes=Config.SCOPES,
            state=session['state'],
            redirect_uri=callback_url
        )
        
        # Ensure we have the full URL with scheme
        authorization_response = request.url
        if not authorization_response.startswith('http'):
            authorization_response = 'http://' + request.host + request.full_path
        
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        
        # Get user info from Google
        try:
            id_info = id_token.verify_oauth2_token(
                credentials.id_token, 
                requests.Request(), 
                credentials.client_id
            )
            email = id_info['email']
        except Exception as e:
            print(f"Error getting user info: {str(e)}")
            # Fallback to using credentials
            email = credentials.id_token.get('email')
        
        if not email:
            raise ValueError("No email found in Google response")
            
        # Find or create user
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email)
            db.session.add(user)
            db.session.commit()
        
        login_user(user)
        
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        
        flash("Successfully connected to Google!", "success")
        return redirect(url_for('auth.timeframe'))
    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        flash("Error connecting to Google. Please try again.", "error")
        return redirect(url_for('auth.login'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))

@auth.route('/timeframe')
@login_required
def timeframe():
    if 'credentials' not in session:
        return redirect(url_for('auth.google_auth'))
    return render_template('timeframe.html', config=Config) 