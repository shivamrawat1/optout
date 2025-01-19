from flask import Blueprint, redirect, url_for, session, render_template, request, flash
from flask_login import login_required, current_user
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from ..services.gmail_service import GmailService
from ..config import Config

dashboard = Blueprint('dashboard', __name__)

@dashboard.route('/dashboard')
@login_required
def show():
    if 'credentials' not in session:
        flash("Please connect your Google account first.", "warning")
        return redirect(url_for('auth.timeframe'))
    
    try:
        timeframe = request.args.get('timeframe', '30')
        if timeframe not in [t[0] for t in Config.EMAIL_TIMEFRAMES]:
            timeframe = '30'  # Default to 30 days if invalid timeframe
        
        credentials = Credentials(**session['credentials'])
        service = build('gmail', 'v1', credentials=credentials)
        
        gmail_service = GmailService(service)
        unsubscribe_links = gmail_service.find_unsubscribe_links(timeframe)
        
        if not unsubscribe_links:
            flash("No newsletter subscriptions found in this time period.", "info")
        
        return render_template('dashboard.html', 
                            unsubscribe_links=unsubscribe_links,
                            timeframe=timeframe,
                            config=Config)
                            
    except RefreshError:
        session.pop('credentials', None)
        flash("Your Google session has expired. Please reconnect.", "warning")
        return redirect(url_for('auth.google_auth'))
        
    except Exception as e:
        print(f"Dashboard error: {str(e)}")
        flash("Error accessing your emails. Please try again.", "error")
        return redirect(url_for('auth.timeframe')) 