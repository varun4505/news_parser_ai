import sys
import os

# Add the parent directory to sys.path to allow importing from app.py
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set up NLTK data directory
os.environ['NLTK_DATA'] = '/tmp/nltk_data'

# Run NLTK setup
try:
    from api.nltk_setup import *
except Exception as e:
    print(f"NLTK setup error: {e}")

from app import app

# This is the entry point for Vercel's serverless function
handler = app
