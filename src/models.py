"""Models SQLAlchemy para banco de dados"""
from sqlalchemy import Column, String, Integer, Float, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class PedidoProcessado(Base):
    """Pedido LAI processado"""
    __tablename__ = "pedidos_processados"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    origem_id = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)
    protocolo = Column(String(100), nullable=True, index=True)
    texto_original_hash = Column(String(64), nullable=False)  # SHA256 do texto
    texto_anonimizado = Column(Text, nullable=False)
    
    # Metadados
    total_entidades = Column(Integer, default=0)
    entidades_por_tipo = Column(JSON, default=dict)
    nivel_risco = Column(String(20))  # baixo, medio, alto
    
    # Auditoria
    usuario_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    processed_at = Column(DateTime, nullable=True)
    tempo_processamento_ms = Column(Integer, nullable=True)
    
    # Rastreabilidade
    auditoria = Column(JSON, default=dict)
    
    # NOVO: Resumo gerado por LLM
    resumo_llm = Column(JSON, nullable=True)

class EntidadeDetectada(Base):
    """Entidades PII detectadas"""
    __tablename__ = "entidades_detectadas"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    pedido_origem_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    tipo = Column(String(50), nullable=False, index=True)
    valor_hash = Column(String(64), nullable=False)  # SHA256 do valor
    confianca = Column(Float, default=1.0)
    posicao_inicio = Column(Integer)
    posicao_fim = Column(Integer)
    metodo_deteccao = Column(String(20))  # regex, presidio, gliner
    
    created_at = Column(DateTime, default=datetime.utcnow)