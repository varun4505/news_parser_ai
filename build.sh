#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

echo "Starting build process..."

# Install Python dependencies
echo "Installing dependencies from requirements.txt..."
pip install -r requirements.txt

# Run NLTK setup script
echo "Setting up NLTK data..."
python api/nltk_setup.py

# Verify critical installations
echo "Verifying installations..."
if python -c "import flask, newspaper, lxml, lxml_html_clean, nltk" > /dev/null 2>&1; then
  echo "All critical packages verified!"
else
  echo "ERROR: Some required packages are not properly installed."
  echo "Please check the requirements.txt and deployment logs."
  exit 1
fi

echo "Build completed successfully!"
