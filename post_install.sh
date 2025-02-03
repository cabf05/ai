#!/bin/bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-por
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt'); nltk.download('wordnet'); nltk.download('omw-1.4')"
