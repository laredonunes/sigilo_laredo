"""Configuração do Celery com RabbitMQ"""
from celery import Celery
import os

# Configuração de Broker (RabbitMQ) e Backend (Redis)
BROKER_URL = os.getenv('CELERY_BROKER_URL', 'amqp://admin:secret123@sigilo-rabbitmq:5672//')
BACKEND_URL = os.getenv('CELERY_RESULT_BACKEND', 'redis://sigilo-redis:6379/1')

celery_app = Celery(
    'pii_detector',
    broker=BROKER_URL,
    backend=BACKEND_URL,
    include=['src.workers']
)

# Configurações Otimizadas para Baixo Consumo de Memória
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    
    # Otimizações de Memória
    worker_prefetch_multiplier=1,  # Pega apenas 1 tarefa por vez
    worker_max_tasks_per_child=10, # Reinicia o worker a cada 10 tarefas (limpa vazamentos de memória)
    worker_concurrency=1,          # Padrão: 1 processo por worker (sobrescrito no docker-compose)

    broker_connection_retry_on_startup=True,
)

# Rotas de filas
celery_app.conf.task_routes = {
    'src.workers.task_detectar_pii': {'queue': 'deteccao'},
    'src.workers.task_salvar_banco': {'queue': 'banco'},
    'src.workers.task_gerar_resumo_llm': {'queue': 'llm'},
    'src.workers.task_gerar_dicionario': {'queue': 'dicionario'},
}