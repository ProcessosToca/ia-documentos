import os
from openai import OpenAI
from typing import Dict, Any, List
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

    def analisar_conversas_com_gpt(self, conversas: List[dict], documentos_analise: dict) -> dict:
        """
        Analisa o histórico de conversas e documentos de uma negociação usando GPT-4 para gerar uma resposta contextual.
        
        Args:
            conversas (List[dict]): Lista de conversas anteriores, cada uma com:
                - sender: 'ia' ou 'user'
                - message: texto da mensagem
                - timestamp: quando foi enviada
            documentos_analise (dict): Análise dos documentos da negociação com:
                - total_obrigatorios: número total de documentos necessários
                - total_recebidos: número de documentos já recebidos
                - total_faltantes: número de documentos pendentes
                - documentos_faltantes: lista de documentos que faltam
                - progresso_percentual: % de conclusão
                
        Returns:
            dict: Resultado da análise com:
                - resumo: Resumo do contexto atual da conversa
                - proxima_mensagem: Texto sugerido para próxima mensagem
                - contexto: Situação atual (ex: "aguardando_documentos", "documentos_completos")
                
        Exemplo:
            >>> conversas = [
                    {"sender": "user", "message": "Bom dia, enviei o RG"},
                    {"sender": "ia", "message": "Recebi! Falta comprovante de renda"}
                ]
            >>> docs = {
                    "total_obrigatorios": 3,
                    "total_recebidos": 1,
                    "documentos_faltantes": [{"name": "Comprovante de Renda"}]
                }
            >>> resultado = analisar_conversas_com_gpt(conversas, docs)
            >>> print(resultado["proxima_mensagem"])
            "Por favor, envie seu comprovante de renda para continuarmos."
        """
        try:
            # Preparar histórico de conversas para análise
            historico = []
            for conversa in conversas:
                papel = "assistant" if conversa['sender'] == 'ia' else "user"
                historico.append(f"{papel.upper()}: {conversa['message']}")
            
            # Validação e acesso seguro aos dados de documentos
            total_obrigatorios = documentos_analise.get('total_obrigatorios', 0)
            total_recebidos = documentos_analise.get('total_recebidos', 0)
            total_faltantes = documentos_analise.get('total_faltantes', 0)
            progresso_percentual = documentos_analise.get('progresso_percentual', 0.0)
            documentos_faltantes = documentos_analise.get('documentos_faltantes', [])
            documentos_recebidos = documentos_analise.get('documentos_recebidos', [])
            
            logger.info(f"📊 Analisando: {total_recebidos}/{total_obrigatorios} documentos ({progresso_percentual:.1f}%)")
            
            # Preparar lista de documentos faltantes de forma segura
            docs_faltantes_lista = []
            for doc in documentos_faltantes:
                nome = doc.get('name', 'Documento não identificado')
                descricao = doc.get('description', 'Sem descrição')
                docs_faltantes_lista.append(f"📄 **{nome}** - {descricao}")
            
            # Preparar lista de documentos recebidos
            docs_recebidos_lista = []
            for doc in documentos_recebidos:
                nome_tipo = doc.get('ai_document_types', {}).get('name', 'Documento')
                docs_recebidos_lista.append(f"✅ {nome_tipo}")
            
            # Preparar informações sobre documentos
            docs_info = f"""
            DOCUMENTOS OBRIGATÓRIOS: {total_obrigatorios}
            DOCUMENTOS RECEBIDOS: {total_recebidos}
            DOCUMENTOS FALTANTES: {total_faltantes}
            PROGRESSO: {progresso_percentual:.1f}%
            
            DOCUMENTOS JÁ RECEBIDOS:
            {chr(10).join(docs_recebidos_lista) if docs_recebidos_lista else "Nenhum documento recebido ainda"}
            
            DOCUMENTOS FALTANTES:
            {chr(10).join(docs_faltantes_lista) if docs_faltantes_lista else "Nenhum documento faltante"}
            """
            
            # Determinar contexto atual baseado nos dados
            if total_obrigatorios == 0:
                contexto_atual = "sem_documentos_definidos"
            elif total_faltantes == 0 and total_recebidos > 0:
                contexto_atual = "documentos_completos"
            elif total_recebidos > 0:
                contexto_atual = "aguardando_documentos"
            else:
                contexto_atual = "iniciando_coleta"
            
            # Prompt para GPT-4
            prompt = f"""
            Você é um assistente IA especializado em negociações imobiliárias. Analise o histórico de conversas abaixo e as informações sobre documentos para:

            1. RESUMIR onde parou a conversa
            2. IDENTIFICAR o que o cliente precisa fazer agora
            3. SUGERIR a próxima mensagem apropriada

            HISTÓRICO DE CONVERSAS ({len(historico)} mensagens):
            {chr(10).join(historico) if historico else "Nenhuma conversa anterior"}

            SITUAÇÃO DOS DOCUMENTOS:
            {docs_info}

            CONTEXTO ATUAL: {contexto_atual}

            INSTRUÇÕES:
            - Seja cordial e profissional
            - Se faltam documentos, mencione ESPECIFICAMENTE quais documentos estão faltando com suas descrições
                        - Use formatação com quebras de linha para melhor legibilidade no WhatsApp:
              "Recebi seu RG ✅
              
              Ainda preciso de:
              📄 *Comprovante de Renda* - últimos 3 holerites
              🏠 *Comprovante de Residência* - conta de luz/água  
              📋 *Certidão de Nascimento/Casamento* - estado civil
              
              Me peça para enviar documentos que inicio a sequência de envios com você! 📄"
            - Se todos os documentos foram enviados, informe o próximo passo
            - Mantenha o tom conversacional e amigável
            - Use emojis para deixar mais amigável
            - Use quebras de linha para separar as informações
            - Se não há conversas anteriores, seja acolhedor e explique o processo

            Responda em JSON com:
            - "resumo": Resumo do contexto atual
            - "proxima_mensagem": Mensagem para enviar ao cliente
            - "contexto": Situação atual (ex: "aguardando_documentos", "documentos_completos", "iniciando_conversa")
            """
            
            # Fazer chamada para GPT-4
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Você é um assistente especializado em análise de conversas imobiliárias. Responda sempre em JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # Processar resposta
            resposta_texto = response.choices[0].message.content.strip()
            
            # Tentar fazer parse do JSON
            try:
                resultado = json.loads(resposta_texto)
                logger.info(f"✅ Análise GPT-4 concluída com sucesso")
                return resultado
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Resposta GPT-4 não é JSON válido: {resposta_texto[:200]}...")
                
                # Tentar extrair mensagem útil do texto mal formado
                mensagem_limpa = resposta_texto
                
                # Se contém estrutura JSON parcial, tentar extrair a mensagem
                if '"proxima_mensagem"' in resposta_texto:
                    try:
                        import re
                        # Buscar o conteúdo da proxima_mensagem
                        match = re.search(r'"proxima_mensagem":\s*"([^"]*)"', resposta_texto)
                        if match:
                            mensagem_limpa = match.group(1)
                            logger.info(f"✅ Mensagem extraída do JSON parcial")
                        else:
                            # Fallback: usar texto após dois pontos
                            if ':"' in resposta_texto:
                                mensagem_limpa = resposta_texto.split(':"')[1].split('"')[0]
                    except Exception as e_regex:
                        logger.warning(f"⚠️ Erro ao extrair mensagem: {e_regex}")
                        # Usar mensagem padrão se falhar
                        mensagem_limpa = "Analisei sua situação e vou continuar te ajudando com os próximos passos!"
                else:
                    # Se não tem estrutura JSON, usar o texto direto mas limitar tamanho
                    mensagem_limpa = resposta_texto[:200] if len(resposta_texto) > 200 else resposta_texto
                    # Remover caracteres JSON comuns que possam aparecer
                    mensagem_limpa = mensagem_limpa.replace('{"', '').replace('"}', '').replace('\\n', '\n')
                
                return {
                    "resumo": "Análise concluída com texto não estruturado",
                    "proxima_mensagem": mensagem_limpa,
                    "contexto": "analise_texto_livre"
                }
            
        except Exception as e:
            logger.error(f"❌ Erro na análise GPT-4: {str(e)}")
            return {
                "resumo": f"Erro na análise: {str(e)}",
                "proxima_mensagem": "Vou analisar sua situação e retorno em breve. Obrigado pela paciência!",
                "contexto": "erro_analise"
            } 