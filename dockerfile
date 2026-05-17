# Dockerfile para o sistema ARIMA de predição de dados

# Usar imagem base do Python
FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de dependências primeiro (para melhor cache)
COPY requirements.txt .

# Instalar dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código da aplicação
COPY . .

# Criar diretórios necessários
RUN mkdir -p output config

# Expor a porta do Flask
EXPOSE 8004

# Comando para executar a aplicação
CMD ["python", "scripts/iniciar_pesquisa.py"]