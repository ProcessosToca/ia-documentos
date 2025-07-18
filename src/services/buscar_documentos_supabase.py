
"""
Módulo de Busca de Documentos no Supabase
"""

import os
import logging
from typing import List, Optional
from supabase import create_client

logger = logging.getLogger(__name__)

def obter_cliente_supabase():
    """Obtém cliente Supabase configurado"""
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Variáveis SUPABASE_URL e SUPABASE_KEY devem estar configuradas")
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def buscar_documentos_supabase(required: Optional[bool] = None) -> List[dict]:
    """
    Busca documentos ativos na tabela ai_document_types
    
    Args:
        required: Se True, retorna apenas obrigatórios. Se False, apenas opcionais. Se None, todos.
    
    Returns:
        Lista de documentos ativos
    """
    try:
        supabase = obter_cliente_supabase()
        query = supabase.table('ai_document_types').select('*').eq('is_active', True)
        
        if required is not None:
            query = query.eq('required', required)
        
        response = query.order('name').execute()
        return response.data or []
        
    except Exception as e:
        logger.error(f"Erro ao buscar documentos: {e}")
        return []

def buscar_documentos_obrigatorios() -> List[dict]:
    """Busca documentos obrigatórios ativos"""
    return buscar_documentos_supabase(required=True)

def buscar_documentos_opcionais() -> List[dict]:
    """Busca documentos opcionais ativos"""
    return buscar_documentos_supabase(required=False)
