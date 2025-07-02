import os
import re
import json
from openai import OpenAI
from typing import Dict, Any, List
import logging

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
                model="gpt-3.5-turbo",
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
                # Tentar fazer parse do JSON
                resultado = json.loads(resposta_texto)
                
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
                # Fallback: continuar fluxo normal
                return {
                    "intencao": "conversa_normal",
                    "confianca": 0.0,
                    "bypass_fluxo": False,
                    "contexto": "usuario_conhecido", 
                    "acao_sugerida": "continuar_fluxo",
                    "erro": "json_parse_error"
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
                model="gpt-3.5-turbo",
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
                # Parse do JSON
                resultado = json.loads(resposta_texto)
                
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
                # Fallback: considerar inválido se não conseguir processar
                return {
                    "valido": False,
                    "motivo_erro": "Erro interno na validação",
                    "sugestao": f"Tente novamente com um {tipo_dado} mais claro",
                    "erro_processamento": str(e)
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
            prompt_sistema = """
            Você é um ESPECIALISTA em NEGOCIAÇÃO DE LOCAÇÃO IMOBILIÁRIA e assistente para colaboradores da Toca Imóveis.

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
            - Se não souber algo específico da Toca Imóveis, seja transparente
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

            Responda esta dúvida de forma especializada, considerando que é um colaborador da Toca Imóveis que precisa de orientação prática para seu trabalho diário.

            Formate sua resposta em JSON com:
            - "resposta": Resposta detalhada e prática para a dúvida
            - "categoria": Categoria da dúvida (documentos|processo|juridico|relacionamento|financeiro|outros)
            - "confianca": Nível de confiança da resposta (alto|medio|baixo)
            - "sugestoes_extras": Array com sugestões adicionais ou próximos passos (máximo 3 sugestões)
            """

            # Fazer chamada para GPT-4
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
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
                # Tentar fazer parse do JSON
                resultado = json.loads(resposta_texto)
                
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
                logger.warning(f"⚠️ Resposta não é JSON válido: {str(e)}")
                
                # Limpar a resposta e usar como texto
                resposta_limpa = resposta_texto.replace('```json', '').replace('```', '').strip()
                
                # Tentar extrair pelo menos a resposta principal
                if '"resposta"' in resposta_limpa:
                    match = re.search(r'"resposta":\s*"([^"]*)"', resposta_limpa)
                    if match:
                        resposta_limpa = match.group(1).replace('\\n', '\n')
                
                return {
                    "sucesso": True,
                    "resposta": resposta_limpa,
                    "categoria": "geral",
                    "confianca": "medio",
                    "sugestoes_extras": ["Posso esclarecer mais detalhes se precisar"],
                    "colaborador": nome_colaborador,
                    "setor": setor_colaborador,
                    "aviso": "Resposta processada como texto livre"
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