import os
import io
import logging
import requests
from flask import Flask, request, redirect, session, render_template_string
from PyPDF2 import PdfReader
from docx import Document
from openpyxl import load_workbook
import pytesseract
from PIL import Image
import fitz  # PyMuPDF

# Configuração do ambiente
os.environ['NLTK_DATA'] = '/opt/render/nltk_data'
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Serviços de IA
AI_SERVICES = {
    'OpenAI': {
        'guide': [
            '1. Acesse https://platform.openai.com/',
            '2. Crie uma API Key em "API Keys"',
            '3. Cole a chave abaixo'
        ],
        'api_url': 'https://api.openai.com/v1/chat/completions'
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

HTML_BASE = '''<!DOCTYPE html>
<html>
<head>
    <title>Sistema de Resumo</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .container { max-width: 800px; margin: 50px auto; }
        .card { padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        textarea { height: 400px; width: 100%; margin: 20px 0; }
        pre { white-space: pre-wrap; background: #f8f9fa; padding: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <h2 class="text-center mb-4">📄 Sistema de Resumo</h2>
        <div class="card">
            <a href="/" class="btn btn-secondary mb-3">🏠 Voltar</a>
            {}
        </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>'''

def extract_text(file):
    try:
        content = file.read()
        filename = file.filename
        
        if filename.endswith('.pdf'):
            try:
                pdf = PdfReader(io.BytesIO(content))
                return '\n'.join([page.extract_text() for page in pdf.pages])
            except:
                doc = fitz.open(stream=content, filetype="pdf")
                text = []
                for page in doc:
                    pix = page.get_pixmap(dpi=200)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    text.append(pytesseract.image_to_string(img))
                return '\n'.join(text)
        
        elif filename.endswith('.docx'):
            doc = Document(io.BytesIO(content))
            return '\n'.join([para.text for para in doc.paragraphs])
        
        elif filename.endswith(('.xlsx', '.xls')):
            wb = load_workbook(io.BytesIO(content))
            return '\n'.join(' '.join(map(str, row)) for sheet in wb for row in sheet.iter_rows(values_only=True))
            
        return "Formato não suportado"
    except Exception as e:
        return f"Erro na extração: {str(e)}"

def generate_summary(text, service, api_key):
    try:
        prompt = f"Resuma este documento em português de forma clara e detalhada:\n\n{text}"
        
        if service == 'OpenAI':
            headers = {'Authorization': f'Bearer {api_key}'}
            data = {
                "model": "gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}]
            }
            response = requests.post(AI_SERVICES[service]['api_url'], json=data, headers=headers, timeout=60)
            return response.json()['choices'][0]['message']['content']
        
        elif service == 'Cohere':
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            }
            data = {
                "prompt": prompt,
                "model": "command",
                "max_tokens": 1000
            }
            response = requests.post(AI_SERVICES[service]['api_url'], json=data, headers=headers, timeout=60)
            return response.json()['generations'][0]['text']
    
    except Exception as e:
        return f"Erro na geração: {str(e)}"

@app.route('/')
def home():
    return render_template_string(HTML_BASE, content='''
        <div class="text-center">
            <h4 class="mb-4">Selecione:</h4>
            <a href="/settings" class="btn btn-primary btn-lg mb-2">⚙️ Configurações</a><br>
            <a href="/process" class="btn btn-success btn-lg">📄 Processar</a>
        </div>
    ''')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        session['ai_service'] = request.form.get('ai_service')
        return redirect(f'/configure/{request.form.get("ai_service")}')
    
    return render_template_string(HTML_BASE, content='''
        <h4 class="mb-4">⚙️ Configurações</h4>
        <form method="POST">
            <select name="ai_service" class="form-select mb-3" required>
                <option value="">Selecione o serviço...</option>
                <option value="OpenAI">OpenAI</option>
                <option value="Cohere">Cohere</option>
            </select>
            <button type="submit" class="btn btn-primary">Continuar</button>
        </form>
    ''')

@app.route('/configure/<service>', methods=['GET', 'POST'])
def configure(service):
    if request.method == 'POST':
        session['api_key'] = request.form.get('api_key')
        return redirect('/')
    
    return render_template_string(HTML_BASE, content=f'''
        <h4 class="mb-4">🔧 {service}</h4>
        <div class="mb-3">
            {'<br>'.join(AI_SERVICES[service]['guide'])}
        </div>
        <form method="POST">
            <input type="text" name="api_key" class="form-control mb-3" placeholder="Cole sua chave API" required>
            <button type="submit" class="btn btn-primary">Salvar</button>
        </form>
    ''')

@app.route('/process', methods=['GET', 'POST'])
def process():
    if 'api_key' not in session:
        return redirect('/settings')
    
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            text = extract_text(file)
            session['text'] = text
            return render_template_string(HTML_BASE, content=f'''
                <h4>✏️ Editar Texto</h4>
                <form method="POST">
                    <textarea name="text" class="form-control">{text}</textarea>
                    <button type="submit" class="btn btn-primary mt-3">Gerar Resumo</button>
                </form>
            ''')
        else:
            text = request.form.get('text', '')
            summary = generate_summary(text, session['ai_service'], session['api_key'])
            return render_template_string(HTML_BASE, content=f'''
                <div class="alert alert-success">
                    <h5>Resumo:</h5>
                    <pre>{summary}</pre>
                </div>
                <a href="/process" class="btn btn-primary">Nova Análise</a>
            ''')
    
    return render_template_string(HTML_BASE, content='''
        <h4>📤 Enviar Documento</h4>
        <form method="POST" enctype="multipart/form-data">
            <input type="file" name="file" class="form-control mb-3" accept=".pdf,.docx,.xlsx" required>
            <button type="submit" class="btn btn-primary">Enviar</button>
        </form>
    ''')

if __name__ == '__main__':
    app.run(debug=False)
