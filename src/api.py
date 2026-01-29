"""API FastAPI - Endpoints"""
from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from src.schemas import PedidoLAIInput, DeteccaoResponse, StatusResponse
from src.workers import task_detectar_pii
from src.database import engine
from src.models import Base
from src.iam.iam_man import get_current_user
from src.audit import router as audit_router
from uuid import uuid4, UUID
from datetime import datetime
from sqlalchemy import text
import redis
import json
import os
import logging
import traceback
import sys

# Rate Limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("API")

# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("🚀 INICIANDO API - Verificando Banco de Dados...")
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Tabelas verificadas/criadas com sucesso!")
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO ao conectar no Banco: {e}")
    yield
    logger.info("🛑 DESLIGANDO API...")

# Metadados da API
tags_metadata = [
    {
        "name": "Detecção",
        "description": "Endpoints principais para envio e processamento de pedidos LAI.",
    },
    {
        "name": "Auditoria",
        "description": "Endpoints restritos para administradores visualizarem logs e relatórios.",
    },
    {
        "name": "Sistema",
        "description": "Health checks e diagnósticos.",
    },
]

app = FastAPI(
    title="🕵️ Sigilo API - Participa DF",
    description="""
    **API de Detecção e Anonimização de Dados Pessoais (PII) com IA Generativa Local.**
    
    Esta API foi desenvolvida para o Hackathon Participa DF com o objetivo de automatizar a proteção de dados em pedidos da Lei de Acesso à Informação (LAI).
    
    ### 🚀 Funcionalidades Principais
    *   **Detecção Híbrida**: Regex + NLP (Presidio) + Contexto.
    *   **Anonimização Segura**: Substituição irreversível de dados sensíveis.
    *   **IA Local (Qwen 2.5)**: Gera resumos e categorização sem enviar dados para nuvem.
    *   **Auditoria Completa**: Rastreabilidade total de cada etapa.
    
    ### 🔒 Segurança
    *   Autenticação via Bearer Token (IAM).
    *   Rate Limiting por IP.
    *   Dados sensíveis nunca são persistidos em texto claro.
    """,
    version="2.0.0",
    contact={
        "name": "Laredo nunes",
        "url": "https://www.linkedin.com/in/laredo-nunes-0a8a7363",
        "email": "laredonunes@gmail.com",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=tags_metadata,
    lifespan=lifespan
)

# Configuração Limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audit_router)

# Conexão Redis
try:
    redis_url = os.getenv('REDIS_URL', 'redis://sigilo-redis:6379/0')
    logger.info(f"🔌 Conectando ao Redis (Cache): {redis_url}")
    redis_client = redis.from_url(redis_url)
    redis_client.ping()
    logger.info("✅ Conexão Redis OK!")
except Exception as e:
    logger.error(f"❌ Falha ao conectar no Redis: {e}")

# --- ROTAS ---

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard():
    """Serve o Dashboard de Teste na raiz"""
    try:
        dashboard_path = "/app/tests/dashboard.html"
        if os.path.exists(dashboard_path):
            with open(dashboard_path, "r", encoding="utf-8") as f:
                return f.read()
        else:
            return "<h1>Dashboard não encontrado</h1>"
    except Exception as e:
        logger.error(f"Erro ao servir dashboard: {e}")
        return JSONResponse({"status": "ok", "message": "API Online"}, status_code=200)

@app.post(
    "/detectar-pii", 
    response_model=DeteccaoResponse, 
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Detecção"],
    summary="Enviar pedido para análise",
    description="Recebe um texto de pedido LAI, enfileira para processamento assíncrono e retorna um ID para acompanhamento."
)
@limiter.limit("10/minute") 
async def detectar_pii(
    request: Request,
    pedido: PedidoLAIInput,
    current_user: dict = Depends(get_current_user)
):
    request_id = str(uuid4())
    user_id = current_user.get('sub') or current_user.get('email') or 'unknown'
    logger.info(f"📥 [POST] Novo pedido recebido de {user_id}. ID Gerado: {request_id}")
    
    try:
        logger.info(f"📤 Enviando mensagem para RabbitMQ (Fila: deteccao)...")
        task_detectar_pii.apply_async(
            args=[request_id, pedido.texto, pedido.protocolo, user_id],
            queue='deteccao'
        )
        logger.info(f"✅ Mensagem enviada para RabbitMQ com sucesso!")
        
        now = datetime.utcnow().isoformat()
        status_inicial = {
            'origem_id': request_id,
            'status': 'processing',
            'step': 'queued',
            'progress': 0,
            'created_at': now,
            'updated_at': now
        }
        redis_client.setex(f"status:{request_id}", 3600, json.dumps(status_inicial))
        logger.info(f"💾 Status inicial salvo no Redis para ID: {request_id}")
        
        return DeteccaoResponse(
            origem_id=UUID(request_id),
            status="processing",
            message=f"Pedido {pedido.protocolo or 'sem protocolo'} em processamento",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"❌ ERRO ao processar pedido {request_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/status/{origem_id}", 
    response_model=StatusResponse,
    tags=["Detecção"],
    summary="Consultar status do processamento",
    description="Retorna o estado atual do pedido. Se concluído, inclui o texto anonimizado, resumo da IA e auditoria."
)
async def consultar_status(
    origem_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    logger.info(f"🔍 [GET] Consultando status para ID: {origem_id} (User: {current_user.get('sub')})")
    
    try:
        status_key = f"status:{origem_id}"
        status_data = redis_client.get(status_key)
        
        if not status_data:
            logger.warning(f"⚠️ Status NÃO ENCONTRADO no Redis para ID: {origem_id}")
            raise HTTPException(status_code=404, detail="Processamento não encontrado")
        
        logger.info(f"✅ Status recuperado do Redis para ID: {origem_id}")
        data = json.loads(status_data)
        
        updated_at_str = data.get('updated_at') or data.get('created_at') or datetime.utcnow().isoformat()
        
        return StatusResponse(
            origem_id=UUID(data['origem_id']),
            status=data['status'],
            step=data.get('step'),
            progress=data.get('progress', 0),
            result=data.get('result'),
            error=data.get('error'),
            updated_at=datetime.fromisoformat(updated_at_str)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ ERRO ao consultar status {origem_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/health", 
    tags=["Sistema"],
    summary="Verificar saúde do sistema",
    description="Checa conectividade com Redis, PostgreSQL e Ollama."
)
async def health_check():
    """Health check detalhado"""
    services_status = {}
    
    # Redis
    try:
        redis_client.ping()
        services_status['redis'] = 'ok'
    except:
        services_status['redis'] = 'error'
    
    # PostgreSQL
    try:
        from src.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        services_status['postgres'] = 'ok'
    except:
        services_status['postgres'] = 'error'
    
    # Ollama
    try:
        import requests
        ollama_url = os.getenv('OLLAMA_URL', 'http://sigilo-ollama:11434')
        res = requests.get(f"{ollama_url}/api/tags", timeout=2)
        services_status['ollama'] = 'ok' if res.status_code == 200 else 'error'
    except:
        services_status['ollama'] = 'error'
    
    all_ok = all(status == 'ok' for status in services_status.values())
    
    return {
        "status": "healthy" if all_ok else "degraded",
        "version": "2.0.0",
        "services": services_status,
        "timestamp": datetime.utcnow().isoformat()
    }