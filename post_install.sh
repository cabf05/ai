#!/bin/bash
set -e

# Instala dependências do sistema
sudo apt-get update
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    libtesseract-dev \
    libleptonica-dev

# Instala dependências Python
python -m pip install --upgrade pip
pip install -r requirements.txt

# Download de recursos NLTK
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt'); nltk.download('wordnet'); nltk.download('omw-1.4')"
