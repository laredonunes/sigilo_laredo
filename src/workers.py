"""Workers Celery para processamento assíncrono"""
from celery import group, chain
from src.celery_app import celery_app
from src.database import get_db
from src.models import PedidoProcessado, EntidadeDetectada
import redis
import json
import hashlib
from datetime import datetime
from uuid import UUID
import os
import logging
import sys

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("WORKER")

# Redis (Cache)
try:
    redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://sigilo-redis:6379/0'))
except Exception as e:
    logger.error(f"❌ Falha ao conectar Redis nos Workers: {e}")

# Variáveis globais para cache (Lazy Loading)
_detector = None
_llm_client = None

def get_detector():
    global _detector
    if _detector is None:
        from src.detector import PIIDetectorLAI
        _detector = PIIDetectorLAI()
    return _detector

def get_llm_client():
    global _llm_client
    if _llm_client is None:
        from src.llm_client import OllamaClient
        _llm_client = OllamaClient()
    return _llm_client

def atualizar_status(origem_id: UUID, status: str, step: str = None, progress: int = 0, result: dict = None):
    """Atualiza status no Redis"""
    try:
        logger.info(f"🔄 [REDIS] Atualizando status ID {origem_id}: {status} ({progress}%) - Step: {step}")
        data = {
            'origem_id': str(origem_id),
            'status': status,
            'step': step,
            'progress': progress,
            'result': result,
            'updated_at': datetime.utcnow().isoformat()
        }
        redis_client.setex(f"status:{origem_id}", 3600, json.dumps(data))
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar status no Redis: {e}")

@celery_app.task(name='src.workers.task_detectar_pii', bind=True)
def task_detectar_pii(self, origem_id: str, texto: str, protocolo: str = None, usuario_id: str = None):
    logger.info(f"🐰 [RABBITMQ] Mensagem recebida na fila 'deteccao'. ID: {origem_id}")
    try:
        origem_uuid = UUID(origem_id)
        atualizar_status(origem_uuid, 'processing', 'detecting', 25)
        
        logger.info(f"🕵️ Executando detector (Regex+Presidio)...")
        detector = get_detector()
        resultado = detector.detect(texto)
        logger.info(f"✅ Detecção concluída. Entidades: {resultado['entities_detected']}")
        
        dados = {
            'origem_id': origem_id,
            'texto': texto,
            'protocolo': protocolo,
            'usuario_id': usuario_id,
            'resultado_deteccao': resultado,
            'start_time': datetime.utcnow().isoformat()
        }
        
        atualizar_status(origem_uuid, 'processing', 'detected', 50)
        
        logger.info(f"🔗 Disparando tasks paralelas (Banco + LLM)...")
        workflow = chain(
            group(
                task_salvar_banco.s(dados),
                task_gerar_resumo_llm.s(dados)
            ),
            task_gerar_dicionario.s()
        )
        workflow.apply_async()
        
        return dados
        
    except Exception as e:
        logger.error(f"❌ [TASK 1] Falha na detecção: {e}")
        atualizar_status(UUID(origem_id), 'error', 'detection_failed', 0, {'error': str(e)})
        raise

@celery_app.task(
    name='src.workers.task_salvar_banco',
    bind=True,
    max_retries=3,
    default_retry_delay=10
)
def task_salvar_banco(self, dados: dict):
    origem_id = dados['origem_id']
    logger.info(f"🐰 [RABBITMQ] Mensagem recebida na fila 'banco'. ID: {origem_id}")
    try:
        origem_uuid = UUID(origem_id)
        resultado = dados['resultado_deteccao']
        
        atualizar_status(origem_uuid, 'processing', 'saving', 75)
        
        db = next(get_db())
        texto_hash = hashlib.sha256(dados['texto'].encode()).hexdigest()
        
        pedido = PedidoProcessado(
            origem_id=origem_uuid,
            protocolo=dados.get('protocolo'),
            texto_original_hash=texto_hash,
            texto_anonimizado=resultado['anonymized_text'],
            total_entidades=resultado['entities_detected'],
            entidades_por_tipo=resultado['entity_types'],
            nivel_risco=resultado['risk_level'],
            usuario_id=dados.get('usuario_id'),
            processed_at=datetime.utcnow()
        )
        db.add(pedido)
        
        for entidade in resultado.get('entities', []):
            valor_hash = hashlib.sha256(entidade['value'].encode()).hexdigest()
            ent_db = EntidadeDetectada(
                pedido_origem_id=origem_uuid,
                tipo=entidade['type'],
                valor_hash=valor_hash,
                confianca=entidade['confidence'],
                posicao_inicio=entidade['start'],
                posicao_fim=entidade['end'],
                metodo_deteccao=entidade['method']
            )
            db.add(ent_db)
        
        db.commit()
        logger.info(f"✅ [TASK 2A] Dados salvos no PostgreSQL com sucesso!")
        
        atualizar_status(origem_uuid, 'processing', 'saved', 85)
        return dados
        
    except Exception as e:
        logger.error(f"❌ [TASK 2A] Erro ao salvar no banco: {e}")
        # Retry automático
        raise self.retry(exc=e)

@celery_app.task(
    name='src.workers.task_gerar_resumo_llm',
    bind=True,
    max_retries=2,
    default_retry_delay=5
)
def task_gerar_resumo_llm(self, dados: dict):
    origem_id = dados['origem_id']
    logger.info(f"🐰 [RABBITMQ] Mensagem recebida na fila 'llm'. ID: {origem_id}")
    try:
        origem_uuid = UUID(origem_id)
        resultado = dados['resultado_deteccao']
        
        atualizar_status(origem_uuid, 'processing', 'generating_summary', 75)
        
        logger.info("🤖 Chamando OllamaClient...")
        llm_client = get_llm_client()
        resumo = llm_client.gerar_resumo_lai(
            texto_anonimizado=resultado['anonymized_text'],
            entidades_detectadas=resultado['entity_types']
        )
        logger.info("✅ [TASK 2B] Resumo LLM gerado com sucesso!")
        
        dados['resumo_llm'] = resumo
        atualizar_status(origem_uuid, 'processing', 'summary_generated', 85)
        return dados
        
    except Exception as e:
        logger.error(f"❌ [TASK 2B] Erro no LLM: {e}")
        # Se for erro de conexão, tenta de novo. Se for timeout, usa fallback.
        if "Connection refused" in str(e):
             raise self.retry(exc=e)

        llm_client = get_llm_client()
        dados['resumo_llm'] = llm_client._fallback_resumo()
        return dados

@celery_app.task(name='src.workers.task_gerar_dicionario')
def task_gerar_dicionario(resultados_anteriores: list):
    logger.info(f"🐰 [RABBITMQ] Mensagem recebida na fila 'dicionario'.")
    try:
        dados_com_resumo = next((r for r in resultados_anteriores if 'resumo_llm' in r), None)
        dados = resultados_anteriores[0]
        
        resumo_llm = dados_com_resumo.get('resumo_llm', {}) if dados_com_resumo else {}
        origem_uuid = UUID(dados['origem_id'])
        
        logger.info(f"📊 Consolidando ID: {origem_uuid}")
        
        resultado = dados['resultado_deteccao']
        start_time = datetime.fromisoformat(dados['start_time'])
        tempo_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        dicionario_saida = {
            'origem_id': dados['origem_id'],
            'protocolo': dados.get('protocolo'),
            'texto_anonimizado': resultado['anonymized_text'],
            'resumo_inteligente': resumo_llm,
            'estatisticas': {
                'total_entidades': resultado['entities_detected'],
                'por_tipo': resultado['entity_types'],
                'nivel_risco': resultado['risk_level']
            },
            'processamento': {
                'tempo_ms': tempo_ms,
                'timestamp': datetime.utcnow().isoformat()
            },
            'auditoria': {
                'usuario_id': dados.get('usuario_id'),
                'timestamp_inicio': dados['start_time'],
                'timestamp_fim': datetime.utcnow().isoformat(),
                'etapas': [
                    {'step': 'deteccao', 'status': 'completed'},
                    {'step': 'resumo_llm', 'status': 'completed'},
                    {'step': 'banco', 'status': 'completed'},
                    {'step': 'dicionario', 'status': 'completed'}
                ],
                'conformidade': {'lgpd': True, 'ia_local': True}
            }
        }
        
        atualizar_status(origem_uuid, 'completed', 'finished', 100, dicionario_saida)
        
        # Atualiza banco
        db = next(get_db())
        pedido = db.query(PedidoProcessado).filter_by(origem_id=origem_uuid).first()
        if pedido:
            pedido.tempo_processamento_ms = tempo_ms
            pedido.auditoria = dicionario_saida['auditoria']
            pedido.resumo_llm = resumo_llm
            db.commit()
            logger.info("💾 Banco atualizado com auditoria e resumo.")
            
        logger.info(f"🏁 [TASK 3] Processo FINALIZADO com sucesso para ID: {origem_uuid}")
        return dicionario_saida
        
    except Exception as e:
        logger.error(f"❌ [TASK 3] Erro na consolidação: {e}")
        atualizar_status(UUID(dados['origem_id']), 'error', 'output_generation_failed', 0, {'error': str(e)})
        raise