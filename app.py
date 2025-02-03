import os
os.environ['NLTK_DATA'] = '/opt/render/nltk_data'

import nltk
nltk.download('stopwords', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('wordnet', quiet=True)
nltk.download('omw-1.4', quiet=True)

import io
import requests
import pytesseract
from flask import Flask, request, redirect, session, render_template_string
from docx import Document
from PyPDF2 import PdfReader
from openpyxl import load_workbook
from PIL import Image
import fitz  # PyMuPDF

# Configuração do Tesseract para Render.com
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configurações dos serviços de IA
AI_SERVICES = {
    'OpenAI': {
        'guide': [
            '1. Acesse https://platform.openai.com/ e faça login',
            '2. Clique em "API Keys" no menu lateral',
            '3. Crie uma nova chave API',
            '4. Cole a chave gerada abaixo'
        ],
        'api_url': 'https://api.openai.com/v1/chat/completions'
    },
    'HuggingFace': {
        'guide': [
            '1. Acesse https://huggingface.co/',
            '2. Crie um token de acesso com permissão "Read"',
            '3. Cole o token abaixo'
        ],
        'api_url': 'https://api-inference.huggingface.co/models/'
    },
    'Cohere': {
        'guide': [
            '1. Acesse https://dashboard.cohere.ai/',
            '2. Crie uma nova chave API',
            '3. Cole a chave gerada abaixo'
        ],
        'api_url': 'https://api.cohere.ai/v1/generate'
    }
}

HTML_BASE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Sistema de Resumo de Documentos</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .container {{ max-width: 800px; margin: 50px auto; }}
        .card {{ margin-top: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); padding: 20px; }}
        .guide-step {{ margin: 15px 0; padding: 10px; background: #f8f9fa; border-radius: 5px; }}
        pre {{ white-space: pre-wrap; background: #f8f9fa; padding: 15px; border-radius: 5px; }}
        textarea {{ height: 400px; width: 100%; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h2 class="text-center mb-4">📄 Sistema de Resumo de Documentos</h2>
        <div class="card">
            <a href="/" class="btn btn-secondary mb-3">🏠 Voltar</a>
            {}
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

def extract_text_with_ocr(pdf_bytes):
    """Extrai texto de PDFs usando OCR"""
    try:
        text = []
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text.append(pytesseract.image_to_string(img, lang='por+eng'))
        
        return '\n'.join(text)
    except Exception as e:
        return f"Erro no OCR: {str(e)}"

def extract_text(file):
    """Extrai texto de diferentes formatos de arquivo"""
    try:
        content = file.read()
        filename = file.filename
        
        if filename.endswith('.pdf'):
            # Tenta extração textual primeiro
            try:
                pdf = PdfReader(io.BytesIO(content))
                text = '\n'.join([page.extract_text() for page in pdf.pages])
                if text.strip():
                    return text
            except:
                pass
            
            # Fallback para OCR
            return extract_text_with_ocr(content)
        
        elif filename.endswith('.docx'):
            doc = Document(io.BytesIO(content))
            return '\n'.join([para.text for para in doc.paragraphs])
        
        elif filename.endswith(('.xlsx', '.xls')):
            wb = load_workbook(io.BytesIO(content))
            text = []
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    text.append(' '.join(map(str, row)))
            return '\n'.join(text)
            
    except Exception as e:
        return f"Erro na extração: {str(e)}"

def generate_summary(text, service, api_key):
    """Gera o resumo usando o serviço de IA selecionado"""
    prompt = f"Resuma este documento de forma clara e detalhada em português brasileiro:\n\n{text}"
    
    try:
        if service == 'OpenAI':
            headers = {'Authorization': f'Bearer {api_key}'}
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}]
            }
            response = requests.post(AI_SERVICES[service]['api_url'], json=data, headers=headers)
            return response.json()['choices'][0]['message']['content']
        
        elif service == 'HuggingFace':
            headers = {'Authorization': f'Bearer {api_key}'}
            data = {"inputs": prompt}
            response = requests.post(AI_SERVICES[service]['api_url'], json=data, headers=headers)
            return response.json()[0]['generated_text']
        
        elif service == 'Cohere':
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            data = {
                "prompt": prompt,
                "model": "command",
                "max_tokens": 500
            }
            response = requests.post(AI_SERVICES[service]['api_url'], json=data, headers=headers)
            return response.json()['generations'][0]['text']
    
    except Exception as e:
        return f"Erro na geração do resumo: {str(e)}"

@app.route('/', methods=['GET'])
def home():
    content = '''
    <div class="text-center">
        <h4 class="mb-4">Selecione uma opção:</h4>
        <a href="/settings" class="btn btn-primary btn-lg mb-2">⚙️ Configurações</a><br>
        <a href="/process" class="btn btn-success btn-lg">📄 Processar Documento</a>
    </div>
    '''
    return render_template_string(HTML_BASE, content=content)

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        session['ai_service'] = request.form.get('ai_service')
        return redirect(f'/configure/{request.form.get("ai_service")}')
    
    content = '''
    <h4 class="mb-4">⚙️ Configurações do Sistema</h4>
    <form method="POST">
        <div class="mb-3">
            <label>Selecione o serviço de IA:</label>
            <select name="ai_service" class="form-select" required>
                <option value="">-- Selecione --</option>
                <option value="OpenAI">OpenAI</option>
                <option value="HuggingFace">HuggingFace</option>
                <option value="Cohere">Cohere</option>
            </select>
        </div>
        <button type="submit" class="btn btn-primary">Continuar</button>
    </form>
    '''
    return render_template_string(HTML_BASE, content=content)

@app.route('/configure/<service>', methods=['GET', 'POST'])
def configure(service):
    if request.method == 'POST':
        session['api_key'] = request.form.get('api_key')
        return redirect('/')
    
    guide_steps = "<hr>".join([f'<div class="guide-step">{step}</div>' for step in AI_SERVICES[service]['guide']])
    
    content = f'''
    <h4 class="mb-4">🔑 Configurar {service}</h4>
    <div class="mb-4">
        {guide_steps}
    </div>
    <form method="POST">
        <div class="mb-3">
            <label>Cole sua chave API:</label>
            <input type="text" name="api_key" class="form-control" required>
        </div>
        <button type="submit" class="btn btn-primary">Salvar</button>
    </form>
    '''
    return render_template_string(HTML_BASE, content=content)

@app.route('/process', methods=['GET', 'POST'])
def process():
    if 'api_key' not in session:
        return redirect('/settings')
    
    if request.method == 'POST':
        if 'file' in request.files:
            # Primeiro estágio: upload do arquivo
            file = request.files['file']
            if file.filename == '':
                return redirect(request.url)
            
            extracted_text = extract_text(file)
            session['extracted_text'] = extracted_text
            session['filename'] = file.filename
            
            content = f'''
            <h4 class="mb-4">✏️ Editar Texto Extraído</h4>
            <form method="POST">
                <div class="mb-3">
                    <label>Texto extraído de {file.filename}:</label>
                    <textarea name="edited_text" class="form-control">{extracted_text}</textarea>
                </div>
                <button type="submit" class="btn btn-primary">Gerar Resumo</button>
            </form>
            '''
            return render_template_string(HTML_BASE, content=content)
        else:
            # Segundo estágio: geração do resumo
            edited_text = request.form.get('edited_text', '')
            summary = generate_summary(
                edited_text,
                session['ai_service'],
                session['api_key']
            )
            
            content = f'''
            <h4 class="mb-4">📝 Resumo Gerado</h4>
            <div class="alert alert-info">
                <h5>Texto Enviado:</h5>
                <pre>{edited_text[:2000]}{'...' if len(edited_text) > 2000 else ''}</pre>
            </div>
            <div class="alert alert-success">
                <h5>Resumo:</h5>
                <pre>{summary}</pre>
            </div>
            <a href="/process" class="btn btn-primary">Nova Análise</a>
            '''
            return render_template_string(HTML_BASE, content=content)
    
    content = '''
    <h4 class="mb-4">📤 Enviar Documento</h4>
    <form method="POST" enctype="multipart/form-data">
        <div class="mb-3">
            <label>Selecione o arquivo (PDF, DOCX, XLSX):</label>
            <input type="file" name="file" class="form-control" required>
        </div>
        <button type="submit" class="btn btn-primary">Enviar</button>
    </form>
    '''
    return render_template_string(HTML_BASE, content=content)

if __name__ == '__main__':
    app.run(debug=True)
