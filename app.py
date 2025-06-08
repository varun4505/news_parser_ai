from flask import Flask, jsonify, request
from flask_cors import CORS
from gnews import GNews
import os
from dotenv import load_dotenv
import time
import urllib.parse
import feedparser

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://news-parser-frontend.vercel.app",
            "https://news-parser-ai.vercel.app",
            "https://*.vercel.app"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

app.config['DEBUG'] = True

news_cache = {}
cache_expiry = 300  # 5 minutes

def cleanup_cache():
    current_time = time.time()
    keys_to_remove = [key for key, (timestamp, _) in news_cache.items() if current_time - timestamp > cache_expiry]
    for key in keys_to_remove:
        del news_cache[key]

def extract_original_url(google_news_url):
    if not google_news_url or not google_news_url.startswith('https://news.google.com'):
        return google_news_url
    try:
        parsed_url = urllib.parse.urlparse(google_news_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        if 'url' in query_params:
            original_url = query_params['url'][0]
            if original_url.startswith('http'):
                return original_url
        return google_news_url
    except Exception:
        return google_news_url

def fetch_feedparser_articles(query, language, country, max_articles):
    rss_url = f'https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl={language}&gl={country}&ceid={country}:{language}'
    feed = feedparser.parse(rss_url)
    articles = []
    # Debug: print feed status and entry count
    print(f"Feedparser RSS URL: {rss_url}")
    print(f"Feedparser status: {getattr(feed, 'status', 'N/A')}")
    print(f"Feedparser bozo: {getattr(feed, 'bozo', 'N/A')}")
    if getattr(feed, 'bozo', False):
        print(f"Feedparser bozo_exception: {getattr(feed, 'bozo_exception', '')}")
    print(f"Feedparser entries found: {len(feed.entries)}")
    for entry in feed.entries[:max_articles]:
        # Prefer summary, but if not present, use title, never use link as description
        summary = getattr(entry, 'summary', '')
        if not summary or summary.strip() == getattr(entry, 'link', '').strip():
            summary = getattr(entry, 'title', '')
        article_data = {
            'title': getattr(entry, 'title', ''),
            'description': summary,
            'date': getattr(entry, 'published', 'Unknown'),
            'link': getattr(entry, 'link', ''),
            'google_news_link': getattr(entry, 'link', ''),
            'publication': entry.get('source', {}).get('title', 'Unknown Source') if hasattr(entry, 'source') else 'Unknown Source',
            'journalist': 'Not specified'
        }
        articles.append(article_data)
    return articles

@app.route('/news/<query>')
def get_news(query):
    try:
        max_articles = request.args.get('articles', default=30, type=int)
        max_articles = min(max(1, max_articles), 1000)
        language = request.args.get('language', default='en', type=str)
        country = request.args.get('country', default='IN', type=str)
        period = request.args.get('period', default='1d', type=str)
        cache_key = f"{query}_{language}_{country}_{period}_{max_articles}"
        cleanup_cache()
        if cache_key in news_cache:
            timestamp, cached_results = news_cache[cache_key]
            if time.time() - timestamp <= cache_expiry:
                return jsonify(cached_results)
        # GNews results
        gnews_client = GNews(
            language=language,
            country=country,
            max_results=max_articles,
            period=period
        )
        try:
            news_results = gnews_client.get_news(query)
        except Exception:
            news_results = []
        articles = []
        for item in news_results:
            title = item.get('title', 'No title')
            description = item.get('description', 'No description available')
            google_news_link = item.get('url', '#')
            publisher_info = item.get('publisher', {})
            publication = publisher_info.get('title', 'Unknown Source')
            date_str = item.get('published date', '')
            date = date_str if date_str else "Unknown"
            article_data = {
                'title': title,
                'description': description,
                'date': date,
                'link': google_news_link,
                'google_news_link': google_news_link,
                'publication': publication,
                'journalist': "Not specified"
            }
            articles.append(article_data)
        # Feedparser results
        feed_articles = fetch_feedparser_articles(query, language, country, max_articles*2)
        # Merge and deduplicate by link
        all_articles = {a['link']: a for a in articles + feed_articles}
        # Return up to max_articles*2 unique articles
        result_list = list(all_articles.values())[:max_articles*2]
        print(f"Total unique articles returned: {len(result_list)}")
        if not result_list:
            return jsonify({
                "error": "No articles found",
                "message": "Try a different search term.",
                "articles": []
            })
        news_cache[cache_key] = (time.time(), result_list)
        return jsonify({
            "count": len(result_list),
            "articles": result_list
        })
    except Exception as e:
        return jsonify({
            "error": "An error occurred while fetching news articles.",
            "details": str(e) if app.debug else None
        }), 500

@app.route('/')
def index():
    return jsonify({
        "name": "News Scraper API",
        "version": "1.0.0",
        "available_endpoints": [
            {"path": "/", "method": "GET", "description": "This information page"},
            {"path": "/news/<query>", "method": "GET", "description": "Get news articles based on search query"},
            {"path": "/options", "method": "GET", "description": "Get available options for languages and countries"},
            {"path": "/health", "method": "GET", "description": "Health check endpoint"}
        ],
        "usage": "Make GET requests to /news/your_search_query to retrieve news articles"
    })

@app.route('/health')
def health_check():
    return jsonify({"status": "OK"})

@app.route('/options')
def get_options():
    return jsonify({
        "languages": {
            "en": "English",
            "hi": "Hindi",
            "te": "Telugu",
            "ta": "Tamil",
            "ml": "Malayalam",
            "bn": "Bengali",
            "mr": "Marathi"
        },
        "countries": {
            "AU": "Australia",
            "IN": "India",
            "US": "United States",
            "GB": "United Kingdom",
            "CA": "Canada"
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
    return jsonify({
        "error": "Endpoint not found",
        "message": "The requested URL was not found on this server. Make sure you're using a valid endpoint.",
        "available_endpoints": ["/", "/news/<query>", "/options", "/health"]
    }), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
