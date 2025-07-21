import os
import json
from supabase import create_client, Client
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cache simples em memória
_cache_memoria = {}

def validar_formatar_cpf(cpf: str) -> dict:
    """
    Valida e formatar um CPF
    
    Args:
        cpf (str): CPF para validar (pode conter pontos e traços)
        
    Returns:
        dict: Resultado da validação com:
            - valido: True/False
            - cpf_limpo: Apenas números
            - cpf_formatado: XXX.XXX.XXX-XX
            - mensagem: Mensagem de erro se inválido
    """
    # Remover caracteres especiais
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    
    # Validar quantidade de dígitos
    if len(cpf_limpo) != 11:
        return {
            "valido": False,
            "cpf_limpo": None,
            "cpf_formatado": None,
            "mensagem": "Por favor, envie um CPF válido com 11 dígitos"
        }
    
    # Formatar CPF
    cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
    
    return {
        "valido": True,
        "cpf_limpo": cpf_limpo,
        "cpf_formatado": cpf_formatado,
        "mensagem": None
    }

def obter_cliente_supabase():
    """
    Obtém cliente Supabase configurado usando variáveis de ambiente
    """
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # Verificar se as variáveis de ambiente estão configuradas
    if not SUPABASE_URL:
        raise ValueError("❌ Variável de ambiente SUPABASE_URL não está configurada")
        
    if not SUPABASE_KEY:
        raise ValueError("❌ Variável de ambiente SUPABASE_KEY não está configurada")
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def buscar_dados_unificados_por_cpf(cpf: str) -> dict:
    """
    Busca unificada por CPF em todas as tabelas relevantes
    """
    global _cache_memoria
    
    # Verificar cache
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    cache_key = f"dados_unificados_{cpf_limpo}"
    
    if cache_key in _cache_memoria:
        logger.info(f"💾 Cache encontrado para: {cache_key}")
        return _cache_memoria[cache_key]
    
    try:
        supabase = obter_cliente_supabase()
        
        # 1. Buscar cliente
        logger.info(f"🔍 Buscando cliente por CPF: {cpf}")
        cliente_response = supabase.table('clientes').select('*').eq('cpf', cpf).execute()
        cliente = cliente_response.data[0] if cliente_response.data else None
        
        if cliente:
            logger.info("✅ Cliente encontrado")
        
        # 2. Buscar colaborador
        logger.info(f"🔍 Buscando colaborador por CPF: {cpf}")
        cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}" if len(cpf_limpo) == 11 else cpf
        
        colaborador = None
        for cpf_busca in [cpf_formatado, cpf_limpo]:
            colaborador_response = supabase.table('system_users').select(
                '*, company_sectors(name)'
            ).eq('cpf', cpf_busca).execute()
            
            if colaborador_response.data:
                colaborador = colaborador_response.data[0]
                break
        
        # 3. Buscar negociações por CPF (usando nova coluna client_cpf)
        logger.info(f"🔍 Buscando negociações por CPF: {cpf}")
        negociacoes = []
        for cpf_busca in [cpf_formatado, cpf_limpo]:
            negociacoes_response = supabase.table('ai_negotiations').select(
                '*, properties(title, address)'
            ).eq('client_cpf', cpf_busca).order('created_at', desc=True).execute()
            
            if negociacoes_response.data:
                negociacoes.extend(negociacoes_response.data)
        
        # 4. Buscar documentos por CPF (usando nova coluna client_cpf)
        logger.info(f"🔍 Buscando documentos por CPF: {cpf}")
        documentos = []
        for cpf_busca in [cpf_formatado, cpf_limpo]:
            documentos_response = supabase.table('ai_documents').select(
                '*, ai_document_types(name, description)'
            ).eq('client_cpf', cpf_busca).execute()
            
            if documentos_response.data:
                documentos.extend(documentos_response.data)
        
        # Montar resultado unificado
        resultado = {
            "colaborador": colaborador,
            "cliente": cliente,
            "negociacoes": negociacoes,
            "documentos": documentos,
            "multiplas_negociacoes": len(negociacoes) > 1,
            "total_negociacoes_ativas": len([n for n in negociacoes if n['status'] in ['iniciada', 'coletando_documentos', 'documentos_pendentes', 'documentos_validados', 'aguardando_corretor']]),
            "documentos_por_cpf": len(documentos),
            "ultima_interacao": max([n['created_at'] for n in negociacoes], default=None) if negociacoes else None
        }
        
        # Armazenar no cache
        _cache_memoria[cache_key] = resultado
        logger.info(f"💾 Cache definido para: {cache_key}")
        logger.info(f"✅ Busca unificada concluída - Colaborador: {colaborador is not None}, Cliente: {cliente is not None}, Negociações: {len(negociacoes)}")
        
        return resultado
        
    except Exception as e:
        logger.error(f"❌ Erro na busca unificada: {str(e)}")
        return {
            "colaborador": None,
            "cliente": None,
            "negociacoes": [],
            "documentos": [],
            "multiplas_negociacoes": False,
            "total_negociacoes_ativas": 0,
            "documentos_por_cpf": 0,
            "ultima_interacao": None
        }

def buscar_usuario_por_cpf(cpf: str) -> Optional[dict]:
    try:
        supabase = obter_cliente_supabase()
        
        # Tentar com CPF formatado primeiro
        cpf_formatado = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf
        
        response = supabase.table('system_users').select(
            '*, company_sectors(name)'
        ).eq('cpf', cpf_formatado).execute()
        
        # Se não encontrar, tentar com CPF limpo
        if not response.data:
            cpf_limpo = ''.join(filter(str.isdigit, cpf))
            if cpf_limpo != cpf_formatado:
                response = supabase.table('system_users').select(
                    '*, company_sectors(name)'
                ).eq('cpf', cpf_limpo).execute()
        
        if response.data:
            logger.info(f"✅ Usuário encontrado no banco")
            return response.data[0]
        else:
            logger.info(f"❌ Usuário não encontrado no banco")
            return None
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar usuário por CPF: {str(e)}")
        return None

def buscar_cliente_por_cpf(cpf: str) -> Optional[dict]:
    """
    Busca cliente na tabela clientes pelo CPF
    """
    try:
        supabase = obter_cliente_supabase()
        
        # Buscar cliente pelo CPF
        response = supabase.table('clientes').select('*').eq('cpf', cpf).execute()
        
        if response.data:
            logger.info(f"✅ Cliente encontrado na tabela clientes")
            return response.data[0]
        else:
            logger.info(f"❌ Cliente não encontrado na tabela clientes")
            return None
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar cliente por CPF: {str(e)}")
        return None

def buscar_negociacao_ativa(telefone: str, cpf: str = None) -> Optional[dict]:
    """
    Busca negociação ativa pelo telefone e/ou CPF do cliente (versão melhorada)
    """
    global _cache_memoria
    
    # Verificar cache
    cache_key = f"negociacao_ativa_{telefone}_{cpf or ''}"
    if cache_key in _cache_memoria:
        logger.info(f"💾 Cache encontrado para: {cache_key}")
        return _cache_memoria[cache_key]
    
    try:
        supabase = obter_cliente_supabase()
        
        # Status considerados como "em andamento" (não finalizados)
        status_ativos = ['iniciada', 'coletando_documentos', 'documentos_pendentes', 
                        'documentos_validados', 'aguardando_corretor']
        
        # Construir query base
        query = supabase.table('ai_negotiations').select(
            '*, properties(title, address)'
        ).in_('status', status_ativos)
        
        # Adicionar filtros
        if cpf:
            query = query.eq('client_cpf', cpf)
        if telefone:
            query = query.eq('client_phone', telefone)
            
        # Ordenar por data mais recente
        query = query.order('created_at', desc=True)
        
        response = query.execute()
        
        if response.data:
            negociacao = response.data[0]  # Mais recente
            
            # Enriquecer com dados de conversas recentes
            conversas_recentes = buscar_conversas_ia_cliente_enriquecidas(negociacao['id'], limite=3)
            
            negociacao['multiplas_negociacoes'] = len(response.data) > 1
            negociacao['total_negociacoes_ativas'] = len(response.data)
            negociacao['conversas_recentes'] = conversas_recentes
            negociacao['ultima_interacao'] = conversas_recentes[0]['timestamp'] if conversas_recentes else None
            
            # Armazenar no cache
            _cache_memoria[cache_key] = negociacao
            logger.info(f"💾 Cache definido para: {cache_key}")
            logger.info(f"✅ Negociação ativa encontrada - ID: {negociacao['id'][:8]}...")
            
            return negociacao
        else:
            logger.info(f"❌ Nenhuma negociação ativa encontrada")
            return None
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar negociação ativa: {str(e)}")
        return None

def buscar_documentos_obrigatorios() -> List[dict]:
    """
    Busca todos os tipos de documentos obrigatórios (com cache)
    """
    global _cache_memoria
    
    cache_key = "documentos_obrigatorios"
    if cache_key in _cache_memoria:
        logger.info(f"💾 Cache encontrado para: {cache_key}")
        return _cache_memoria[cache_key]
    
    try:
        supabase = obter_cliente_supabase()
        
        response = supabase.table('ai_document_types').select('*').eq('required', True).eq('is_active', True).execute()
        
        if response.data:
            _cache_memoria[cache_key] = response.data
            logger.info(f"💾 Cache definido para: {cache_key}")
            logger.info(f"✅ {len(response.data)} tipos de documentos obrigatórios encontrados")
            return response.data
        else:
            logger.info(f"❌ Nenhum tipo de documento obrigatório encontrado")
            return []
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar documentos obrigatórios: {str(e)}")
        return []

def obter_sequencia_coleta_documentos() -> List[dict]:
    """
    Obtém a sequência dinâmica de documentos obrigatórios para coleta
    Busca no Supabase e retorna lista ordenada com fallback
    
    Returns:
        List[dict]: Lista de documentos com nome e descrição, ordenados para coleta
    """
    try:
        # Buscar documentos obrigatórios do Supabase
        documentos = buscar_documentos_obrigatorios()
        
        # Se não encontrar no Supabase, usar fallback
        if not documentos:
            logger.warning("⚠️ Nenhum documento obrigatório encontrado no Supabase. Usando lista fallback.")
            documentos = [
                {"name": "Comprovante de Residência", "description": "Conta de luz, água ou telefone"},
                {"name": "Comprovante de Renda", "description": "Últimos 3 holerites ou declaração de renda"},
                {"name": "Certidão de Nascimento/Casamento", "description": "Estado civil"},
                {"name": "RG / CNH", "description": "Documento de identidade"}
            ]
        
        # Logar a sequência no terminal
        logger.info("📋 SEQUÊNCIA DE COLETA DE DOCUMENTOS:")
        logger.info("=" * 50)
        for i, doc in enumerate(documentos, 1):
            logger.info(f"{i}. {doc['name']}")
            if doc.get('description'):
                logger.info(f"   📝 {doc['description']}")
            logger.info("")
        
        logger.info(f"✅ Total de documentos na sequência: {len(documentos)}")
        logger.info("=" * 50)
        
        return documentos
        
    except Exception as e:
        logger.error(f"❌ Erro ao obter sequência de documentos: {str(e)}")
        # Retornar fallback em caso de erro
        logger.warning("🔄 Usando lista fallback devido a erro")
        return [
            {"name": "Comprovante de Residência", "description": "Conta de luz, água ou telefone"},
            {"name": "Comprovante de Renda", "description": "Últimos 3 holerites ou declaração de renda"},
            {"name": "Certidão de Nascimento/Casamento", "description": "Estado civil"},
            {"name": "RG / CNH", "description": "Documento de identidade"}
        ]

def criar_mensagem_documentos_obrigatorios() -> str:
    """
    Cria mensagem formatada com lista de documentos obrigatórios
    
    Returns:
        str: Mensagem formatada com lista de documentos obrigatórios
    """
    try:
        documentos = buscar_documentos_obrigatorios()
        
        if not documentos:
            logger.warning("⚠️ Nenhum documento obrigatório encontrado")
            return "❌ Erro: Não foi possível carregar a lista de documentos obrigatórios."
        
        mensagem = "📄 *DOCUMENTOS OBRIGATÓRIOS*\n\n"
        mensagem += "Ótimo! Vamos iniciar o Fluxo de Coleta de Documentos.\n\n"
        mensagem += "Os documentos obrigatórios são:\n\n"
        
        for i, doc in enumerate(documentos, 1):
            mensagem += f"{i}. *{doc['name']}*\n"
            if doc.get('description'):
                mensagem += f"   {doc['description']}\n"
            mensagem += "\n"
        
        mensagem += "⚠️ *IMPORTANTE:* Todos os documentos devem estar em formato PDF.\n\n"
        mensagem += "Envie um documento por vez. Vou te guiar durante todo o processo! 📋"
        
        logger.info(f"✅ Mensagem de documentos criada com {len(documentos)} documentos")
        return mensagem
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar mensagem de documentos: {str(e)}")
        return "❌ Erro ao carregar lista de documentos. Tente novamente."

def buscar_documentos_recebidos(negotiation_id: str) -> List[dict]:
    """
    Busca documentos já recebidos para uma negociação (com cache)
    """
    global _cache_memoria
    
    cache_key = f"documentos_recebidos_{negotiation_id}"
    if cache_key in _cache_memoria:
        logger.info(f"💾 Cache encontrado para: {cache_key}")
        return _cache_memoria[cache_key]
    
    try:
        supabase = obter_cliente_supabase()
        
        response = supabase.table('ai_documents').select(
            '*, ai_document_types(name, description)'
        ).eq('negotiation_id', negotiation_id).execute()
        
        if response.data:
            _cache_memoria[cache_key] = response.data
            logger.info(f"💾 Cache definido para: {cache_key}")
            logger.info(f"✅ {len(response.data)} documentos recebidos encontrados")
            return response.data
        else:
            logger.info(f"❌ Nenhum documento recebido encontrado")
            return []
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar documentos recebidos: {str(e)}")
        return []

def analisar_documentos_faltantes(negotiation_id: str) -> dict:
    """
    Analisa quais documentos estão faltando para uma negociação
    """
    try:
        documentos_obrigatorios = buscar_documentos_obrigatorios()
        documentos_recebidos = buscar_documentos_recebidos(negotiation_id)
        
        # IDs dos documentos já recebidos
        ids_recebidos = {doc['document_type_id'] for doc in documentos_recebidos}
        
        # Documentos faltantes
        documentos_faltantes = [
            doc for doc in documentos_obrigatorios 
            if doc['id'] not in ids_recebidos
        ]
        
        resultado = {
            "total_obrigatorios": len(documentos_obrigatorios),
            "total_recebidos": len(documentos_recebidos),
            "total_faltantes": len(documentos_faltantes),
            "documentos_faltantes": documentos_faltantes,
            "documentos_recebidos": documentos_recebidos,
            "progresso_percentual": (len(documentos_recebidos) / len(documentos_obrigatorios)) * 100 if documentos_obrigatorios else 0
        }
        
        logger.info(f"✅ Análise de documentos concluída: {resultado['total_recebidos']}/{resultado['total_obrigatorios']} documentos ({resultado['progresso_percentual']:.1f}%)")
        
        return resultado

    except Exception as e:
        logger.error(f"❌ Erro ao analisar documentos faltantes: {str(e)}")
        return {
            "total_obrigatorios": 0,
            "total_recebidos": 0,
            "total_faltantes": 0,
            "documentos_faltantes": [],
            "documentos_recebidos": [],
            "progresso_percentual": 0
        }

def buscar_conversas_ia_cliente_enriquecidas(negotiation_id: str, limite: int = None) -> List[dict]:
    """
    Busca conversas entre IA e cliente com dados enriquecidos e contextuais
    """
    global _cache_memoria
    
    cache_key = f"conversas_{negotiation_id}_{limite or 'todas'}"
    if cache_key in _cache_memoria:
        logger.info(f"💾 Cache encontrado para: {cache_key}")
        return _cache_memoria[cache_key]
    
    try:
        supabase = obter_cliente_supabase()
        
        query = supabase.table('ai_conversations').select('*').eq(
            'negotiation_id', negotiation_id
        ).eq('conversation_type', 'ia_cliente').order('timestamp')
        
        if limite:
            query = query.limit(limite)
        
        response = query.execute()
        
        if response.data:
            conversas = response.data
            
            # Enriquecer conversas com contexto
            for i, conversa in enumerate(conversas):
                conversa['contexto'] = {
                    'eh_primeira': i == 0,
                    'eh_ultima': i == len(conversas) - 1,
                    'posicao': i + 1,
                    'total_conversas': len(conversas),
                    'tempo_desde_anterior': None
                }
                
                # Calcular tempo desde conversa anterior
                if i > 0:
                    from datetime import datetime
                    atual = datetime.fromisoformat(conversa['timestamp'].replace('Z', '+00:00'))
                    anterior = datetime.fromisoformat(conversas[i-1]['timestamp'].replace('Z', '+00:00'))
                    conversa['contexto']['tempo_desde_anterior'] = (atual - anterior).total_seconds()
            
            _cache_memoria[cache_key] = conversas
            logger.info(f"💾 Cache definido para: {cache_key}")
            logger.info(f"✅ {len(conversas)} conversas IA-Cliente encontradas e enriquecidas")
            return conversas
        else:
            logger.info(f"❌ Nenhuma conversa IA-Cliente encontrada")
            return []
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar conversas IA-Cliente: {str(e)}")
        return []

def buscar_conversas_ia_cliente(negotiation_id: str) -> List[dict]:
    """
    Busca todas as conversas entre IA e cliente para uma negociação (mantém compatibilidade)
    """
    return buscar_conversas_ia_cliente_enriquecidas(negotiation_id)

def analisar_conversas_com_gpt(conversas: List[dict], documentos_analise: dict) -> dict:
    """
    Analisa conversas e documentos usando o OpenAIService
    MELHORADA com contexto enriquecido das novas colunas CPF
    """
    try:
        from .openai_service import OpenAIService
        
        # MELHORIA: Usar OpenAIService para análise real com GPT-4
        openai_service = OpenAIService()
        return openai_service.analisar_conversas_com_gpt(conversas, documentos_analise)
        
    except Exception as e:
        logger.error(f"❌ Erro ao analisar conversas com GPT: {str(e)}")
        return {
            "resumo": f"Erro na análise: {str(e)}",
            "proxima_mensagem": "Vou analisar sua situação e retorno em breve. Obrigado pela paciência!",
            "contexto": "erro_analise"
        }

def processar_cliente_completo(cpf: str, telefone: str = None) -> dict:
    """
    Processa cliente completo: verifica cadastro, negociações, documentos e análise GPT
    """
    try:
        # 1. Buscar dados unificados primeiro (nova funcionalidade)
        dados_unificados = buscar_dados_unificados_por_cpf(cpf)
        
        # 2. Verificar se é cliente cadastrado
        cliente = dados_unificados.get('cliente')
        
        if not cliente:
            return {
                "tipo": "cliente",
                "cliente_cadastrado": False,
                "mensagem": "Olá! Seu CPF não está em nossa base de clientes cadastrados. Vou transferir você para um corretor para iniciar seu cadastro."
            }
        
        # 3. Usar telefone do cliente ou o informado
        telefone_busca = telefone or cliente.get('telefone')
        
        if not telefone_busca:
            return {
                "tipo": "cliente",
                "cliente_cadastrado": True,
                "dados_cliente": cliente,
                "mensagem": f"Olá {cliente['nome']}! Seu cadastro foi encontrado, mas preciso do seu telefone para verificar negociações em andamento."
            }
        
        # 4. Buscar negociação ativa (versão melhorada)
        negociacao = buscar_negociacao_ativa(telefone_busca, cpf)
        
        if not negociacao:
            return {
                "tipo": "cliente",
                "cliente_cadastrado": True,
                "dados_cliente": cliente,
                "negociacao_ativa": False,
                "dados_unificados": {
                    "multiplas_negociacoes": dados_unificados.get('multiplas_negociacoes', False),
                    "total_negociacoes_ativas": dados_unificados.get('total_negociacoes_ativas', 0),
                    "documentos_por_cpf": dados_unificados.get('documentos_por_cpf', 0),
                    "ultima_interacao": dados_unificados.get('ultima_interacao')
                },
                "mensagem": f"Olá {cliente['nome']}! Não encontrei negociações em andamento. Posso ajudar você a iniciar uma nova negociação?"
            }
        
        # 5. Analisar documentos
        analise_docs = analisar_documentos_faltantes(negociacao['id'])
        
        # 6. Buscar conversas
        conversas = buscar_conversas_ia_cliente(negociacao['id'])
        
        # 7. Analisar com GPT (versão corrigida)
        analise_gpt = analisar_conversas_com_gpt(conversas, analise_docs)
        
        # 8. Montar resposta completa
        return {
            "tipo": "cliente",
            "cliente_cadastrado": True,
            "dados_cliente": cliente,
            "negociacao_ativa": True,
            "dados_negociacao": negociacao,
            "analise_documentos": analise_docs,
            "total_conversas": len(conversas),
            "analise_gpt": analise_gpt,
            "dados_unificados": {
                "multiplas_negociacoes": dados_unificados.get('multiplas_negociacoes', False),
                "total_negociacoes_ativas": dados_unificados.get('total_negociacoes_ativas', 0),
                "documentos_por_cpf": dados_unificados.get('documentos_por_cpf', 0),
                "ultima_interacao": dados_unificados.get('ultima_interacao')
            },
            "mensagem": f"Olá {cliente['nome']}! {analise_gpt['proxima_mensagem']}"
        }
        
    except Exception as e:
        logger.error(f"❌ Erro no processamento completo do cliente: {str(e)}")
        return {
            "tipo": "cliente",
            "cliente_cadastrado": False,
            "mensagem": "Desculpe, tive um problema ao verificar suas informações. Por favor, tente novamente em alguns instantes."
        }

def identificar_tipo_usuario(cpf: str, telefone: str = None) -> dict:
    """
    Identifica se o CPF pertence a um colaborador ou cliente
    Versão expandida com análise completa para clientes
    
    Args:
        cpf (str): CPF para verificar (pode conter pontos e traços)
        telefone (str, optional): Telefone do cliente para buscar negociações
        
    Returns:
        dict: Dicionário com informações completas do usuário
    """
    logger.info(f"🔍 Iniciando identificação de usuário para CPF: {cpf[:3]}***")
    
    try:
        # 1. VALIDAÇÃO E FORMATAÇÃO DO CPF
        logger.info("📋 Validando e formatando CPF...")
        validacao = validar_formatar_cpf(cpf)
        if not validacao["valido"]:
            logger.warning(f"❌ CPF inválido: {validacao['mensagem']}")
            return {
                "tipo": "invalido",
                "cpf_valido": False,
                "dados_usuario": None,
                "mensagem": validacao["mensagem"],
                "debug": {
                    "etapa": "validacao_cpf",
                    "erro": validacao["mensagem"]
                }
            }
        
        logger.info(f"✅ CPF válido - formatado: {validacao['cpf_formatado']}")
        
        # 2. BUSCA UNIFICADA PRIMEIRO (nova funcionalidade)
        dados_unificados = buscar_dados_unificados_por_cpf(validacao["cpf_formatado"])
        
        # 3. VERIFICAR SE É COLABORADOR
        colaborador = dados_unificados.get('colaborador')
        
        if colaborador:
            logger.info("👤 Processando dados do colaborador...")
            
            # Tratamento robusto do setor
            nome_setor = "Não informado"
            try:
                company_sectors = colaborador.get('company_sectors')
                logger.info(f"📊 Dados do setor: {type(company_sectors)} - {company_sectors}")
                
                if company_sectors:
                    if isinstance(company_sectors, list) and len(company_sectors) > 0:
                        primeiro_setor = company_sectors[0]
                        if isinstance(primeiro_setor, dict):
                            nome_setor = primeiro_setor.get('name', 'Não informado')
                    elif isinstance(company_sectors, dict):
                        nome_setor = company_sectors.get('name', 'Não informado')
                
                logger.info(f"🏢 Setor identificado: {nome_setor}")
                
            except Exception as e_setor:
                logger.warning(f"⚠️ Erro ao processar setor: {str(e_setor)}")
                nome_setor = "Erro ao carregar setor"
            
            # Preparar dados do colaborador
            dados_usuario = {
                "id": colaborador.get('id'),
                "nome": colaborador.get('full_name') or "Nome não informado",
                "email": colaborador.get('email') or "Email não informado", 
                "username": colaborador.get('username') or "Username não informado",
                "setor": nome_setor,
                "funcao": colaborador.get('role') or "Função não informada",
                "ativo": colaborador.get('is_active', False),
                "criado_em": colaborador.get('created_at')
            }
            
            # Verificar se colaborador está ativo
            if not dados_usuario["ativo"]:
                logger.warning("⚠️ Colaborador encontrado mas está inativo")
                return {
                    "tipo": "colaborador_inativo",
                    "cpf_valido": True,
                    "dados_usuario": dados_usuario,
                    "mensagem": f"Olá {dados_usuario['nome']}! Seu acesso está temporariamente desativado. Entre em contato com o administrador."
                }
            
            # Montar mensagem personalizada para colaborador
            mensagem = (
                f"Olá {dados_usuario['nome']}! 👋\n"
                f"✅ Acesso autorizado como Colaborador da Toca Imóveis\n"
                f"Setor: {dados_usuario['setor']}"
            )
            
            logger.info("✅ Colaborador processado com sucesso")
            return {
                "tipo": "colaborador",
                "cpf_valido": True,
                "dados_usuario": dados_usuario,
                "mensagem": mensagem,
                "debug": {
                    "etapa": "colaborador_encontrado",
                    "setor_raw": colaborador.get('company_sectors'),
                    "setor_processado": nome_setor
                }
            }
        
        # 4. PROCESSAR COMO CLIENTE
        logger.info("👥 Não é colaborador - processando como cliente...")
        
        try:
            resultado_cliente = processar_cliente_completo(validacao["cpf_formatado"], telefone)
            
            # Adicionar informações de debug
            resultado_cliente["debug"] = {
                "etapa": "cliente_processado",
                "cpf_formatado": validacao["cpf_formatado"],
                "telefone_informado": telefone is not None,
                "dados_unificados_disponiveis": dados_unificados is not None,
                "total_negociacoes_encontradas": len(dados_unificados.get('negociacoes', [])),
                "total_documentos_encontrados": len(dados_unificados.get('documentos', []))
            }
            
            logger.info("✅ Cliente processado com sucesso")
            return resultado_cliente
            
        except Exception as e_cliente:
            logger.error(f"❌ Erro ao processar cliente: {str(e_cliente)}")
            return {
                "tipo": "erro",
                "cpf_valido": True,
                "dados_usuario": None,
                "mensagem": "Encontrei um problema ao verificar suas informações de cliente. Vou transferir você para um atendente humano.",
                "debug": {
                    "etapa": "erro_cliente",
                    "erro": str(e_cliente)
                }
            }
            
    except Exception as e_geral:
        logger.error(f"❌ Erro geral ao identificar tipo de usuário: {str(e_geral)}")
        logger.error(f"❌ Tipo do erro: {type(e_geral).__name__}")
        logger.error(f"❌ Detalhes: {str(e_geral)}")
        
        return {
            "tipo": "erro",
            "cpf_valido": False,
            "dados_usuario": None,
            "mensagem": "Desculpe, tive um problema técnico ao verificar seu CPF. Nossa equipe já foi notificada. Tente novamente em alguns instantes.",
            "debug": {
                "etapa": "erro_geral",
                "tipo_erro": type(e_geral).__name__,
                "erro": str(e_geral),
                "cpf_recebido": cpf[:3] + "***" if cpf else "None"
            }
        }


