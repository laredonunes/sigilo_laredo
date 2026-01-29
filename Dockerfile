# ==========================================
# Estágio 1: Base (Leve) - Para API, Banco, LLM, Dicionário
# ==========================================
FROM python:3.11-slim as base

WORKDIR /app

# Dependências do sistema (mínimas)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências leves
COPY requirements-base.txt .
RUN pip install --no-cache-dir -r requirements-base.txt

# Copia código fonte
COPY ./src /app/src

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# ==========================================
# Estágio 2: Heavy (Pesado) - Apenas para Detecção
# ==========================================
FROM base as heavy

# Instala dependências pesadas de IA
COPY requirements-heavy.txt .
RUN pip install --no-cache-dir -r requirements-heavy.txt

# Baixa modelo spaCy (apenas nesta imagem)
RUN pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl

# O código fonte já vem do estágio base