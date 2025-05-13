from flask import Flask, jsonify, request
from flask_cors import CORS
from gnews import GNews
import newspaper
from newspaper import Article
import os
from dotenv import load_dotenv
import json
import re
from datetime import datetime
import time
import traceback
from functools import lru_cache  # Import LRU Cache for caching results
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Initialize rate limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per day", "30 per hour"],
    storage_uri="memory://",
)
# Configure CORS with specific settings
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:3000", "https://*.vercel.app"],  # Local and Vercel domains
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Set debug mode based on environment
app.config['DEBUG'] = os.environ.get('FLASK_ENV') == 'development'

# Simple in-memory cache for news results
news_cache = {}
cache_expiry = 300  # Cache results for 5 minutes (300 seconds)

# Cache cleanup function
def cleanup_cache():
    current_time = time.time()
    keys_to_remove = []
    for key, (timestamp, _) in news_cache.items():
        if current_time - timestamp > cache_expiry:
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del news_cache[key]

def extract_journalist(title, content=None):
    """Attempt to extract journalist name if it exists in the title or content"""
    # Common words that indicate what follows is likely a journalist name
    journalist_indicators = [
        r'by\s+',
        r'written\s+by\s+', 
        r'reported\s+by\s+',
        r'author[:\s]+',
        r'correspondent[:\s]+',
        r'staff\s+writer[:\s]+',
        r'byline[:\s]+',
        r'\|\s+'  # Common separator in some news sites
    ]
    
    # More precise patterns that must include proper structure of a name
    name_patterns = [
        # Matches common name formats with proper capitalization
        r'([A-Z][a-z]+(?:\s+[A-Z]\.?\s+)?[A-Z][a-z]+(?:-[A-Z][a-z]+)?)',  # First (Middle) Last(-Last)
        r'([A-Z][a-z]+\s+[a-z]+\s+[A-Z][a-z]+)',  # First van/de/la Last
    ]
    
    # Words that, if found in the match, likely indicate it's not a person's name
    false_positives = [
        'news', 'times', 'post', 'reuters', 'associated', 'press', 'agency',
        'today', 'yesterday', 'tomorrow', 'google', 'facebook', 'twitter',
        'breaking', 'exclusive', 'update', 'latest', 'report', 'copyright'
    ]
    
    # First try more structured extraction from beginning/end of content
    potential_authors = []
    
    # Look at title first
    for indicator in journalist_indicators:
        for pattern in name_patterns:
            # Look for indicator followed by name pattern
            combined_pattern = f"{indicator}{pattern}"
            matches = re.finditer(combined_pattern, title, re.IGNORECASE)
            for match in matches:
                potential_name = match.group(1)
                # Validate the name
                if _is_valid_name(potential_name, false_positives):
                    print(f"Found author in title: {potential_name}")
                    return potential_name
    
    # If no match in title and content is provided, check content
    if not content:
        return None
        
    # Look in the first 500 characters (bylines often at the beginning)
    content_start = content[:500]
    
    for indicator in journalist_indicators:
        for pattern in name_patterns:
            combined_pattern = f"{indicator}{pattern}"
            matches = re.finditer(combined_pattern, content_start, re.IGNORECASE)
            for match in matches:
                potential_name = match.group(1)
                if _is_valid_name(potential_name, false_positives):
                    print(f"Found author at beginning of content: {potential_name}")
                    return potential_name
    
    # Look in the last 500 characters (bylines often at the end)
    if len(content) > 500:
        content_end = content[-500:]
        
        for indicator in journalist_indicators:
            for pattern in name_patterns:
                combined_pattern = f"{indicator}{pattern}"
                matches = re.finditer(combined_pattern, content_end, re.IGNORECASE)
                for match in matches:
                    potential_name = match.group(1)
                    if _is_valid_name(potential_name, false_positives):
                        print(f"Found author at end of content: {potential_name}")
                        return potential_name
    
    return None

def _is_valid_name(name, false_positives):
    """Validate if a string really looks like a person's name"""
    # Check if it's too long to be a name
    if len(name) > 40:
        return False
        
    # Check for false positives
    name_lower = name.lower()
    for fp in false_positives:
        if fp in name_lower:
            return False
            
    # Check if it has reasonable word count for a name (1-4 words)
    words = name.split()
    if len(words) > 4 or len(words) < 1:
        return False
        
    # Check that all words start with uppercase (proper names)
    if not all(word[0].isupper() for word in words if len(word) > 1):
        return False
        
    return True

def fetch_article_details(url):
    """Fetch detailed article information using newspaper3k"""
    if not url or url == '#':
        return {
            'text': '',
            'top_image': '',
            'authors': [],
            'publish_date': None,
            'keywords': []
        }
    
    try:
        # Configure newspaper
        article = Article(url)
        article.download()
        article.parse()
        
        # Try to extract NLP features if possible
        try:
            article.nlp()
        except Exception as e:
            print(f"NLP extraction error: {e}")
            
        # Build result dict with extracted data
        result = {
            'text': article.text[:1000] if article.text else '',  # Limit text length
            'top_image': article.top_image,
            'authors': article.authors,
            'publish_date': article.publish_date,
            'keywords': article.keywords if hasattr(article, 'keywords') else []
        }
        
        return result
        
    except Exception as e:
        print(f"Error fetching article details: {e}")
        traceback.print_exc()
        return {
            'text': '',
            'top_image': '',
            'authors': [],
            'publish_date': None,
            'keywords': []
        }

@app.route('/news/<query>')
@limiter.limit("5 per minute")  # More restrictive rate limit for the resource-intensive endpoint
def get_news(query):
    try:
        # Get number of articles from query parameters (default to 30)
        max_articles = request.args.get('articles', default=30, type=int)
        # Limit to reasonable range
        max_articles = min(max(1, max_articles), 30)  # Between 1 and 30 articles
        
        # Get if detailed mode is enabled (uses newspaper3k to fetch full article content)
        detailed_mode = request.args.get('detailed', default=True, type=lambda v: v.lower() == 'true')
        
        # Get language, country and time period from query parameters
        language = request.args.get('language', default='en', type=str)
        country = request.args.get('country', default='IN', type=str)
        period = request.args.get('period', default='1d', type=str)
        
        # Check cache first
        cache_key = f"{query}_{language}_{country}_{period}_{max_articles}_{detailed_mode}"
        
        # Clean expired cache entries
        cleanup_cache()
        
        # Check if we have a cached result
        if cache_key in news_cache:
            timestamp, cached_results = news_cache[cache_key]
            if time.time() - timestamp <= cache_expiry:
                print(f"Returning cached results for: {query}")
                return jsonify(cached_results)
        
        print(f"Searching with filters - Language: {language}, Country: {country}, Period: {period}")
        
        # Initialize GNews
        gnews_client = GNews(
            language=language,
            country=country,
            max_results=max_articles,
            period=period  # Time period for news
        )
        
        try:
            # Search for the query
            print(f"Searching for: {query}")
            news_results = gnews_client.get_news(query)
            print(f"Total articles fetched: {len(news_results)}")
            
        except Exception as e:
            print(f"Error fetching news: {e}")
            traceback.print_exc()
            raise

        # Process the results
        if not news_results:
            print(f"No articles found for query: {query}")
            return jsonify({
                "error": "No articles found",
                "message": "Try a different search term.",
                "articles": []
            })
            
        # Print summary of results
        print(f"\nTotal articles found: {len(news_results)}")
        print("===================================")
        
        # Print sample of first article
        if news_results:
            first = news_results[0]
            print("Sample article:")
            print('Title:', first.get('title', 'No title'))
            print('Link:', first.get('url', 'No link'))
            print('Publisher:', first.get('publisher', {}).get('title', 'Unknown'))
            print('Published At:', first.get('published date', 'No date'))
            print('Description:', first.get('description', 'No description'))
            print("===================================")
            
        articles = []
        
        for item in news_results:
            # Extract basic data from GNews
            title = item.get('title', 'No title')
            description = item.get('description', 'No description available')
            link = item.get('url', '#')
            
            print(f"\nProcessing article: {title}")
            
            # Extract publication from publisher info
            publisher_info = item.get('publisher', {})
            publication = publisher_info.get('title', 'Unknown Source')
            
            # Parse date if available
            date_str = item.get('published date', '')
            if date_str:
                try:
                    date = date_str
                except Exception as e:
                    print(f"Date parsing error: {e}")
                    date = date_str
            else:
                date = "Unknown"
            
            article_data = {
                'title': title,
                'description': description,
                'date': date,
                'link': link,
                'publication': publication,
                'journalist': "Not specified"  # Will update if we fetch detailed info
            }
              # If detailed mode is enabled, fetch additional info using newspaper3k
            if detailed_mode and link and link != '#':
                try:
                    print(f"Fetching detailed information for: {link}")
                    start_time = time.time()
                    article_details = fetch_article_details(link)
                    elapsed_time = time.time() - start_time
                    print(f"Article details fetched in {elapsed_time:.2f} seconds")
                    
                    # Update with detailed information
                    if article_details['text']:
                        # Use the fuller article text from newspaper3k if available
                        article_data['full_text'] = article_details['text']
                        
                        # Use article text as description if current one is short or improve longer descriptions
                        if len(description) < 100 and article_details['text']:
                            article_data['description'] = article_details['text'][:400] + "..."
                        elif len(description) < 250 and article_details['text']:
                            # Append a bit more content to make description richer
                            article_data['description'] = description + "\n\n" + article_details['text'][:200] + "..."
                    
                    # Update with image
                    if article_details['top_image']:
                        article_data['image_url'] = article_details['top_image']
                    
                    # Update with authors from newspaper3k
                    if article_details['authors']:
                        article_data['journalist'] = ", ".join(article_details['authors'][:3])  # Limit to first 3 authors
                        print(f"Authors found via newspaper3k: {article_data['journalist']}")
                    
                    # Update with published date if available and original is Unknown
                    if article_details['publish_date'] and date == "Unknown":
                        try:
                            article_data['date'] = article_details['publish_date'].strftime('%Y-%m-%d')
                        except:
                            pass
                    
                    # Add keywords if available
                    if article_details['keywords']:
                        article_data['keywords'] = article_details['keywords'][:10]  # Limit to top 10 keywords
                
                except Exception as e:
                    print(f"Error processing detailed article info: {e}")
                    traceback.print_exc()
            
            # Extract journalist name if possible and not already set from newspaper3k
            if article_data['journalist'] == "Not specified":                # Try to extract from title first, then from content if available
                full_text = article_data.get('full_text', '')
                journalist = extract_journalist(title, full_text)
                if journalist:
                    article_data['journalist'] = journalist
            
            articles.append(article_data)
        
        if not articles:
            return jsonify({
                "error": "No articles found",
                "message": "Please try with a different search term.",
                "articles": []
            })
        
        # Store results in cache before returning
        news_cache[cache_key] = (time.time(), articles)
        
        return jsonify(articles)
        
    except Exception as e:
        print(f"Error in get_news: {str(e)}")
        error_message = "An error occurred while fetching news articles."
        if "GoogleNews" in str(e):
            error_message = "Error fetching news from source. Please try again."
        return jsonify({
            "error": error_message,
            "details": str(e) if app.debug else None
        }), 500

@app.route('/')
def index():
    """Root endpoint that provides API information"""
    return jsonify({
        "name": "News Scraper API",
        "version": "1.0.0",
        "available_endpoints": [
            {"path": "/", "method": "GET", "description": "This information page"},
            {
                "path": "/news/<query>", 
                "method": "GET", 
                "description": "Get news articles based on search query",                "parameters": {
                    "articles": "Optional: Number of articles to fetch (default: 30, max: 30)",
                    "language": "Optional: Language code (default: 'en')",
                    "country": "Optional: Country code (default: 'IN')",
                    "period": "Optional: Time period for news (default: '1d')"
                },
                "example": "/news/technology?language=en&country=US&period=7d"
            },
            {"path": "/options", "method": "GET", "description": "Get available options for languages, countries and time periods"},
            {"path": "/health", "method": "GET", "description": "Health check endpoint"}
        ],
        "usage": "Make GET requests to /news/your_search_query to retrieve news articles"
    })

@app.route('/health')
def health_check():
    return jsonify({"status": "OK"})

@app.route('/options')
def get_options():
    """Returns available options for language, country, and time period"""
    return jsonify({
        "languages": {
            # Primary languages for the app
            "en": "English",
            "hi": "Hindi",
            "te": "Telugu",
            "ta": "Tamil",
            "ml": "Malayalam",
            "bn": "Bengali",
            "mr": "Marathi",
            
            # Other languages supported by GNews but not shown in the dropdown
            "id": "Indonesian",
            "cs": "Czech",
            "de": "German",
            "es-419": "Spanish",
            "fr": "French",
            "it": "Italian",
            "lv": "Latvian",
            "lt": "Lithuanian",
            "hu": "Hungarian",
            "nl": "Dutch",
            "no": "Norwegian",
            "pl": "Polish",
            "pt-419": "Portuguese (Brazil)",
            "pt-150": "Portuguese (Portugal)",
            "ro": "Romanian",
            "sk": "Slovak",
            "sl": "Slovenian",
            "sv": "Swedish",
            "vi": "Vietnamese",
            "tr": "Turkish",
            "el": "Greek",
            "bg": "Bulgarian",
            "ru": "Russian",
            "sr": "Serbian",
            "uk": "Ukrainian",
            "he": "Hebrew",
            "ar": "Arabic",
            "th": "Thai",
            "zh-Hans": "Chinese (Simplified)",
            "zh-Hant": "Chinese (Traditional)",
            "ja": "Japanese",
            "ko": "Korean"
        },
        "countries": {
            "AU": "Australia",
            "BW": "Botswana",
            "CA": "Canada",
            "ET": "Ethiopia",
            "GH": "Ghana",
            "IN": "India",
            "ID": "Indonesia",
            "IE": "Ireland",
            "IL": "Israel",
            "KE": "Kenya",
            "LV": "Latvia",
            "MY": "Malaysia",
            "NA": "Namibia",
            "NZ": "New Zealand",
            "NG": "Nigeria",
            "PK": "Pakistan",
            "PH": "Philippines",
            "SG": "Singapore",
            "ZA": "South Africa",
            "TZ": "Tanzania",
            "UG": "Uganda",
            "GB": "United Kingdom",
            "US": "United States",
            "ZW": "Zimbabwe",
            "CZ": "Czech Republic",
            "DE": "Germany",
            "AT": "Austria",
            "CH": "Switzerland",
            "AR": "Argentina",
            "CL": "Chile",
            "CO": "Colombia",
            "CU": "Cuba",
            "MX": "Mexico",
            "PE": "Peru",
            "VE": "Venezuela",
            "BE": "Belgium",
            "FR": "France",
            "MA": "Morocco",
            "SN": "Senegal",
            "IT": "Italy",
            "LT": "Lithuania",
            "HU": "Hungary",
            "NL": "Netherlands",
            "NO": "Norway",
            "PL": "Poland",
            "BR": "Brazil",
            "PT": "Portugal",
            "RO": "Romania",
            "SK": "Slovakia",
            "SI": "Slovenia",
            "SE": "Sweden",
            "VN": "Vietnam",
            "TR": "Turkey",
            "GR": "Greece",
            "BG": "Bulgaria",
            "RU": "Russia",
            "UA": "Ukraine",
            "RS": "Serbia",
            "AE": "United Arab Emirates",
            "SA": "Saudi Arabia",
            "LB": "Lebanon",
            "EG": "Egypt",
            "BD": "Bangladesh",
            "TH": "Thailand",
            "CN": "China",
            "TW": "Taiwan",
            "HK": "Hong Kong",
            "JP": "Japan",
            "KR": "Republic of Korea"
        },
        "periods": {
            "1h": "Past hour",
            "12h": "Past 12 hours",
            "1d": "Past day",
            "3d": "Past 3 days",
            "7d": "Past week",
            "1m": "Past month"
        }
    })

@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors with a friendly message"""
    return jsonify({
        "error": "Endpoint not found",
        "message": "The requested URL was not found on this server. Make sure you're using a valid endpoint.",
        "available_endpoints": ["/", "/news/<query>", "/options", "/health"]
    }), 404

if __name__ == '__main__':
    print("News Scraper API running...")
    print("Available endpoints:")
    print("  - / : API information")
    print("  - /news/<query> : Get news articles")
    print("  - /options : Get available options for languages, countries, and time periods")
    print("  - /health : Health check")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
