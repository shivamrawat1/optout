import os
from dotenv import load_dotenv
from app import create_app

# Load environment variables from .env file in development
if os.environ.get('FLASK_ENV') != 'production':
    load_dotenv()

app = create_app()

if __name__ == '__main__':
    app.run() 