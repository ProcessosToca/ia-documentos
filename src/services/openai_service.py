import os
from openai import OpenAI
from typing import Dict, Any
import logging
import json

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIService:
    """Serviço para integração com OpenAI"""
    
    def __init__(self):
        # Configurar cliente OpenAI
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
    def interpretar_mensagem(self, mensagem: str) -> Dict[str, Any]:
        """
        Interpreta a mensagem do usuário usando OpenAI
        
        Args:
            mensagem (str): Mensagem do usuário
            
        Returns:
            Dict: Resultado da interpretação com campos:
                - cpf: CPF encontrado ou None
                - novo_usuario: True se for saudação/primeiro contato, False caso contrário
                - solicitar_cpf: True se precisa solicitar CPF
                - mensagem_resposta: Mensagem para enviar ao usuário
        """
        try:
            # Prompt para a OpenAI
            prompt = f"""Como uma Corretora de Locação, analise a mensagem do cliente:

            Mensagem: {mensagem}

            1. Identifique se é uma saudação ou primeiro contato
            2. Procure por um CPF na mensagem
            3. Determine a próxima ação apropriada

            Retorne apenas um objeto JSON com:
            - cpf: número do CPF se encontrado (apenas números), ou null se não encontrado
            - novo_usuario: true se for saudação/primeiro contato, false caso contrário
            - solicitar_cpf: true se não encontrou CPF ou false se encontrou
            - mensagem_resposta: mensagem apropriada para o cliente:
              - Se for novo usuário: enviar primeira mensagem padrão
              - Se encontrou CPF: apenas confirmar "Olá! Confirmo o recebimento do CPF [CPF formatado]."
              - Se não encontrou CPF: solicitar gentilmente
            """
            
            # Fazer chamada para OpenAI com nova sintaxe
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": """Você é uma Corretora de Locação profissional e eficiente.
                        Seu objetivo é identificar informações importantes para o processo de locação.
                        Mantenha um tom profissional e direto.
                        Para novos usuários, apresente-se como Bia e solicite o CPF.
                        Para confirmação de CPF, apenas confirme o recebimento sem perguntas adicionais.
                        """
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=200
            )
            
            # Extrair resposta
            resultado = json.loads(response.choices[0].message.content)
            logger.info("🤖 Interpretação concluída")
            
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Erro ao interpretar mensagem: {str(e)}")
            return {
                "cpf": None,
                "novo_usuario": False,
                "solicitar_cpf": True,
                "mensagem_resposta": "Por favor, me envie seu CPF (apenas números) para continuarmos o atendimento."
            } 