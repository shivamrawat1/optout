from datetime import datetime, timedelta
import base64
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse

class GmailService:
    def __init__(self, service):
        self.service = service
        self.unsubscribe_cache = {}
        self.sender_cache = set()  # Add this to track unique senders

    def find_unsubscribe_links(self, timeframe):
        try:
            # Convert timeframe to days
            days = int(timeframe) if timeframe != 'all' else 36500  # ~100 years for 'all'
            
            # Calculate the date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Format dates for Gmail query
            after_date = start_date.strftime('%Y/%m/%d')
            before_date = end_date.strftime('%Y/%m/%d')
            
            # Build Gmail query
            query = f'after:{after_date} before:{before_date}'
            
            # Get messages within the timeframe
            results = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=500  # Adjust this number based on your needs
            ).execute()

            messages = results.get('messages', [])
            unsubscribe_links = []

            for message in messages:
                msg_id = message['id']
                if msg_id in self.unsubscribe_cache:
                    continue

                msg = self.service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='full'
                ).execute()

                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
                from_header = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown Sender')
                
                # Clean up the from address and extract email
                from_match = re.match(r'"?([^"<]+)"?\s*(?:<([^>]+)>)?', from_header)
                if from_match:
                    sender_name = from_match.group(1).strip()
                    sender_email = from_match.group(2) if from_match.group(2) else sender_name
                else:
                    sender_name = from_header
                    sender_email = from_header

                # Skip if we already have an unsubscribe link for this sender
                if sender_email in self.sender_cache:
                    continue

                # Look for List-Unsubscribe header
                unsubscribe_header = next(
                    (h['value'] for h in headers if h['name'].lower() == 'list-unsubscribe'),
                    None
                )

                unsubscribe_found = False

                if unsubscribe_header:
                    # Extract URL from List-Unsubscribe header
                    url_match = re.search(r'<(https?://[^>]+)>', unsubscribe_header)
                    if url_match:
                        unsubscribe_url = url_match.group(1)
                        domain = urlparse(unsubscribe_url).netloc
                        
                        unsubscribe_links.append({
                            'subject': subject,
                            'sender': sender_name,
                            'sender_email': sender_email,
                            'url': unsubscribe_url,
                            'domain': domain,
                            'source': 'header'
                        })
                        self.unsubscribe_cache[msg_id] = True
                        self.sender_cache.add(sender_email)
                        unsubscribe_found = True

                # If no header found, look in the email body
                if not unsubscribe_found:
                    if 'parts' in msg['payload']:
                        parts = msg['payload']['parts']
                    else:
                        parts = [msg['payload']]

                    for part in parts:
                        if part.get('mimeType') == 'text/html':
                            try:
                                data = base64.urlsafe_b64decode(
                                    part['body']['data'].encode('UTF-8')
                                ).decode('UTF-8')
                                
                                soup = BeautifulSoup(data, 'html.parser')
                                
                                # Look for unsubscribe links in the HTML
                                for link in soup.find_all('a', href=True):
                                    text = link.get_text().lower()
                                    href = link['href']
                                    
                                    if ('unsubscribe' in text or 
                                        'opt out' in text or 
                                        'opt-out' in text or 
                                        'remove me' in text):
                                        
                                        domain = urlparse(href).netloc
                                        unsubscribe_links.append({
                                            'subject': subject,
                                            'sender': sender_name,
                                            'sender_email': sender_email,
                                            'url': href,
                                            'domain': domain,
                                            'source': 'body'
                                        })
                                        self.unsubscribe_cache[msg_id] = True
                                        self.sender_cache.add(sender_email)
                                        break
                            except Exception as e:
                                print(f"Error processing email body: {str(e)}")
                                continue

            # Sort by sender name
            unsubscribe_links.sort(key=lambda x: x['sender'].lower())
            return unsubscribe_links

        except Exception as e:
            print(f"Error finding unsubscribe links: {str(e)}")
            return [] 