import nltk
import ssl
import os
import sys

# Set up SSL context for NLTK downloads
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# Ensure NLTK_DATA directory exists
nltk_data_dir = os.environ.get('NLTK_DATA', '/tmp/nltk_data')
os.makedirs(nltk_data_dir, exist_ok=True)

print(f"Downloading NLTK data to: {nltk_data_dir}")

# Download required NLTK data packages
try:
    # punkt is needed by newspaper3k for sentence tokenization
    nltk.download('punkt', download_dir=nltk_data_dir, quiet=False)
    
    # Optional: download additional NLTK data that might be useful
    # nltk.download('stopwords', download_dir=nltk_data_dir, quiet=False)
    
    print("NLTK data downloaded successfully!")
except Exception as e:
    print(f"Error downloading NLTK data: {e}", file=sys.stderr)
    sys.exit(1)
