import os
from supabase import create_client, Client
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validar_formatar_cpf(cpf: str) -> dict:
    """
    Valida e formata um CPF
    
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

def buscar_usuario_por_cpf(cpf):
    """
    Função específica para buscar usuário pelo CPF
    """
    SUPABASE_URL = "https://rqyyoofuwrwwfcuxfjwu.supabase.co"
    SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxeXlvb2Z1d3J3d2ZjdXhmand1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTAwODk2MjUsImV4cCI6MjA2NTY2NTYyNX0.lBOrYvRIGEhLLMgcaaooS9-w2M8VAZW_4rQYFxc6abE"
    
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Formatar CPF com pontos e traços
        cpf_formatado = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
        
        # Primeiro tenta buscar com CPF formatado
        response = supabase.table('system_users').select('*').eq('cpf', cpf_formatado).execute()
        
        # Se não encontrar, tenta com CPF sem formatação
        if not response.data:
            cpf_limpo = ''.join(filter(str.isdigit, cpf))
            response = supabase.table('system_users').select('*').eq('cpf', cpf_limpo).execute()
        
        if response.data:
            logger.info(f"✅ Usuário encontrado no banco")
            return response.data[0]  # Retorna o primeiro usuário encontrado
        else:
            logger.info(f"❌ Usuário não encontrado no banco")
            return None
            
    except Exception as e:
        logger.error(f"❌ Erro ao buscar usuário por CPF: {str(e)}")
        return None

def identificar_tipo_usuario(cpf: str) -> dict:
    """
    Identifica se o CPF pertence a um colaborador ou cliente
    
    Args:
        cpf (str): CPF para verificar (pode conter pontos e traços)
        
    Returns:
        dict: Dicionário com:
            - tipo: "colaborador" ou "cliente"
            - cpf_valido: True/False
            - dados_usuario: Dados do usuário se for colaborador
            - mensagem: Mensagem formatada para resposta
    """
    try:
        # Validar e formatar CPF
        validacao = validar_formatar_cpf(cpf)
        if not validacao["valido"]:
            return {
                "tipo": "invalido",
                "cpf_valido": False,
                "dados_usuario": None,
                "mensagem": validacao["mensagem"]
            }
        
        # Buscar usuário no Supabase
        usuario = buscar_usuario_por_cpf(validacao["cpf_limpo"])
        
        if usuario:
            logger.info(f"✅ CPF identificado como colaborador")
            
            # Preparar dados do usuário
            dados_usuario = {
                "nome": usuario.get('full_name'),
                "email": usuario.get('email'),
                "setor": usuario.get('sector_id'),
                "funcao": usuario.get('role')
            }
            
            # Montar mensagem personalizada para colaborador
            mensagem = (
                f"Olá {dados_usuario['nome']}! "
                f"Obrigado por enviar seu CPF.\n"
                f"Você é um Colaborador da Toca Imóveis.\n"
                f"Setor: {dados_usuario['setor']}"
            )
            
            return {
                "tipo": "colaborador",
                "cpf_valido": True,
                "dados_usuario": dados_usuario,
                "mensagem": mensagem
            }
        else:
            logger.info(f"✅ CPF identificado como cliente")
            return {
                "tipo": "cliente",
                "cpf_valido": True,
                "dados_usuario": None,
                "mensagem": f"Olá! Obrigado por enviar seu CPF. Você é um Cliente"
            }
            
    except Exception as e:
        logger.error(f"❌ Erro ao identificar tipo de usuário: {str(e)}")
        return {
            "tipo": "erro",
            "cpf_valido": False,
            "dados_usuario": None,
            "mensagem": "Desculpe, tive um problema ao verificar seu CPF. Por favor, tente novamente."
        }
