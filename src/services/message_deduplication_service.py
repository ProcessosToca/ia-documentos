# Message Deduplication Service
# Serviço para controle de mensagens duplicadas no WhatsApp

import os
import logging
from datetime import datetime, timedelta
import hashlib
from typing import Dict, Optional, Any, Tuple

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageDeduplicationService:
    """
    Serviço para controle e prevenção de mensagens duplicadas no WhatsApp
    
    Responsável por:
    - Detectar e prevenir mensagens duplicadas
    - Considerar contexto da conversa
    - Manter cache com expiração
    - Logging detalhado
    
    Autor: Sistema IA Toca Imóveis
    Data: Julho/2025
    """
    
    def __init__(self):
        """
        Inicializa o serviço de deduplicação
        """
        # Cache de mensagens: {hash: (timestamp, conteúdo)}
        self.message_cache: Dict[str, Tuple[datetime, str]] = {}
        
        # Configurações
        self.cache_duration = timedelta(minutes=5)  # 5 minutos de cache
        self.enabled = True
        
        logger.info("✅ MessageDeduplicationService inicializado")
    
    def _generate_message_hash(self, content: str, recipient: str, 
                             context: Optional[Dict[str, Any]] = None) -> str:
        """
        Gera hash único para a mensagem
        
        Args:
            content: Conteúdo da mensagem
            recipient: Número do destinatário
            context: Contexto adicional (fase da conversa, etc)
            
        Returns:
            str: Hash MD5 da mensagem
        """
        try:
            # Truncar conteúdo muito longo
            content_truncated = content[:100] if content else ""
            
            # Base do hash: conteúdo + destinatário
            base_data = f"{recipient}:{content_truncated}"
            
            # Adicionar contexto se existir
            if context:
                context_str = str(sorted(context.items()))
                base_data = f"{base_data}:{context_str}"
            
            return hashlib.md5(base_data.encode()).hexdigest()
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar hash: {e}")
            return ""
    
    def _clean_expired_messages(self):
        """
        Remove mensagens expiradas do cache
        """
        try:
            now = datetime.now()
            expired_keys = [
                key for key, (timestamp, _) in self.message_cache.items()
                if (now - timestamp) > self.cache_duration
            ]
            
            for key in expired_keys:
                del self.message_cache[key]
                
            if expired_keys:
                logger.info(f"🧹 Cache limpo: {len(expired_keys)} mensagens removidas")
                
        except Exception as e:
            logger.error(f"❌ Erro na limpeza do cache: {e}")
    
    def is_duplicate(self, content: str, recipient: str, 
                    context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Verifica se uma mensagem é duplicada
        
        Args:
            content: Conteúdo da mensagem
            recipient: Número do destinatário
            context: Contexto adicional (fase da conversa, etc)
            
        Returns:
            bool: True se for duplicada, False caso contrário
        """
        try:
            if not self.enabled:
                return False
            
            # Limpar mensagens antigas
            self._clean_expired_messages()
            
            # Gerar hash da mensagem
            message_hash = self._generate_message_hash(content, recipient, context)
            if not message_hash:
                return False
            
            # Verificar no cache
            if message_hash in self.message_cache:
                timestamp, _ = self.message_cache[message_hash]
                
                # Verificar se ainda não expirou
                if (datetime.now() - timestamp) <= self.cache_duration:
                    logger.info(f"🔄 Mensagem duplicada detectada para: {recipient}")
                    return True
            
            # Não é duplicada - registrar no cache
            self.message_cache[message_hash] = (datetime.now(), content)
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar duplicação: {e}")
            return False  # Em caso de erro, permite o envio
    
    def clear_cache(self):
        """
        Limpa todo o cache manualmente
        """
        try:
            cache_size = len(self.message_cache)
            self.message_cache.clear()
            logger.info(f"🧹 Cache limpo manualmente: {cache_size} mensagens removidas")
        except Exception as e:
            logger.error(f"❌ Erro ao limpar cache: {e}")