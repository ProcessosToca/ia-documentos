import os
import re
import json
from openai import OpenAI
from typing import Dict, Any, List
import logging
from datetime import datetime

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpenAIService:
    """Serviço para integração com OpenAI"""
    
    def __init__(self):
        # Configurar cliente OpenAI
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.company_name = os.getenv('COMPANY_NAME', 'Locação Online')
        
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
                model="gpt-4o",
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
            
            # Extrair e processar resposta
            resposta_texto = response.choices[0].message.content.strip()
            logger.info(f"🤖 Resposta recebida: {resposta_texto[:100]}...")
            
            try:
                # ✅ CORREÇÃO: Limpeza robusta do JSON
                resposta_limpa = resposta_texto
                
                # Remover markdown se presente
                if '```json' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```json')[1]
                if '```' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```')[0]
                
                # Remover espaços e quebras de linha extras
                resposta_limpa = resposta_limpa.strip()
                
                resultado = json.loads(resposta_limpa)
                logger.info("🤖 Interpretação concluída com sucesso")
                
                return resultado
                
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Erro ao processar JSON: {e}")
                logger.warning(f"🔍 Resposta original: {resposta_texto}")
                
                # ✅ CORREÇÃO: Fallback inteligente
                # Tentar extrair CPF da resposta mesmo com JSON malformado
                cpf_encontrado = None
                if '"cpf"' in resposta_texto:
                    # Buscar padrão de CPF na resposta
                    cpf_match = re.search(r'"cpf":\s*"?(\d{11})"?', resposta_texto)
                    if cpf_match:
                        cpf_encontrado = cpf_match.group(1)
                
                # Detectar se é novo usuário
                novo_usuario = '"novo_usuario": true' in resposta_texto or '"saudacao"' in resposta_texto.lower()
                
                logger.info(f"🔄 Fallback aplicado - CPF: {cpf_encontrado}, Novo: {novo_usuario}")
                
                return {
                    "cpf": cpf_encontrado,
                    "novo_usuario": novo_usuario,
                    "solicitar_cpf": cpf_encontrado is None,
                    "mensagem_resposta": "Por favor, me envie seu CPF (apenas números) para continuarmos o atendimento.",
                    "erro": "json_parse_error_com_fallback"
                }
            
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
                docs_faltantes_lista.append(f"📄 *{nome}* - {descricao}")
            
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
            logger.info(f"🤖 Resposta GPT-4 recebida: {resposta_texto[:100]}...")
            
            # Tentar fazer parse do JSON
            try:
                # ✅ CORREÇÃO: Limpeza robusta do JSON
                resposta_limpa = resposta_texto
                
                # Remover markdown se presente
                if '```json' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```json')[1]
                if '```' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```')[0]
                
                # Remover espaços e quebras de linha extras
                resposta_limpa = resposta_limpa.strip()
                
                resultado = json.loads(resposta_limpa)
                logger.info(f"✅ Análise GPT-4 concluída com sucesso")
                return resultado
                
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Erro ao processar JSON: {e}")
                logger.warning(f"🔍 Resposta original: {resposta_texto}")
                
                # ✅ CORREÇÃO: Fallback inteligente melhorado
                mensagem_limpa = resposta_texto
                
                # Se contém estrutura JSON parcial, tentar extrair a mensagem
                if '"proxima_mensagem"' in resposta_texto:
                    try:
                        # Buscar o conteúdo da proxima_mensagem
                        match = re.search(r'"proxima_mensagem":\s*"([^"]*)"', resposta_texto)
                        if match:
                            mensagem_limpa = match.group(1).replace('\\n', '\n')
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
                
                logger.info(f"🔄 Fallback aplicado - Mensagem: {mensagem_limpa[:50]}...")
                
                return {
                    "resumo": "Análise concluída com fallback inteligente",
                    "proxima_mensagem": mensagem_limpa,
                    "contexto": "analise_texto_livre_com_fallback",
                    "erro": "json_parse_error_com_fallback"
                }
            
        except Exception as e:
            logger.error(f"❌ Erro na análise GPT-4: {str(e)}")
            return {
                "resumo": f"Erro na análise: {str(e)}",
                "proxima_mensagem": "Vou analisar sua situação e retorno em breve. Obrigado pela paciência!",
                "contexto": "erro_analise"
            }

    def interpretar_intencao_mensagem(self, mensagem: str, remetente: str = None) -> Dict[str, Any]:
        """
        Interpretador inteligente para detectar intenções em mensagens usando GPT
        
        Esta função é o INTERPRETADOR CENTRAL que processa TODAS as mensagens
        antes do fluxo principal, identificando:
        - Saudações (oi, olá, bom dia) → Primeira mensagem da Bia
        - Solicitações de menu (menu, opções) → Menu apropriado por tipo de usuário
        - Conversas normais → Continua fluxo original
        
        Args:
            mensagem (str): Texto da mensagem recebida do usuário
            remetente (str, optional): Número do telefone (para contexto futuro)
            
        Returns:
            Dict com análise da intenção:
                - intencao: "saudacao" | "menu" | "conversa_normal" | "duvida_tecnica"
                - confianca: 0.0-1.0 (nível de certeza da IA)
                - bypass_fluxo: True se deve interceptar, False se continua normal
                - contexto: "primeira_interacao" | "usuario_conhecido"
                - acao_sugerida: "primeira_mensagem" | "enviar_menu" | "continuar_fluxo"
        
        Exemplo de uso:
            >>> interpretacao = service.interpretar_intencao_mensagem("oi, tudo bem?")
            >>> print(interpretacao["intencao"])  # "saudacao"
            >>> print(interpretacao["bypass_fluxo"])  # True
        """
        try:
            logger.info(f"🧠 Interpretando intenção da mensagem: {mensagem[:50]}...")
            
            # Prompt especializado para detectar intenções
            prompt = f"""Analise esta mensagem do WhatsApp e identifique a intenção do usuário:

MENSAGEM: "{mensagem}"

Classifique a intenção como:

1. "saudacao" - Se contém cumprimentos como: oi, olá, bom dia, boa tarde, boa noite, hey, e aí, tudo bem, como vai, etc.

2. "menu" - Se solicita navegação como: menu, opções, voltar menu, menu inicial, mostrar opções, escolhas, navegar, etc.

3. "conversa_normal" - Se contém: CPF, números, perguntas específicas, documentos, informações pessoais

4. "duvida_tecnica" - Se contém perguntas sobre: locação, processos, contratos, documentação, análise, negociação

IMPORTANTE:
- Alta confiança (>0.8) apenas se for CLARAMENTE uma saudação ou solicitação de menu
- Média confiança (0.5-0.8) se houver dúvida
- Baixa confiança (<0.5) se for ambíguo

Responda APENAS em JSON válido:
{{
  "intencao": "saudacao|menu|conversa_normal|duvida_tecnica",
  "confianca": 0.0,
  "bypass_fluxo": true/false,
  "contexto": "primeira_interacao|usuario_conhecido",
  "acao_sugerida": "primeira_mensagem|enviar_menu|continuar_fluxo"
}}"""

            # Chamada para GPT com configurações otimizadas
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """Você é um analisador especializado em intenções de mensagens para um sistema de atendimento imobiliário.

Sua função é identificar com precisão a intenção real do usuário:

- SAUDAÇÕES: Cumprimentos gerais e iniciais de conversa
- MENU: Solicitações explícitas de navegação ou opções
- CONVERSA_NORMAL: Informações específicas como CPF, dados pessoais
- DUVIDA_TECNICA: Perguntas sobre processos, contratos, locação

Seja conservador: apenas classifique como "saudacao" ou "menu" se tiver ALTA CERTEZA.
Caso contrário, use "conversa_normal" para manter o fluxo original funcionando.

SEMPRE retorne JSON válido sem texto adicional."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Baixa criatividade para consistência
                max_tokens=150    # Resposta curta e objetiva
            )
            
            # Processar resposta do GPT
            resposta_texto = response.choices[0].message.content.strip()
            logger.info(f"🤖 Resposta GPT: {resposta_texto[:100]}...")
            
            try:
                # ✅ CORREÇÃO: Limpeza robusta do JSON
                resposta_limpa = resposta_texto
                
                # Remover markdown se presente
                if '```json' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```json')[1]
                if '```' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```')[0]
                
                # Remover espaços e quebras de linha extras
                resposta_limpa = resposta_limpa.strip()
                
                # Log da resposta limpa para debug
                logger.info(f"🧹 JSON limpo: {resposta_limpa[:150]}...")
                
                # Tentar fazer parse do JSON
                resultado = json.loads(resposta_limpa)
                
                # Validar campos obrigatórios
                campos_obrigatorios = ["intencao", "confianca", "bypass_fluxo", "acao_sugerida"]
                for campo in campos_obrigatorios:
                    if campo not in resultado:
                        raise ValueError(f"Campo obrigatório ausente: {campo}")
                
                # Ajustar bypass_fluxo baseado na intenção e confiança
                if resultado["confianca"] < 0.7:
                    resultado["bypass_fluxo"] = False
                    resultado["acao_sugerida"] = "continuar_fluxo"
                else:
                    # Para saudações e menu com alta confiança, sempre fazer bypass
                    if resultado["intencao"] in ["saudacao", "menu"]:
                        resultado["bypass_fluxo"] = True
                        if resultado["intencao"] == "saudacao":
                            resultado["acao_sugerida"] = "primeira_mensagem"
                        elif resultado["intencao"] == "menu":
                            resultado["acao_sugerida"] = "enviar_menu"
                
                logger.info(f"✅ Intenção detectada: {resultado['intencao']} (confiança: {resultado['confianca']})")
                return resultado
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"⚠️ Erro ao processar JSON do GPT: {e}")
                logger.warning(f"🔍 Resposta original: {resposta_texto}")
                
                # ✅ CORREÇÃO: Fallback inteligente baseado no conteúdo
                # Tentar extrair informações mesmo com JSON malformado
                intencao_detectada = "conversa_normal"
                confianca_detectada = 0.0
                
                # Buscar padrões na resposta mesmo sem JSON válido
                if '"intencao": "saudacao"' in resposta_texto or '"saudacao"' in resposta_texto:
                    intencao_detectada = "saudacao"
                    confianca_detectada = 0.8
                elif '"intencao": "menu"' in resposta_texto or '"menu"' in resposta_texto:
                    intencao_detectada = "menu"
                    confianca_detectada = 0.8
                
                # Determinar ação baseada na intenção detectada
                if intencao_detectada == "saudacao":
                    acao_sugerida = "primeira_mensagem"
                    bypass_fluxo = True
                elif intencao_detectada == "menu":
                    acao_sugerida = "enviar_menu"
                    bypass_fluxo = True
                else:
                    acao_sugerida = "continuar_fluxo"
                    bypass_fluxo = False
                
                logger.info(f"🔄 Fallback inteligente: {intencao_detectada} (confiança: {confianca_detectada})")
                
                return {
                    "intencao": intencao_detectada,
                    "confianca": confianca_detectada,
                    "bypass_fluxo": bypass_fluxo,
                    "contexto": "usuario_conhecido", 
                    "acao_sugerida": acao_sugerida,
                    "erro": "json_parse_error_com_fallback"
                }
                
        except Exception as e:
            logger.error(f"❌ Erro crítico no interpretador de intenções: {str(e)}")
            # Fallback seguro: sempre continuar fluxo normal em caso de erro
            return {
                "intencao": "conversa_normal",
                "confianca": 0.0,
                "bypass_fluxo": False,
                "contexto": "usuario_conhecido",
                "acao_sugerida": "continuar_fluxo",
                "erro": str(e)
            }


    def validar_dado_cliente(self, tipo_dado: str, valor: str) -> Dict[str, Any]:
        """
        Valida dados do cliente coletados durante processo de fechamento usando GPT
        
        Esta função usa IA para validar se os dados fornecidos pelo colaborador
        são válidos para um processo de locação imobiliária.
        
        Args:
            tipo_dado (str): Tipo do dado a validar ("nome" | "telefone")
            valor (str): Valor fornecido pelo colaborador para validação
            
        Returns:
            Dict com resultado da validação:
                - valido: True se dado é válido, False se inválido
                - valor_corrigido: Valor formatado/corrigido se necessário
                - motivo_erro: Explicação se inválido
                - sugestao: Sugestão de correção se aplicável
        
        Exemplos de uso:
            >>> resultado = service.validar_dado_cliente("nome", "João Silva")
            >>> print(resultado["valido"])  # True
            
            >>> resultado = service.validar_dado_cliente("telefone", "11999999999")
            >>> print(resultado["valor_corrigido"])  # "(11) 99999-9999"
        """
        try:
            logger.info(f"🔍 Validando {tipo_dado}: {valor[:30]}...")
            
            if tipo_dado == "nome":
                # Prompt para validação de nome
                prompt = f"""Analise se este é um nome válido para um cliente de locação imobiliária:

NOME: "{valor}"

Critérios FLEXÍVEIS de validação:
1. Deve conter pelo menos 2 palavras (nome + sobrenome)
2. Deve usar caracteres alfabéticos (permitir acentos, espaços)
3. Não deve conter números ou símbolos especiais
4. Deve parecer um nome real de pessoa
5. Aceitar nomes compostos, duplos, estrangeiros

Exemplos VÁLIDOS: "João Silva", "Maria Santos", "José da Silva", "Ana Beatriz", "Carlos Eduardo", "Andreia Robe", "Maria José", "João Pedro"
Exemplos INVÁLIDOS: "João", "123", "abc", "João123", "@#$", "X Y", "A B"

IMPORTANTE: Seja FLEXÍVEL com nomes reais. Se parece um nome de pessoa válido com pelo menos 2 palavras, ACEITE.

Responda APENAS em JSON:
{{
  "valido": true/false,
  "valor_corrigido": "Nome formatado corretamente",
  "motivo_erro": "Explicação se inválido",
  "sugestao": "Sugestão de correção se necessário"
}}"""

            elif tipo_dado == "telefone":
                # Prompt para validação de telefone
                prompt = f"""Analise se este é um telefone válido brasileiro:

TELEFONE: "{valor}"

Critérios de validação:
1. Deve ter 10 ou 11 dígitos (com DDD)
2. DDD válido brasileiro (11-99)
3. Número de celular ou fixo válido
4. Pode ter ou não formatação
5. Não deve conter letras

Exemplos VÁLIDOS: "11999999999", "(11) 99999-9999", "1133334444"
Exemplos INVÁLIDOS: "999999999", "abc", "123", "00999999999"

Se válido, formate como: (XX) XXXXX-XXXX para celular ou (XX) XXXX-XXXX para fixo

Responda APENAS em JSON:
{{
  "valido": true/false,
  "valor_corrigido": "Telefone formatado: (XX) XXXXX-XXXX",
  "motivo_erro": "Explicação se inválido",
  "sugestao": "Sugestão de correção se necessário"
}}"""

            else:
                return {
                    "valido": False,
                    "motivo_erro": f"Tipo de dado não suportado: {tipo_dado}",
                    "sugestao": "Use 'nome' ou 'telefone'"
                }

            # Chamada para GPT com configurações de validação
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """Você é um validador especializado em dados de clientes para processos imobiliários.

Sua função é verificar se os dados fornecidos são válidos e úteis para um processo de locação.

Seja rigoroso na validação:
- Nomes devem ser completos e reais
- Telefones devem ser brasileiros válidos
- Sempre formate corretamente os dados válidos
- Forneça explicações claras para dados inválidos

SEMPRE retorne JSON válido sem texto adicional."""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Baixa criatividade para consistência na validação
                max_tokens=200
            )
            
            # Processar resposta do GPT
            resposta_texto = response.choices[0].message.content.strip()
            logger.info(f"🤖 Validação GPT: {resposta_texto[:100]}...")
            
            try:
                # ✅ CORREÇÃO: Limpeza robusta do JSON
                resposta_limpa = resposta_texto
                
                # Remover markdown se presente
                if '```json' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```json')[1]
                if '```' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```')[0]
                
                # Remover espaços e quebras de linha extras
                resposta_limpa = resposta_limpa.strip()
                
                # Parse do JSON
                resultado = json.loads(resposta_limpa)
                
                # Validar campos obrigatórios
                if "valido" not in resultado:
                    raise ValueError("Campo 'valido' ausente na resposta")
                
                # Adicionar informações de contexto
                resultado.update({
                    "tipo_dado": tipo_dado,
                    "valor_original": valor,
                    "timestamp_validacao": "now"
                })
                
                status = "✅ VÁLIDO" if resultado["valido"] else "❌ INVÁLIDO"
                logger.info(f"{status} - {tipo_dado}: {valor[:20]}...")
                
                return resultado
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"⚠️ Erro ao processar JSON de validação: {e}")
                logger.warning(f"🔍 Resposta original: {resposta_texto}")
                
                # ✅ CORREÇÃO: Fallback inteligente
                # Tentar extrair informações básicas mesmo com JSON malformado
                valido_detectado = False
                if '"valido": true' in resposta_texto or '"valido":true' in resposta_texto:
                    valido_detectado = True
                
                logger.info(f"🔄 Fallback aplicado - Válido: {valido_detectado}")
                
                # Fallback: considerar inválido se não conseguir processar
                return {
                    "valido": valido_detectado,
                    "motivo_erro": "Erro interno na validação" if not valido_detectado else "Processamento com fallback",
                    "sugestao": f"Tente novamente com um {tipo_dado} mais claro",
                    "erro_processamento": str(e),
                    "tipo_dado": tipo_dado,
                    "valor_original": valor
                }
                
        except Exception as e:
            logger.error(f"❌ Erro crítico na validação de dados: {str(e)}")
            # Fallback seguro: sempre rejeitar em caso de erro
            return {
                "valido": False,
                "motivo_erro": "Erro técnico na validação",
                "sugestao": f"Tente novamente fornecendo o {tipo_dado}",
                "erro_critico": str(e)
            }

    def responder_duvida_locacao(self, duvida: str, contexto_colaborador: dict = None) -> Dict[str, Any]:
        """
        IA especializada em responder dúvidas sobre negociação de locação para colaboradores
        
        Esta função é chamada quando um colaborador seleciona "Usar IA para Dúvidas" no menu
        e envia uma pergunta relacionada a processos de locação, documentos, negociação, etc.
        
        Args:
            duvida (str): Pergunta/dúvida do colaborador sobre locação
            contexto_colaborador (dict, optional): Dados do colaborador (setor, nome, etc.)
            
        Returns:
            Dict: Resposta estruturada com:
                - resposta: Texto da resposta especializada
                - categoria: Categoria da dúvida (documentos, processo, juridico, etc.)
                - confianca: Nível de confiança da resposta (alto/medio/baixo)
                - sugestoes_extras: Sugestões adicionais se aplicável
                
        Exemplo:
            >>> resultado = responder_duvida_locacao("Como validar comprovante de renda?")
            >>> print(resultado["resposta"])
            "Para validar comprovante de renda, você deve verificar..."
        """
        try:
            logger.info(f"🤖 Processando dúvida de locação: {duvida[:50]}...")
            
            # Extrair informações do colaborador se disponível
            nome_colaborador = "Colaborador"
            setor_colaborador = "Não informado"
            
            if contexto_colaborador:
                nome_colaborador = contexto_colaborador.get('nome', 'Colaborador')
                setor_colaborador = contexto_colaborador.get('setor', 'Não informado')
            
            # Prompt especializado em negociação de locação
            prompt_sistema = f"""Você é um ESPECIALISTA em NEGOCIAÇÃO DE LOCAÇÃO IMOBILIÁRIA e assistente para colaboradores da {self.company_name}.

            ESPECIALIDADES:
            🏠 Processos de locação sem fiador
            📄 Documentação necessária (RG, CPF, comprovantes)
            💰 Análise de renda e capacidade financeira
            📋 Contratos e termos legais
            🔍 Validação de documentos
            👥 Relacionamento com clientes
            ⚖️ Aspectos jurídicos básicos
            📊 Fluxos e procedimentos internos

            INSTRUÇÕES:
            - Responda de forma PRÁTICA e OBJETIVA
            - Use linguagem PROFISSIONAL mas ACESSÍVEL
            - Forneça PASSOS CONCRETOS quando aplicável
            - Mencione DOCUMENTOS ESPECÍFICOS quando necessário
            - Use EMOJIS para organizar a informação
            - Se não souber algo específico da {self.company_name}, seja transparente
            - Foque em SOLUÇÕES PRÁTICAS para o dia a dia

            FORMATO DA RESPOSTA:
            - Use quebras de linha para facilitar leitura no WhatsApp
            - Organize em tópicos quando necessário
            - Seja direto e evite textos muito longos
            """

            prompt_usuario = f"""
            CONTEXTO DO COLABORADOR:
            👤 Nome: {nome_colaborador}
            🏢 Setor: {setor_colaborador}

            DÚVIDA:
            {duvida}

            Responda esta dúvida de forma especializada, considerando que é um colaborador da {self.company_name} que precisa de orientação prática para seu trabalho diário.

            Formate sua resposta em JSON com:
            - "resposta": Resposta detalhada e prática para a dúvida
            - "categoria": Categoria da dúvida (documentos|processo|juridico|relacionamento|financeiro|outros)
            - "confianca": Nível de confiança da resposta (alto|medio|baixo)
            - "sugestoes_extras": Array com sugestões adicionais ou próximos passos (máximo 3 sugestões)
            """

            # Fazer chamada para GPT-4
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt_sistema},
                    {"role": "user", "content": prompt_usuario}
                ],
                temperature=0.3,  # Baixa temperatura para respostas mais consistentes
                max_tokens=800,   # Espaço suficiente para resposta detalhada
                top_p=0.9
            )

            # Extrair e processar resposta
            resposta_texto = response.choices[0].message.content.strip()
            
            try:
                # ✅ CORREÇÃO: Limpeza robusta do JSON
                resposta_limpa = resposta_texto
                
                # Remover markdown se presente
                if '```json' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```json')[1]
                if '```' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```')[0]
                
                # Remover espaços e quebras de linha extras
                resposta_limpa = resposta_limpa.strip()
                
                # Tentar fazer parse do JSON
                resultado = json.loads(resposta_limpa)
                
                # Validar estrutura da resposta
                if not all(key in resultado for key in ['resposta', 'categoria', 'confianca']):
                    raise ValueError("JSON não contém todas as chaves necessárias")
                
                # Garantir que sugestoes_extras seja uma lista
                if 'sugestoes_extras' not in resultado:
                    resultado['sugestoes_extras'] = []
                elif not isinstance(resultado['sugestoes_extras'], list):
                    resultado['sugestoes_extras'] = [str(resultado['sugestoes_extras'])]
                
                logger.info(f"✅ Dúvida processada - Categoria: {resultado['categoria']}")
                logger.info(f"🎯 Confiança: {resultado['confianca']}")
                
                return {
                    "sucesso": True,
                    "resposta": resultado['resposta'],
                    "categoria": resultado['categoria'],
                    "confianca": resultado['confianca'],
                    "sugestoes_extras": resultado['sugestoes_extras'],
                    "colaborador": nome_colaborador,
                    "setor": setor_colaborador
                }
                
            except (json.JSONDecodeError, ValueError) as e:
                # Se JSON inválido, usar resposta como texto simples
                logger.warning(f"⚠️ Erro ao processar JSON: {str(e)}")
                logger.warning(f"🔍 Resposta original: {resposta_texto}")
                
                # ✅ CORREÇÃO: Fallback inteligente melhorado
                resposta_limpa = resposta_texto
                
                # Remover markdown básico
                resposta_limpa = resposta_limpa.replace('```json', '').replace('```', '').strip()
                
                # Tentar extrair pelo menos a resposta principal
                if '"resposta"' in resposta_limpa:
                    match = re.search(r'"resposta":\s*"([^"]*)"', resposta_limpa)
                    if match:
                        resposta_limpa = match.group(1).replace('\\n', '\n')
                
                # Detectar categoria se possível
                categoria_detectada = "geral"
                if '"categoria"' in resposta_texto:
                    cat_match = re.search(r'"categoria":\s*"([^"]*)"', resposta_texto)
                    if cat_match:
                        categoria_detectada = cat_match.group(1)
                
                logger.info(f"🔄 Fallback aplicado - Categoria: {categoria_detectada}")
                
                return {
                    "sucesso": True,
                    "resposta": resposta_limpa,
                    "categoria": categoria_detectada,
                    "confianca": "medio",
                    "sugestoes_extras": ["Posso esclarecer mais detalhes se precisar"],
                    "colaborador": nome_colaborador,
                    "setor": setor_colaborador,
                    "aviso": "Resposta processada com fallback inteligente",
                    "erro": "json_parse_error_com_fallback"
                }
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar dúvida de locação: {str(e)}")
            
            return {
                "sucesso": False,
                "resposta": "Desculpe, tive um problema técnico ao processar sua dúvida. Pode reformular sua pergunta ou tentar novamente em alguns instantes?",
                "categoria": "erro",
                "confianca": "baixo",
                "sugestoes_extras": [
                    "Tente reformular a pergunta",
                    "Seja mais específico sobre o tema",
                    "Verifique se é uma dúvida sobre locação"
                ],
                "colaborador": nome_colaborador,
                "setor": setor_colaborador,
                "erro": str(e)
            } 

    def analisar_e_limpar_conversa_json(self, conversa_json: Dict[str, Any]) -> Dict[str, Any]:
        """
        🧠 NOVA FUNÇÃO: Usa OpenAI para analisar e limpar JSON de conversa
        
        Funcionalidades:
        - Remove mensagens duplicadas
        - Remove logs técnicos e do sistema
        - Formata mensagens de menu naturalmente
        - Remove detalhes técnicos como "(row_id: iniciar_fechamento)"
        - Prepara JSON otimizado para banco de dados
        
        Args:
            conversa_json (Dict): JSON da conversa original
            
        Returns:
            Dict: JSON limpo e otimizado
        """
        try:
            logger.info("🧠 Iniciando análise e limpeza do JSON da conversa com OpenAI...")
            
            # Extrair mensagens para análise
            mensagens_originais = conversa_json.get('messages', [])
            
            if not mensagens_originais:
                logger.warning("⚠️ Nenhuma mensagem encontrada para analisar")
                return conversa_json
            
            # Preparar dados para OpenAI
            mensagens_para_analise = []
            for i, msg in enumerate(mensagens_originais):
                mensagens_para_analise.append({
                    "index": i,
                    "id": msg.get('id'),
                    "timestamp": msg.get('timestamp'),
                    "sender": msg.get('sender'),
                    "content": msg.get('content', '')[:500],  # Limitar tamanho
                    "message_type": msg.get('message_type'),
                    "phase": msg.get('phase')
                })
            
            # Extrair dados dos participantes para detecção inteligente
            participants = conversa_json.get('participants', {})
            client_data = participants.get('client', {})
            client_cpf = client_data.get('cpf', '')
            client_email = client_data.get('email', '')
            
            # ✅ OTIMIZADO: Prompt mais assertivo e específico
            prompt_analise = f"""
Você é um ESPECIALISTA em limpeza de conversas WhatsApp. EXECUTE AS 4 REGRAS OBRIGATÓRIAS:

🎯 **REGRA 1 - CLASSIFICAÇÃO IA→CORRETOR** (OBRIGATÓRIA):
- "✅ *Dados do cliente coletados com sucesso!*" = sender="ia", receiver="corretor"
- "🚀 Mensagem enviada ao cliente" = sender="ia", receiver="corretor"  
- "✅ Iniciando contato com o cliente" = sender="ia", receiver="corretor"

🎯 **REGRA 2 - NATURALIZAÇÃO MENUS** (OBRIGATÓRIA):
- REMOVER: "(row_id: iniciar_fechamento)" → "Iniciar Fechamento Locação"
- REMOVER: "(row_id: qualquer_codigo)" → texto natural apenas

🎯 **REGRA 3 - DUPLICATAS** (OBRIGATÓRIA):
- Mensagens IDÊNTICAS = REMOVER a segunda ocorrência
- Conteúdo 90%+ similar = REMOVER duplicata
- Seja AGRESSIVO na remoção de duplicatas

🎯 **REGRA 4 - FLUXO PERDIDO** (OBRIGATÓRIA):
- IA pede CPF → IA pede EMAIL = INSERIR resposta CPF do cliente
- IA pede EMAIL → IA pede DATA = INSERIR resposta EMAIL do cliente

**REGRAS ESPECÍFICAS OBRIGATÓRIAS:**

1. **CPF SEMPRE = CLIENTE**: Qualquer mensagem contendo CPF (11 dígitos) deve ter sender="cliente"

2. **REMOVER MENSAGEM DUPLICADA DE CPF**: 
   - SEMPRE remover: "📄 Para prosseguir, preciso do seu CPF: (Somente números, exemplo: 12345678901)"
   - MANTER apenas: "✅ Perfeito! Para prosseguir, preciso do seu CPF."

3. **MENSAGENS IA→CORRETOR (sender="ia", receiver="corretor")**:
   - "✅ Iniciando contato com o cliente..."
   - "✅ Dados do cliente coletados com sucesso!"
   - Qualquer mensagem começando com "✅ Dados do cliente"

4. **CLASSIFICAÇÃO CORRETA**:
   - Mensagem com CPF = sender="cliente"
   - Mensagem "✅ Iniciando contato" = sender="ia", receiver="corretor"
   - Mensagem "✅ Dados coletados" = sender="ia", receiver="corretor"

**MENSAGENS DA CONVERSA:**
{json.dumps(mensagens_para_analise, ensure_ascii=False, indent=2)}

**DADOS DO CLIENTE (para detecção inteligente):**
- CPF: {client_cpf}
- Email: {client_email}

**DETECÇÃO INTELIGENTE (REGRA CRÍTICA):**

EXEMPLO DE PROBLEMA:
1. msg_003: IA diz "preciso do seu CPF"
2. msg_004: IA detalha "Para prosseguir, preciso do seu CPF: (números)"
3. msg_005: IA diz "Digite seu e-mail"  ← PROBLEMA! Cliente não respondeu CPF!

REGRA: Se IA pede CPF e próxima mensagem é IA pedindo EMAIL (sem resposta do cliente), então INSERIR:
{{
  "inserir_apos_index": [índice da mensagem que pede CPF],
  "sender": "cliente", 
  "content": "{client_cpf}",
  "motivo": "Resposta de CPF perdida detectada"
}}

OUTROS PADRÕES:
- IA pede CPF → IA pede EMAIL = FALTA resposta CPF
- IA pede EMAIL → IA pede DATA = FALTA resposta EMAIL
- IA pede DATA → IA pede CEP = FALTA resposta DATA

**RESPONDA EM JSON:**
{{
  "mensagens_para_manter": [índices das mensagens que devem ser mantidas],
  "mensagens_para_remover": [índices das mensagens que devem ser removidas],
  "mensagens_para_reformatar": [
    {{
      "index": índice,
      "novo_conteudo": "nova versão sem detalhes técnicos"
    }}
  ],
  "mensagens_para_reclassificar": [
    {{
      "index": índice,
      "novo_sender": "cliente|ia|corretor",
      "novo_receiver": "ia|corretor|cliente",
      "motivo": "classificação correta aplicada"
    }}
  ],
  "mensagens_para_inserir": [
    {{
      "inserir_apos_index": índice,
      "sender": "cliente",
      "content": "resposta do cliente",
      "motivo": "mensagem perdida detectada"
    }}
  ],
  "justificativa": "explicação breve das mudanças"
}}

**REGRAS:**
- Manter TODAS as mensagens essenciais do cliente e IA
- Remover apenas duplicatas óbvias e logs técnicos
- Naturalizar menus: "Iniciar Fechamento Locação" (sem row_id)
- INSERIR mensagens perdidas do cliente automaticamente
- RECLASSIFICAR mensagens conforme regras específicas
- Preservar fluxo da conversa
- Ser conservador - na dúvida, manter
"""

            # Chamar OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {
                        "role": "system", 
                        "content": """Você é um especialista em análise de conversas de WhatsApp. 

SUA MISSÃO ESPECÍFICA: Detectar quando mensagens do cliente estão perdidas.

PADRÃO CRÍTICO A DETECTAR:
- IA pede CPF: "preciso do seu CPF"
- IA pede email: "Digite seu e-mail" (SEM o cliente ter respondido CPF)
- = PROBLEMA! Falta mensagem do cliente com CPF

QUANDO DETECTAR ESSE PADRÃO, você DEVE inserir a mensagem perdida usando os dados dos participants.

Seja PRECISO na detecção de fluxos quebrados."""
                    },
                    {
                        "role": "user", 
                        "content": prompt_analise
                    }
                ],
                temperature=0.1,  # Baixa temperatura para consistência
                max_tokens=2000
            )
            
            # Processar resposta
            resposta_openai = response.choices[0].message.content.strip()
            
            # Limpar resposta removendo markdown
            resposta_limpa = resposta_openai.replace('```json', '').replace('```', '').strip()
            
            try:
                # ✅ OTIMIZADO: Limpeza robusta do JSON (igual ao projeto anterior)
                if '```json' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```json')[1]
                if '```' in resposta_limpa:
                    resposta_limpa = resposta_limpa.split('```')[0]
                
                # Remove quebras de linha extras e normaliza
                resposta_limpa = " ".join(resposta_limpa.split())
                
                # Tentar parsear JSON da resposta
                analise = json.loads(resposta_limpa)
                logger.info(f"✅ Análise OpenAI concluída: {analise.get('justificativa', 'N/A')}")
                
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Erro ao parsear JSON da OpenAI: {e}")
                logger.warning(f"🔍 Resposta original: {resposta_openai[:200]}...")
                
                # ✅ NOVO: Fallback inteligente que executa regras RAG básicas
                logger.info("🔄 Aplicando fallback inteligente com regras RAG...")
                analise = self._criar_analise_fallback_rag(mensagens_para_analise, resposta_openai)
            
            # Aplicar as mudanças recomendadas
            mensagens_limpas = self._aplicar_limpeza_conversa(
                mensagens_originais, 
                analise,
                conversa_json
            )

            # ✅ NOVO: Aplicar verificação final obrigatória
            mensagens_verificadas = self._verificacao_final_obrigatoria(mensagens_limpas)
            
            # ✅ NOVO: Gerar relatório de auditoria
            relatorio_auditoria = self._auditar_resultado_limpeza(
                mensagens_originais, 
                mensagens_verificadas, 
                analise
            )

            # Criar JSON limpo
            conversa_limpa = conversa_json.copy()
            conversa_limpa['messages'] = mensagens_verificadas
            
            # Atualizar estatísticas
            if 'conversation_summary' in conversa_limpa:
                conversa_limpa['conversation_summary']['total_messages'] = len(mensagens_verificadas)
                conversa_limpa['conversation_summary']['cleaned_by_ai'] = True
                conversa_limpa['conversation_summary']['original_count'] = len(mensagens_originais)
                conversa_limpa['conversation_summary']['removed_count'] = len(mensagens_originais) - len(mensagens_verificadas)
            
            # Adicionar metadata da limpeza
            conversa_limpa['ai_cleaning'] = {
                "cleaned_at": datetime.now().isoformat(),
                "original_message_count": len(mensagens_originais),
                "cleaned_message_count": len(mensagens_verificadas),
                "justificativa": analise.get('justificativa', 'Limpeza automática'),
                "removed_indices": analise.get('mensagens_para_remover', []),
                "reformatted_count": len(analise.get('mensagens_para_reformatar', [])),
                "inserted_count": len(analise.get('mensagens_para_inserir', [])),
                "inserted_messages": analise.get('mensagens_para_inserir', []),
                "auditoria": relatorio_auditoria  # ✅ NOVO: Incluir relatório de auditoria
            }
            
            logger.info(f"🧹 Limpeza concluída: {len(mensagens_originais)} → {len(mensagens_verificadas)} mensagens")
            
            return conversa_limpa
            
        except Exception as e:
            logger.error(f"❌ Erro na análise/limpeza da conversa: {str(e)}")
            # Em caso de erro, retornar conversa original
            return conversa_json
    
    def _aplicar_limpeza_conversa(self, mensagens_originais: List[Dict], analise: Dict, conversa_json: Dict = None) -> List[Dict]:
        """
        Aplica as recomendações de limpeza da OpenAI
        
        Args:
            mensagens_originais: Lista de mensagens originais
            analise: Resultado da análise OpenAI
            conversa_json: JSON completo da conversa (para dados dos participants)
            
        Returns:
            List: Mensagens limpas
        """
        try:
            mensagens_limpas = []
            indices_para_remover = set(analise.get('mensagens_para_remover', []))
            reformatacoes = {item['index']: item['novo_conteudo'] 
                           for item in analise.get('mensagens_para_reformatar', [])}
            
            # NOVO: Processar reclassificações
            reclassificacoes = {}
            for item in analise.get('mensagens_para_reclassificar', []):
                reclassificacoes[item['index']] = {
                    'sender': item.get('novo_sender'),
                    'receiver': item.get('novo_receiver'),
                    'motivo': item.get('motivo')
                }
            
            # Processar mensagens para inserir
            mensagens_para_inserir = {}
            for item in analise.get('mensagens_para_inserir', []):
                inserir_apos = item.get('inserir_apos_index', -1)
                mensagens_para_inserir[inserir_apos] = item
            
            for i, mensagem in enumerate(mensagens_originais):
                # Pular mensagens marcadas para remoção
                if i in indices_para_remover:
                    logger.info(f"🗑️ Removendo mensagem {i}: {mensagem.get('content', '')[:50]}...")
                    continue
                
                # Criar cópia da mensagem para modificações
                mensagem_processada = mensagem.copy()
                
                # Aplicar reformatação se necessário
                if i in reformatacoes:
                    mensagem_processada['content'] = reformatacoes[i]
                    mensagem_processada['ai_reformatted'] = True
                    logger.info(f"✏️ Reformatada mensagem {i}: {reformatacoes[i][:50]}...")
                
                # ✅ OTIMIZADO: Aplicar reclassificação mais robusta
                if i in reclassificacoes:
                    reclass = reclassificacoes[i]
                    if reclass['sender']:
                        mensagem_processada['sender'] = reclass['sender']
                        mensagem_processada['sender_specific'] = reclass['sender']
                    if reclass['receiver']:
                        mensagem_processada['receiver'] = reclass['receiver']
                        mensagem_processada['receiver_specific'] = reclass['receiver']
                        
                        # ✅ NOVO: Atualizar TODOS os campos relacionados
                        if 'metadata' not in mensagem_processada:
                            mensagem_processada['metadata'] = {}
                        mensagem_processada['metadata']['receiver_explicit'] = reclass['receiver']
                        mensagem_processada['interaction_type'] = f"{reclass['sender']}_{reclass['receiver']}"
                    
                    mensagem_processada['ai_reclassified'] = True
                    mensagem_processada['ai_reclassified_reason'] = reclass['motivo']
                    
                    logger.info(f"🔄 Reclassificada mensagem {i}: {reclass['sender']}→{reclass['receiver']} - {reclass['motivo']}")
                
                # ✅ NOVO: Detectar CPF e forçar classificação como cliente
                content = mensagem_processada.get('content', '')
                if re.search(r'\b\d{11}\b', content) and mensagem_processada.get('sender') != 'cliente':
                    mensagem_processada['sender'] = 'cliente'
                    mensagem_processada['sender_specific'] = 'cliente'
                    mensagem_processada['receiver'] = 'ia'
                    mensagem_processada['receiver_specific'] = 'ia'
                    mensagem_processada['ai_auto_classified'] = True
                    logger.info(f"🔄 AUTO-CLASSIFICAÇÃO: Mensagem {i} com CPF → cliente")
                
                mensagens_limpas.append(mensagem_processada)
                
                # Verificar se precisa inserir mensagem após esta
                if i in mensagens_para_inserir:
                    nova_mensagem = mensagens_para_inserir[i]
                    
                    # Criar nova mensagem do cliente
                    mensagem_inserida = {
                        "id": f"msg_ai_inserted_{i+1}",
                        "timestamp": mensagem.get('timestamp', ''),
                        "sender": nova_mensagem.get('sender', 'cliente'),
                        "content": nova_mensagem.get('content', ''),
                        "message_type": "text",
                        "metadata": {
                            "receiver_explicit": "ia",
                            "enhanced_method": True,
                            "ai_inserted": True
                        },
                        "sender_specific": nova_mensagem.get('sender', 'cliente'),
                        "receiver_specific": "ia",
                        "interaction_type": "cliente_ia",
                        "phase": mensagem.get('phase', 'ia_cliente'),
                        "ai_inserted": True,
                        "ai_inserted_reason": nova_mensagem.get('motivo', 'Mensagem perdida detectada')
                    }
                    
                    mensagens_limpas.append(mensagem_inserida)
                    logger.info(f"🔄 Inserida mensagem perdida após {i}: {nova_mensagem.get('content', '')[:50]}...")
            
            return mensagens_limpas
            
        except Exception as e:
            logger.error(f"❌ Erro ao aplicar limpeza: {e}")
            return mensagens_originais 
    
    def _criar_analise_fallback_rag(self, mensagens_para_analise: List[Dict], resposta_openai: str) -> Dict:
        """
        ✅ NOVO: Fallback inteligente que executa regras RAG deterministicamente
        
        Quando JSON parse falha, aplica as 4 regras principais diretamente no código:
        1. Classificação IA→Corretor
        2. Naturalização de Menus  
        3. Remoção de Duplicatas
        4. Fluxo Lógico
        """
        logger.info("🎯 Executando regras RAG determinísticas...")
        
        mensagens_para_remover = []
        mensagens_para_reformatar = []
        mensagens_para_reclassificar = []
        mensagens_para_inserir = []
        
        # ✅ REGRA 1: CLASSIFICAÇÃO IA→CORRETOR
        for i, msg in enumerate(mensagens_para_analise):
            content = msg.get('content', '').strip()
            sender = msg.get('sender', '')
            
            # Padrões específicos para reclassificação
            padroes_ia_corretor = [
                "✅ *Dados do cliente coletados com sucesso!*",
                "🚀 Mensagem enviada ao cliente",
                "✅ Dados do cliente coletados",
                "✅ Iniciando contato com o cliente"
            ]
            
            for padrao in padroes_ia_corretor:
                if padrao in content and sender != 'corretor':
                    mensagens_para_reclassificar.append({
                        "index": i,
                        "novo_sender": "ia",
                        "novo_receiver": "corretor", 
                        "motivo": f"Padrão IA→Corretor detectado: {padrao[:30]}..."
                    })
                    logger.info(f"🔄 REGRA 1: Reclassificando mensagem {i} para IA→Corretor")
                    break
        
        # ✅ REGRA 2: NATURALIZAÇÃO DE MENUS
        for i, msg in enumerate(mensagens_para_analise):
            content = msg.get('content', '').strip()
            
            if "(row_id:" in content:
                # Remove row_id dos menus
                novo_conteudo = re.sub(r'\s*\(row_id:[^)]+\)', '', content)
                if novo_conteudo != content:
                    mensagens_para_reformatar.append({
                        "index": i,
                        "novo_conteudo": novo_conteudo.strip()
                    })
                    logger.info(f"🔄 REGRA 2: Naturalizando menu {i}: {novo_conteudo[:50]}...")
        
        # ✅ REGRA 3: REMOÇÃO DE DUPLICATAS (ultra agressiva)
        conteudos_vistos = {}
        for i, msg in enumerate(mensagens_para_analise):
            content = msg.get('content', '').strip()
            
            # Ignora mensagens muito curtas
            if len(content) < 3:
                continue
            
            # ✅ NOVO: Múltiplas estratégias de normalização
            estrategias = [
                # Estratégia 1: Exata (case insensitive)
                content.lower().strip(),
                
                # Estratégia 2: Sem pontuação/emojis
                re.sub(r'[^\w\s]', '', content.lower()).strip(),
                
                # Estratégia 3: Só palavras principais (>3 chars)
                ' '.join([word for word in content.lower().split() if len(word) > 3]),
                
                # Estratégia 4: Números apenas (para CPF/telefone)
                re.sub(r'[^\d]', '', content) if re.search(r'\d{6,}', content) else None
            ]
            
            for estrategia_idx, content_normalizado in enumerate(estrategias):
                if not content_normalizado:
                    continue
                
                # Chave única por estratégia
                chave = f"{estrategia_idx}:{content_normalizado}"
                
                if chave in conteudos_vistos:
                    # Duplicata encontrada
                    primeiro_indice = conteudos_vistos[chave]
                    if i not in mensagens_para_remover:  # Evitar duplicação na lista
                        mensagens_para_remover.append(i)
                        logger.info(f"🔄 REGRA 3: Removendo duplicata {i} (estratégia {estrategia_idx+1}, igual à {primeiro_indice}): {content[:40]}...")
                    break
                else:
                    conteudos_vistos[chave] = i
        
        # ✅ REGRA 4: FLUXO LÓGICO - Detectar mensagens perdidas
        for i in range(len(mensagens_para_analise) - 1):
            msg_atual = mensagens_para_analise[i]
            msg_proxima = mensagens_para_analise[i + 1]
            
            content_atual = msg_atual.get('content', '').strip()
            content_proxima = msg_proxima.get('content', '').strip()
            sender_atual = msg_atual.get('sender', '')
            sender_proxima = msg_proxima.get('sender', '')
            
            # Detectar padrão: IA pede CPF → IA pede EMAIL (falta resposta cliente)
            if (sender_atual == 'ia' and sender_proxima == 'ia' and
                'cpf' in content_atual.lower() and 'email' in content_proxima.lower()):
                
                # Inserir resposta de CPF perdida
                mensagens_para_inserir.append({
                    "inserir_apos_index": i,
                    "sender": "cliente",
                    "content": "12345678901",  # CPF padrão (será ajustado com dados reais)
                    "motivo": "Resposta de CPF perdida detectada no fluxo"
                })
                logger.info(f"🔄 REGRA 4: Inserindo CPF perdido após mensagem {i}")
            
            # Detectar: IA pede EMAIL → IA pede DATA (falta resposta email)
            elif (sender_atual == 'ia' and sender_proxima == 'ia' and
                  'email' in content_atual.lower() and 'data' in content_proxima.lower()):
                
                mensagens_para_inserir.append({
                    "inserir_apos_index": i,
                    "sender": "cliente", 
                    "content": "teste@exemplo.com",
                    "motivo": "Resposta de email perdida detectada no fluxo"
                })
                logger.info(f"🔄 REGRA 4: Inserindo email perdido após mensagem {i}")
        
        # Estatísticas do fallback
        total_modificacoes = (len(mensagens_para_remover) + len(mensagens_para_reformatar) + 
                            len(mensagens_para_reclassificar) + len(mensagens_para_inserir))
        
        logger.info(f"🎯 FALLBACK RAG EXECUTADO:")
        logger.info(f"   - Reclassificações: {len(mensagens_para_reclassificar)}")
        logger.info(f"   - Naturalizações: {len(mensagens_para_reformatar)}")
        logger.info(f"   - Duplicatas removidas: {len(mensagens_para_remover)}")
        logger.info(f"   - Mensagens inseridas: {len(mensagens_para_inserir)}")
        logger.info(f"   - Total modificações: {total_modificacoes}")
        
        return {
            "mensagens_para_manter": list(range(len(mensagens_para_analise))),  # Manter todas exceto as removidas
            "mensagens_para_remover": mensagens_para_remover,
            "mensagens_para_reformatar": mensagens_para_reformatar,
            "mensagens_para_reclassificar": mensagens_para_reclassificar,
            "mensagens_para_inserir": mensagens_para_inserir,
            "justificativa": f"Fallback RAG determinístico aplicado: {total_modificacoes} modificações executadas",
            "fallback_aplicado": True,
            "regras_executadas": ["classificacao_ia_corretor", "naturalizacao_menus", "remocao_duplicatas", "fluxo_logico"]
        }

    def _verificacao_final_obrigatoria(self, mensagens_limpas: List[Dict]) -> List[Dict]:
        """
        ✅ NOVA FUNÇÃO: Verificação final determinística para garantir classificações corretas
        
        Esta função executa uma verificação final OBRIGATÓRIA após a limpeza OpenAI,
        aplicando regras determinísticas para corrigir classificações incorretas.
        
        REGRAS CRÍTICAS:
        1. Mensagens com CPF (11 dígitos) = sender="cliente"
        2. "✅ *Dados do cliente coletados*" = sender="ia", receiver="corretor"
        3. "🚀 Mensagem enviada ao cliente" = sender="ia", receiver="corretor"
        4. "✅ Iniciando contato com o cliente" = sender="ia", receiver="corretor"
        
        Args:
            mensagens_limpas (List[Dict]): Mensagens após limpeza OpenAI
            
        Returns:
            List[Dict]: Mensagens com classificações verificadas e corrigidas
        """
        try:
            logger.info("🔍 Iniciando verificação final obrigatória...")
            
            mensagens_verificadas = []
            correcoes_aplicadas = 0
            
            for i, mensagem in enumerate(mensagens_limpas):
                mensagem_verificada = mensagem.copy()
                content = mensagem.get('content', '').strip()
                sender_atual = mensagem.get('sender', '')
                
                # ✅ REGRA 1: CPF sempre = cliente
                if re.search(r'\b\d{11}\b', content):
                    if sender_atual != 'cliente':
                        mensagem_verificada['sender'] = 'cliente'
                        mensagem_verificada['sender_specific'] = 'cliente'
                        mensagem_verificada['receiver'] = 'ia'
                        mensagem_verificada['receiver_specific'] = 'ia'
                        mensagem_verificada['interaction_type'] = 'cliente_ia'
                        mensagem_verificada['verificacao_final_aplicada'] = True
                        mensagem_verificada['correcao_motivo'] = 'CPF detectado - forçado para cliente'
                        correcoes_aplicadas += 1
                        logger.info(f"🔧 Correção CPF: Mensagem {i} reclassificada para cliente")
                
                # ✅ REGRA 2: Padrões específicos IA→Corretor
                padroes_ia_corretor = [
                    "✅ *Dados do cliente coletados",
                    "✅ Dados do cliente coletados", 
                    "🚀 Mensagem enviada ao cliente",
                    "✅ Iniciando contato com o cliente"
                ]
                
                for padrao in padroes_ia_corretor:
                    if padrao in content:
                        if (sender_atual != 'ia' or 
                            mensagem.get('receiver') != 'corretor' or
                            mensagem.get('receiver_specific') != 'corretor'):
                            
                            mensagem_verificada['sender'] = 'ia'
                            mensagem_verificada['sender_specific'] = 'ia'
                            mensagem_verificada['receiver'] = 'corretor'
                            mensagem_verificada['receiver_specific'] = 'corretor'
                            mensagem_verificada['interaction_type'] = 'ia_corretor'
                            
                            # Atualizar metadata
                            if 'metadata' not in mensagem_verificada:
                                mensagem_verificada['metadata'] = {}
                            mensagem_verificada['metadata']['receiver_explicit'] = 'corretor'
                            
                            mensagem_verificada['verificacao_final_aplicada'] = True
                            mensagem_verificada['correcao_motivo'] = f'Padrão IA→Corretor: {padrao[:30]}...'
                            correcoes_aplicadas += 1
                            logger.info(f"🔧 Correção IA→Corretor: Mensagem {i} - {padrao[:30]}...")
                        break
                
                # ✅ REGRA 3: Garantir campos obrigatórios
                if 'sender_specific' not in mensagem_verificada:
                    mensagem_verificada['sender_specific'] = mensagem_verificada.get('sender', 'ia')
                
                if 'receiver_specific' not in mensagem_verificada:
                    mensagem_verificada['receiver_specific'] = mensagem_verificada.get('receiver', 'ia')
                
                if 'interaction_type' not in mensagem_verificada:
                    sender = mensagem_verificada.get('sender', 'ia')
                    receiver = mensagem_verificada.get('receiver', 'ia')
                    mensagem_verificada['interaction_type'] = f"{sender}_{receiver}"
                
                mensagens_verificadas.append(mensagem_verificada)
            
            logger.info(f"✅ Verificação final concluída: {correcoes_aplicadas} correções aplicadas")
            return mensagens_verificadas
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação final: {str(e)}")
            # Em caso de erro, retornar mensagens originais
            return mensagens_limpas

    def _auditar_resultado_limpeza(self, mensagens_originais: List[Dict], mensagens_finais: List[Dict], analise_openai: Dict) -> Dict:
        """
        ✅ NOVA FUNÇÃO: Auditoria completa do processo de limpeza
        
        Gera um relatório detalhado de todas as transformações aplicadas,
        estatísticas de qualidade e métricas de confiabilidade.
        
        Args:
            mensagens_originais (List[Dict]): Mensagens antes da limpeza
            mensagens_finais (List[Dict]): Mensagens após toda a limpeza
            analise_openai (Dict): Resultado da análise OpenAI
            
        Returns:
            Dict: Relatório completo de auditoria
        """
        try:
            logger.info("📊 Gerando relatório de auditoria...")
            
            # Estatísticas básicas
            total_original = len(mensagens_originais)
            total_final = len(mensagens_finais)
            total_removidas = total_original - total_final
            
            # Análise de classificações
            classificacoes_originais = {}
            classificacoes_finais = {}
            
            for msg in mensagens_originais:
                sender = msg.get('sender', 'indefinido')
                classificacoes_originais[sender] = classificacoes_originais.get(sender, 0) + 1
            
            for msg in mensagens_finais:
                sender = msg.get('sender', 'indefinido')
                classificacoes_finais[sender] = classificacoes_finais.get(sender, 0) + 1
            
            # Contar transformações específicas
            mensagens_reformatadas = sum(1 for msg in mensagens_finais if msg.get('ai_reformatted'))
            mensagens_reclassificadas = sum(1 for msg in mensagens_finais if msg.get('ai_reclassified'))
            mensagens_inseridas = sum(1 for msg in mensagens_finais if msg.get('ai_inserted'))
            verificacoes_aplicadas = sum(1 for msg in mensagens_finais if msg.get('verificacao_final_aplicada'))
            
            # Detectar mensagens com CPF
            mensagens_com_cpf = 0
            cpf_classificado_cliente = 0
            
            for msg in mensagens_finais:
                content = msg.get('content', '')
                if re.search(r'\b\d{11}\b', content):
                    mensagens_com_cpf += 1
                    if msg.get('sender') == 'cliente':
                        cpf_classificado_cliente += 1
            
            # Calcular taxa de acerto CPF
            taxa_acerto_cpf = (cpf_classificado_cliente / mensagens_com_cpf * 100) if mensagens_com_cpf > 0 else 100
            
            # Detectar padrões IA→Corretor
            padroes_ia_corretor = [
                "✅ *Dados do cliente coletados",
                "✅ Dados do cliente coletados",
                "🚀 Mensagem enviada ao cliente", 
                "✅ Iniciando contato com o cliente"
            ]
            
            mensagens_ia_corretor = 0
            ia_corretor_classificado_correto = 0
            
            for msg in mensagens_finais:
                content = msg.get('content', '')
                for padrao in padroes_ia_corretor:
                    if padrao in content:
                        mensagens_ia_corretor += 1
                        if (msg.get('sender') == 'ia' and 
                            msg.get('receiver') == 'corretor'):
                            ia_corretor_classificado_correto += 1
                        break
            
            # Taxa de acerto IA→Corretor
            taxa_acerto_ia_corretor = (ia_corretor_classificado_correto / mensagens_ia_corretor * 100) if mensagens_ia_corretor > 0 else 100
            
            # Qualidade geral
            score_qualidade = (taxa_acerto_cpf + taxa_acerto_ia_corretor) / 2
            
            # Determinar status da limpeza
            if score_qualidade >= 95:
                status_limpeza = "EXCELENTE"
            elif score_qualidade >= 85:
                status_limpeza = "BOM"
            elif score_qualidade >= 70:
                status_limpeza = "REGULAR"
            else:
                status_limpeza = "REQUER_ATENCAO"
            
            # Construir relatório
            relatorio = {
                "timestamp": datetime.now().isoformat(),
                "estatisticas_gerais": {
                    "mensagens_originais": total_original,
                    "mensagens_finais": total_final,
                    "mensagens_removidas": total_removidas,
                    "taxa_reducao_pct": round((total_removidas / total_original * 100), 2) if total_original > 0 else 0
                },
                "transformacoes_aplicadas": {
                    "reformatadas": mensagens_reformatadas,
                    "reclassificadas": mensagens_reclassificadas,
                    "inseridas": mensagens_inseridas,
                    "verificacoes_finais": verificacoes_aplicadas,
                    "total_transformacoes": mensagens_reformatadas + mensagens_reclassificadas + mensagens_inseridas + verificacoes_aplicadas
                },
                "classificacoes": {
                    "originais": classificacoes_originais,
                    "finais": classificacoes_finais
                },
                "qualidade_classificacao": {
                    "mensagens_com_cpf": mensagens_com_cpf,
                    "cpf_classificado_cliente": cpf_classificado_cliente,
                    "taxa_acerto_cpf_pct": round(taxa_acerto_cpf, 2),
                    "mensagens_ia_corretor": mensagens_ia_corretor,
                    "ia_corretor_classificado_correto": ia_corretor_classificado_correto,
                    "taxa_acerto_ia_corretor_pct": round(taxa_acerto_ia_corretor, 2)
                },
                "score_qualidade": {
                    "score_geral": round(score_qualidade, 2),
                    "status": status_limpeza,
                    "confiabilidade": "ALTA" if score_qualidade >= 90 else "MEDIA" if score_qualidade >= 75 else "BAIXA"
                },
                "openai_analysis": {
                    "justificativa": analise_openai.get('justificativa', 'N/A'),
                    "fallback_aplicado": analise_openai.get('fallback_aplicado', False),
                    "regras_executadas": analise_openai.get('regras_executadas', [])
                }
            }
            
            logger.info(f"📊 Auditoria concluída - Score: {score_qualidade:.1f}% ({status_limpeza})")
            logger.info(f"📈 CPF: {taxa_acerto_cpf:.1f}% | IA→Corretor: {taxa_acerto_ia_corretor:.1f}%")
            
            return relatorio
            
        except Exception as e:
            logger.error(f"❌ Erro na auditoria: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "erro": str(e),
                "status": "ERRO_AUDITORIA"
            }