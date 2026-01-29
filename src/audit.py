"""Endpoints de Auditoria e Relatórios"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from src.database import get_db
from src.models import PedidoProcessado, EntidadeDetectada
from src.iam.iam_man import admin_required
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])

# Schemas de Resposta (apenas para leitura)
class AuditoriaResumo(BaseModel):
    origem_id: UUID
    protocolo: Optional[str]
    created_at: datetime
    nivel_risco: Optional[str]
    total_entidades: int
    usuario_id: Optional[str]

class AuditoriaDetalhe(AuditoriaResumo):
    texto_anonimizado: str
    entidades_por_tipo: dict
    auditoria_tecnica: dict
    resumo_llm: Optional[dict]

@router.get(
    "/pedidos", 
    response_model=List[AuditoriaResumo],
    summary="Listar pedidos processados",
    description="Retorna uma lista paginada de pedidos. Requer privilégios de administrador."
)
async def listar_pedidos(
    skip: int = Query(0, description="Número de registros para pular"),
    limit: int = Query(50, description="Número máximo de registros"),
    risco: Optional[str] = Query(None, description="Filtrar por nível de risco (baixo, medio, alto)"),
    user: dict = Depends(admin_required),
    db: Session = Depends(get_db)
):
    query = db.query(PedidoProcessado)
    
    if risco:
        query = query.filter(PedidoProcessado.nivel_risco == risco)
        
    pedidos = query.order_by(PedidoProcessado.created_at.desc()).offset(skip).limit(limit).all()
    
    return [
        AuditoriaResumo(
            origem_id=p.origem_id,
            protocolo=p.protocolo,
            created_at=p.created_at,
            nivel_risco=p.nivel_risco,
            total_entidades=p.total_entidades,
            usuario_id=p.usuario_id
        ) for p in pedidos
    ]

@router.get(
    "/pedidos/{origem_id}", 
    response_model=AuditoriaDetalhe,
    summary="Detalhes completos de um pedido",
    description="Retorna todos os dados de um pedido específico, incluindo texto anonimizado e logs técnicos."
)
async def detalhar_pedido(
    origem_id: UUID,
    user: dict = Depends(admin_required),
    db: Session = Depends(get_db)
):
    pedido = db.query(PedidoProcessado).filter(PedidoProcessado.origem_id == origem_id).first()
    
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
        
    return AuditoriaDetalhe(
        origem_id=pedido.origem_id,
        protocolo=pedido.protocolo,
        created_at=pedido.created_at,
        nivel_risco=pedido.nivel_risco,
        total_entidades=pedido.total_entidades,
        usuario_id=pedido.usuario_id,
        texto_anonimizado=pedido.texto_anonimizado,
        entidades_por_tipo=pedido.entidades_por_tipo,
        auditoria_tecnica=pedido.auditoria,
        resumo_llm=pedido.resumo_llm
    )