from flask import Flask, render_template, redirect, url_for, session, request
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from bs4 import BeautifulSoup
import base64
import os
import re
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = 'hahbusbjdsb'  # Change this to a secure secret key

# OAuth 2.0 client configuration
CLIENT_SECRETS_FILE = "client_secrets.json"
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]

# Store unsubscribe links to avoid duplicates
unsubscribe_cache = {}

@app.route('/')
def index():
    if 'credentials' not in session:
        return render_template('login.html')
    return redirect(url_for('dashboard'))

@app.route('/login')
def login():
    try:
        # Get the full URL for the callback
        callback_url = url_for('oauth2callback', _external=True, _scheme='http')
        
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            redirect_uri=callback_url
        )
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        session['state'] = state
        return redirect(authorization_url)
    except Exception as e:
        print(f"Login error: {str(e)}")
        return f"Error during login: {str(e)}", 500

@app.route('/oauth2callback')
def oauth2callback():
    try:
        callback_url = url_for('oauth2callback', _external=True, _scheme='http')
        
        state = session['state']
        flow = Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE,
            scopes=SCOPES,
            state=state,
            redirect_uri=callback_url
        )
        
        authorization_response = request.url
        if not request.is_secure and 'http://' not in authorization_response:
            authorization_response = 'http://' + authorization_response.split('://', 1)[1]
        
        flow.fetch_token(authorization_response=authorization_response)
        credentials = flow.credentials
        session['credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
        return redirect(url_for('dashboard'))
    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        print(f"Authorization response: {authorization_response}")  # Debug info
        return f"Error during OAuth callback: {str(e)}", 500

@app.route('/dashboard')
def dashboard():
    if 'credentials' not in session:
        return redirect(url_for('login'))
    
    credentials = Credentials(**session['credentials'])
    service = build('gmail', 'v1', credentials=credentials)
    
    # Clear the cache for new requests
    unsubscribe_cache.clear()
    
    # Get emails with unsubscribe links
    unsubscribe_links = find_unsubscribe_links(service)
    
    return render_template('dashboard.html', unsubscribe_links=unsubscribe_links)

def find_unsubscribe_links(service):
    unsubscribe_links = []
    
    # Search for emails with potential unsubscribe links
    results = service.users().messages().list(
        userId='me',
        q='unsubscribe',
        maxResults=50
    ).execute()
    
    messages = results.get('messages', [])
    
    for message in messages:
        msg = service.users().messages().get(
            userId='me',
            id=message['id'],
            format='full'
        ).execute()
        
        # Get sender information
        headers = msg['payload']['headers']
        from_header = next(h for h in headers if h['name'].lower() == 'from')
        sender = from_header['value']
        
        # Check for List-Unsubscribe header
        unsubscribe_header = next(
            (h for h in headers if h['name'].lower() == 'list-unsubscribe'),
            None
        )
        
        if unsubscribe_header:
            link = extract_url_from_header(unsubscribe_header['value'])
            if link and sender not in unsubscribe_cache:
                unsubscribe_cache[sender] = link
                unsubscribe_links.append({
                    'sender': sender,
                    'link': link,
                    'type': 'header'
                })
                continue
        
        # Check email body for unsubscribe links
        if 'parts' in msg['payload']:
            for part in msg['payload']['parts']:
                if part['mimeType'] == 'text/html':
                    body = base64.urlsafe_b64decode(
                        part['body']['data'].encode('ASCII')
                    ).decode('utf-8')
                    link = extract_url_from_body(body)
                    if link and sender not in unsubscribe_cache:
                        unsubscribe_cache[sender] = link
                        unsubscribe_links.append({
                            'sender': sender,
                            'link': link,
                            'type': 'body'
                        })
                    break
    
    return unsubscribe_links

def extract_url_from_header(header_value):
    # Extract URL from List-Unsubscribe header
    urls = re.findall(r'<(https?://[^>]+)>', header_value)
    for url in urls:
        if 'mailto:' not in url.lower():
            return url
    return None

def extract_url_from_body(body):
    soup = BeautifulSoup(body, 'html.parser')
    
    # Look for links containing "unsubscribe"
    for link in soup.find_all('a', href=True):
        if 'unsubscribe' in link.text.lower() or 'unsubscribe' in link['href'].lower():
            return link['href']
    return None

if __name__ == '__main__':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Make sure this line is present
    app.run(debug=True) 