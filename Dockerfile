# Dockerfile - VERSÃO FINAL PYTHON

# Usar uma imagem oficial do Python
FROM python:3.9-slim

# Definir o diretório de trabalho
WORKDIR /app

# Copiar o ficheiro de dependências
COPY requirements.txt requirements.txt

# Instalar as dependências
RUN pip install -r requirements.txt

# Copiar todo o código da aplicação
COPY . .

# Comando para executar a nossa aplicação Flask
CMD ["python", "app.py"]