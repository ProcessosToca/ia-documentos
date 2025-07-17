import time
from typing import Dict, Any, Optional
import logging

# Configuração de logging
logger = logging.getLogger(__name__)

class SessionManager:
    """
    Gerenciador de sessões ativas do sistema
    
    RESPONSABILIDADES:
    =================
    - Gestão de sessões de IA especializada
    - Controle de timeouts automáticos
    - Verificação de sessões ativas
    - Limpeza automática de sessões expiradas
    
    TIPOS DE SESSÃO SUPORTADOS:
    ===========================
    - ia_especializada: Sessão de dúvidas técnicas para colaboradores
    - [FUTURO] coleta_dados: Sessão de coleta de dados
    - [FUTURO] atendimento: Sessão de atendimento a clientes
    
    BENEFÍCIOS DA SEPARAÇÃO:
    =======================
    - Gestão centralizada de estado
    - Controle preciso de timeouts
    - Fácil adição de novos tipos de sessão
    - Logs específicos para debugging
    - Menor complexidade no código principal
    
    VERSÃO: 1.0
    EXTRAÍDO DE: WhatsAppService DATA: JUlho/2025
    """
    
    def __init__(self, timeout_sessao: int = 30 * 60):
        """
        Inicializar gerenciador de sessões
        
        Args:
            timeout_sessao (int): Timeout padrão em segundos (padrão: 30 minutos)
        """
        # Dicionário para armazenar sessões ativas
        # Formato: {telefone: {"tipo": str, "dados": dict, "ativado_em": float, "expira_em": float, "ultima_atividade": float}}
        self.sessoes_ativas = {}
        
        # Timeout padrão para sessões
        self.TIMEOUT_SESSAO = timeout_sessao
        
        logger.info(f"SessionManager inicializado com timeout de {timeout_sessao/60:.1f} minutos")

    def criar_sessao(self, telefone: str, tipo_sessao: str, dados_sessao: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Criar uma nova sessão ativa
        
        Args:
            telefone (str): Número do telefone do usuário
            tipo_sessao (str): Tipo da sessão ("ia_especializada", etc.)
            dados_sessao (Dict, optional): Dados específicos da sessão
            
        Returns:
            Dict: Resultado da criação da sessão
        """
        try:
            agora = time.time()
            
            # Criar sessão
            self.sessoes_ativas[telefone] = {
                "tipo": tipo_sessao,
                "dados": dados_sessao or {},
                "ativado_em": agora,
                "expira_em": agora + self.TIMEOUT_SESSAO,
                "ultima_atividade": agora
            }
            
            logger.info(f"✅ Sessão '{tipo_sessao}' criada para {telefone} (expira em {self.TIMEOUT_SESSAO/60:.1f}min)")
            
            return {
                "sucesso": True,
                "tipo_sessao": tipo_sessao,
                "telefone": telefone,
                "expira_em": self.sessoes_ativas[telefone]["expira_em"],
                "timeout_minutos": self.TIMEOUT_SESSAO / 60
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar sessão: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e)
            }

    def sessao_ativa(self, telefone: str) -> bool:
        """
        Verifica se existe uma sessão ativa para o telefone e se não expirou
        
        Args:
            telefone (str): Número do telefone do usuário
            
        Returns:
            bool: True se sessão ativa, False se não existe ou expirou
        """
        try:
            if telefone not in self.sessoes_ativas:
                return False
            
            sessao = self.sessoes_ativas[telefone]
            agora = time.time()
            
            # Verificar se expirou
            if agora > sessao["expira_em"]:
                # Sessão expirada, remover
                tipo_sessao = sessao.get("tipo", "desconhecida")
                logger.info(f"🕐 Sessão '{tipo_sessao}' expirada para {telefone}")
                del self.sessoes_ativas[telefone]
                return False
            
            # Atualizar última atividade
            sessao["ultima_atividade"] = agora
            logger.debug(f"✅ Sessão ativa confirmada para {telefone}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar sessão: {str(e)}")
            return False

    def obter_dados_sessao(self, telefone: str) -> Optional[Dict[str, Any]]:
        """
        Obter dados de uma sessão ativa
        
        Args:
            telefone (str): Número do telefone do usuário
            
        Returns:
            Optional[Dict]: Dados da sessão ou None se não existir/expirada
        """
        try:
            if not self.sessao_ativa(telefone):
                return None
            
            return self.sessoes_ativas[telefone].copy()
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter dados da sessão: {str(e)}")
            return None

    def atualizar_dados_sessao(self, telefone: str, novos_dados: Dict[str, Any]) -> bool:
        """
        Atualizar dados de uma sessão existente
        
        Args:
            telefone (str): Número do telefone do usuário
            novos_dados (Dict): Novos dados para a sessão
            
        Returns:
            bool: True se atualizado com sucesso, False caso contrário
        """
        try:
            if not self.sessao_ativa(telefone):
                logger.warning(f"⚠️ Tentativa de atualizar sessão inexistente: {telefone}")
                return False
            
            # Atualizar dados mantendo metadados de controle
            self.sessoes_ativas[telefone]["dados"].update(novos_dados)
            self.sessoes_ativas[telefone]["ultima_atividade"] = time.time()
            
            logger.debug(f"✅ Dados da sessão atualizados para {telefone}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar dados da sessão: {str(e)}")
            return False

    def encerrar_sessao(self, telefone: str, motivo: str = "encerramento_manual") -> Dict[str, Any]:
        """
        Encerrar uma sessão ativa
        
        Args:
            telefone (str): Número do telefone do usuário
            motivo (str): Motivo do encerramento
            
        Returns:
            Dict: Resultado do encerramento
        """
        try:
            if telefone not in self.sessoes_ativas:
                return {
                    "sucesso": False,
                    "motivo": "sessao_nao_encontrada"
                }
            
            # Obter dados antes de remover
            sessao = self.sessoes_ativas[telefone]
            tipo_sessao = sessao.get("tipo", "desconhecida")
            duracao = time.time() - sessao.get("ativado_em", 0)
            
            # Remover sessão
            del self.sessoes_ativas[telefone]
            
            logger.info(f"🔚 Sessão '{tipo_sessao}' encerrada para {telefone} - Motivo: {motivo} - Duração: {duracao/60:.1f}min")
            
            return {
                "sucesso": True,
                "tipo_sessao": tipo_sessao,
                "motivo": motivo,
                "duracao_segundos": duracao,
                "duracao_minutos": duracao / 60
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao encerrar sessão: {str(e)}")
            return {
                "sucesso": False,
                "erro": str(e)
            }

    def listar_sessoes_ativas(self) -> Dict[str, Any]:
        """
        Listar todas as sessões ativas (para debugging/monitoramento)
        
        Returns:
            Dict: Informações sobre sessões ativas
        """
        try:
            # Limpar sessões expiradas primeiro
            self._limpar_sessoes_expiradas()
            
            sessoes_info = {}
            agora = time.time()
            
            for telefone, sessao in self.sessoes_ativas.items():
                tempo_restante = sessao["expira_em"] - agora
                sessoes_info[telefone] = {
                    "tipo": sessao["tipo"],
                    "tempo_restante_minutos": max(0, tempo_restante / 60),
                    "ativa_desde": sessao["ativado_em"],
                    "ultima_atividade": sessao["ultima_atividade"]
                }
            
            return {
                "total_sessoes": len(sessoes_info),
                "sessoes": sessoes_info,
                "timestamp_consulta": agora
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao listar sessões: {str(e)}")
            return {
                "total_sessoes": 0,
                "sessoes": {},
                "erro": str(e)
            }

    def _limpar_sessoes_expiradas(self) -> int:
        """
        Limpar sessões expiradas (método interno)
        
        Returns:
            int: Número de sessões removidas
        """
        try:
            agora = time.time()
            telefones_expirados = []
            
            # Identificar sessões expiradas
            for telefone, sessao in self.sessoes_ativas.items():
                if agora > sessao["expira_em"]:
                    telefones_expirados.append(telefone)
            
            # Remover sessões expiradas
            for telefone in telefones_expirados:
                tipo_sessao = self.sessoes_ativas[telefone].get("tipo", "desconhecida")
                del self.sessoes_ativas[telefone]
                logger.info(f"🗑️ Sessão '{tipo_sessao}' removida por expiração: {telefone}")
            
            if telefones_expirados:
                logger.info(f"🧹 Limpeza automática: {len(telefones_expirados)} sessões expiradas removidas")
            
            return len(telefones_expirados)
            
        except Exception as e:
            logger.error(f"❌ Erro na limpeza automática: {str(e)}")
            return 0

    def criar_sessao_ia_especializada(self, telefone: str, dados_colaborador: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Método específico para criar sessão de IA especializada (compatibilidade)
        
        Args:
            telefone (str): Número do telefone do colaborador
            dados_colaborador (Dict, optional): Dados do colaborador
            
        Returns:
            Dict: Resultado da criação da sessão
        """
        return self.criar_sessao(
            telefone=telefone,
            tipo_sessao="ia_especializada",
            dados_sessao={"dados_colaborador": dados_colaborador}
        ) 