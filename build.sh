#!/bin/bash

# Install Python dependencies
pip install -r requirements.txt

# Run NLTK setup script
python api/nltk_setup.py

echo "Build completed successfully!"
