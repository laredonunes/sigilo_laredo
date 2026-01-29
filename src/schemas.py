"""Schemas Pydantic para validação de dados"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

class PedidoLAIInput(BaseModel):
    """Input do pedido LAI"""
    texto: str = Field(
        ..., 
        min_length=10, 
        max_length=10000,
        description="Texto integral do pedido de acesso à informação.",
        examples=["Solicito cópia do contrato 123/2023. Meu nome é João Silva, CPF 123.456.789-00."]
    )
    protocolo: Optional[str] = Field(
        None, 
        description="Número de protocolo do sistema de origem (opcional).",
        examples=["LAI-2026-001"]
    )
    usuario_id: Optional[str] = Field(
        None, 
        description="Identificador do usuário solicitante (opcional).",
        examples=["cidadao@email.com"]
    )

    class Config:
        json_schema_extra = {
            "example": {
                "texto": "Solicito acesso aos dados de salário dos servidores. Sou Maria Souza, RG 12.345.678-9.",
                "protocolo": "PROTO-999",
                "usuario_id": "maria.souza"
            }
        }

class DeteccaoResponse(BaseModel):
    """Resposta imediata da API (Async)"""
    origem_id: UUID = Field(..., description="ID único gerado para rastrear o pedido.")
    status: str = Field(..., description="Status atual do processamento.", examples=["processing"])
    message: str = Field(..., description="Mensagem informativa.")
    created_at: datetime

class StatusResponse(BaseModel):
    """Status do processamento"""
    origem_id: UUID
    status: str = Field(..., description="processing, completed, error")
    step: Optional[str] = Field(None, description="Etapa atual (ex: detecting, saving, generating_summary)")
    progress: int = Field(0, description="Progresso estimado (0-100)")
    result: Optional[Dict[str, Any]] = Field(None, description="Resultado final (apenas quando status=completed)")
    error: Optional[str] = None
    updated_at: datetime

class EntidadeDetectada(BaseModel):
    """Entidade PII detectada"""
    tipo: str
    valor_hash: str
    confianca: float
    inicio: int
    fim: int
    metodo: str

class ResultadoFinal(BaseModel):
    """Resultado final do processamento"""
    origem_id: UUID
    texto_anonimizado: str
    total_entidades: int
    entidades_por_tipo: Dict[str, int]
    nivel_risco: str
    tempo_processamento_ms: int
    auditoria: Dict[str, Any]