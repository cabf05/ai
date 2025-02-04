#!/bin/bash
set -e  # Para parar em caso de erro

# Instala dependências do sistema
sudo apt-get update -qq
sudo apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    libleptonica-dev \
    libtesseract-dev \
    poppler-utils

# Verifica instalação do Tesseract
echo "Versão do Tesseract:"
tesseract --version

# Instala dependências Python
python -m pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt

# Download de recursos NLTK
python -c "import nltk; nltk.download('stopwords'); nltk.download('punkt'); nltk.download('wordnet'); nltk.download('omw-1.4')"
