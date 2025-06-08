# This script sets up the development environment for the backend

# Create virtual environment if it doesn't exist
if (-not (Test-Path -Path ".\venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

# Activate virtual environment
Write-Host "Activating virtual environment..."
.\venv\Scripts\Activate

# Install dependencies
Write-Host "Installing dependencies..."
pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete! You can now run the Flask application with:"
Write-Host "python app.py"
Write-Host ""
Write-Host "Note: This application uses the gnews and newspaper3k libraries."
Write-Host "- gnews is used to fetch news articles from various sources"
Write-Host "- newspaper3k is used to extract detailed content from articles"
Write-Host ""
Write-Host "API endpoints:"
Write-Host "- /news/<query>                    Basic news search"
Write-Host "- /news/<query>?detailed=true      Get detailed article content (default)"
Write-Host "- /news/<query>?detailed=false     Skip detailed article extraction"
Write-Host "- /news/<query>?articles=20        Fetch up to 20 articles (default: 30, max: 30)"
Write-Host "- /news/<query>?language=fr        Filter by language (default: en)"
Write-Host "- /news/<query>?country=germany    Filter by country (default: india)"
Write-Host "- /news/<query>?period=7d         Filter by time period (default: 1d)"
Write-Host "- /options                         Get all available filter options"
