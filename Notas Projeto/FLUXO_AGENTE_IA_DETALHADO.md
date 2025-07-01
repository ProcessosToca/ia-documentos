# 🤖 AGENTE IA - TOCA IMÓVEIS

## 📁 Estrutura Simplificada

```
toca_imoveis_agent/
├── src/
│   ├── config.py               # Configurações e credenciais
│   │
│   ├── models/
│   │   ├── negotiation.py     # Modelo de negociação
│   │   └── document.py        # Modelo de documentos
│   │
│   ├── services/
│   │   ├── whatsapp.py        # Integração WhatsApp
│   │   ├── openai_service.py  # Processamento de linguagem
│   │   └── vision_service.py  # OCR de documentos
│   │
│   ├── handlers/
│   │   ├── broker.py          # Lógica do corretor
│   │   └── documents.py       # Processamento docs
│   │
│   └── utils.py               # Funções auxiliares
│
├── tests/                     # Testes básicos
├── .env.example              # Template de variáveis
├── requirements.txt          # Dependências
└── main.py                   # Inicialização
```

## 🔄 Fluxo Principal

```mermaid
graph TD
    A[Corretor] -->|WhatsApp| B[broker.py]
    B -->|Criar| C[negotiation.py]
    C -->|Processar| D[openai_service.py]
    D -->|Docs| E[vision_service.py]
    E -->|Salvar| F[Supabase]
```

## ⚙️ Componentes Essenciais

1. **broker.py**
   - Recebe mensagem do corretor
   - Inicia negociação
   - Solicita dados do cliente

2. **documents.py**
   - Processa documentos recebidos
   - Valida com OCR
   - Salva no Supabase

3. **services/**
   - WhatsApp: Comunicação
   - OpenAI: Processamento texto
   - Vision: Validação documentos

## 📋 Fluxo do Agente IA

1. **CORRETOR inicia o processo**
   - Envia mensagem para IA
   - IA mostra menu "Realizar Fechamento Locação Sem Fiador"
   - Corretor informa: Nome Cliente + Telefone Cliente + Nome Corretor

2. **IA inicia comunicação com CLIENTE**
   - Envia mensagem confirmando dados
   - Inicia fluxo de documentação
   - Coleta documentos do cliente

3. **IA processa documentos**
   - Salva no banco Supabase
   - Salva no storage
   - Valida documentos usando OCR

## 🔑 Credenciais e Configurações

```python
# Supabase
SUPABASE_URL = "https://rqyyoofuwrwwfcuxfjwu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxeXlvb2Z1d3J3d2ZjdXhmand1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTAwODk2MjUsImV4cCI6MjA2NTY2NTYyNX0.lBOrYvRIGEhLLMgcaaooS9-w2M8VAZW_4rQYFxc6abE"

# Integrações
- WhatsApp API
- OpenAI
- Google Cloud Vision
```

## 📊 Tabelas do Agente

### 1. ai_negotiations
```sql
CREATE TABLE ai_negotiations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_name TEXT NOT NULL,
  client_phone TEXT NOT NULL,
  status ai_negotiation_status NOT NULL DEFAULT 'iniciada',
  broker_id UUID REFERENCES system_users(id),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
);
```

### 2. ai_conversations
```sql
CREATE TABLE ai_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  negotiation_id UUID REFERENCES ai_negotiations(id),
  sender TEXT NOT NULL,      -- 'ia', 'cliente', 'corretor'
  message TEXT NOT NULL,
  timestamp TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### 3. ai_documents
```sql
CREATE TABLE ai_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  negotiation_id UUID REFERENCES ai_negotiations(id),
  document_type_id UUID REFERENCES ai_document_types(id),
  file_path TEXT NOT NULL,
  status document_status DEFAULT 'pendente'
);
```

## 💻 Estrutura do Agente

```
ai_agent_vps/
├── main.py                 # Webhook WhatsApp + Rotas
├── services/
│   ├── whatsapp.py        # Integração WhatsApp
│   ├── supabase.py        # Operações Banco
│   ├── openai.py          # Processamento Linguagem
│   └── vision.py          # OCR Documentos
└── requirements.txt
```

## ⚙️ Requisitos Mínimos

```python
# requirements.txt
supabase==2.3.4
flask==3.0.0
requests==2.31.0
python-dotenv==1.0.0
openai==1.12.0
google-cloud-vision==3.4.4
```

## 🚀 Deploy VPS

```bash
# Instalar
sudo apt update && sudo apt install python3 python3-pip
git clone [repo] && cd ai_agent_vps
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Rodar
python main.py  # Inicia webhook na porta 8080
```

## 📁 Estrutura de Pastas Detalhada

```
toca_imoveis_agent/
│
├── src/
│   ├── core/                    # Núcleo da aplicação
│   │   ├── __init__.py
│   │   ├── config.py           # Configurações e variáveis de ambiente
│   │   ├── database.py         # Conexão Supabase
│   │   └── exceptions.py       # Exceções customizadas
│   │
│   ├── models/                 # Modelos de dados
│   │   ├── __init__.py
│   │   ├── negotiation.py      # Modelo de negociação
│   │   ├── conversation.py     # Modelo de conversas
│   │   └── document.py         # Modelo de documentos
│   │
│   ├── services/               # Serviços externos
│   │   ├── __init__.py
│   │   ├── whatsapp/          # Integração WhatsApp
│   │   │   ├── __init__.py
│   │   │   ├── client.py      # Cliente WhatsApp
│   │   │   └── handlers.py    # Handlers de mensagens
│   │   │
│   │   ├── ai/                # Serviços de IA
│   │   │   ├── __init__.py
│   │   │   ├── openai.py      # Integração OpenAI
│   │   │   └── vision.py      # Google Cloud Vision
│   │   │
│   │   └── storage/           # Gerenciamento de arquivos
│   │       ├── __init__.py
│   │       └── supabase.py    # Upload/Download Supabase
│   │
│   ├── handlers/              # Handlers de negócio
│   │   ├── __init__.py
│   │   ├── broker.py         # Lógica do corretor
│   │   ├── client.py         # Lógica do cliente
│   │   └── documents.py      # Processamento docs
│   │
│   └── utils/                # Utilitários
│       ├── __init__.py
│       ├── validators.py     # Validadores
│       ├── formatters.py     # Formatadores
│       └── logger.py         # Configuração de logs
│
├── tests/                    # Testes
│   ├── __init__.py
│   ├── conftest.py          # Configurações pytest
│   ├── test_handlers/       # Testes dos handlers
│   ├── test_services/       # Testes dos serviços
│   └── test_models/         # Testes dos modelos
│
├── scripts/                  # Scripts úteis
│   ├── setup_db.py          # Setup inicial do banco
│   └── generate_docs.py     # Gerador de documentação
│
├── docs/                     # Documentação
│   ├── setup.md             # Guia de instalação
│   ├── architecture.md      # Arquitetura do sistema
│   └── api.md              # Documentação da API
│
├── .env.example             # Template de variáveis de ambiente
├── requirements.txt         # Dependências principais
├── requirements-dev.txt     # Dependências de desenvolvimento
├── pytest.ini              # Configuração de testes
├── Dockerfile              # Configuração Docker
├── docker-compose.yml      # Compose para desenvolvimento
└── README.md              # Documentação principal
```

### 📝 Descrição dos Componentes Principais

1. **core/**
   - Configurações centrais
   - Conexão com banco
   - Tratamento de erros

2. **models/**
   - Modelos de dados Supabase
   - Validações de schema
   - Relacionamentos

3. **services/**
   - Integrações externas
   - Clientes API
   - Processamento IA

4. **handlers/**
   - Lógica de negócio
   - Fluxos de conversa
   - Processamento documentos

5. **utils/**
   - Funções auxiliares
   - Formatadores
   - Logging

### 🔄 Fluxo de Dados

```mermaid
graph TD
    A[Corretor] -->|WhatsApp| B[handlers/broker.py]
    B -->|Criar Negociação| C[models/negotiation.py]
    C -->|Processar Mensagem| D[services/ai/openai.py]
    D -->|Enviar Resposta| E[services/whatsapp/client.py]
    E -->|Receber Docs| F[handlers/documents.py]
    F -->|Validar| G[services/ai/vision.py]
    G -->|Salvar| H[services/storage/supabase.py]
```

### 🛠️ Padrões de Projeto Utilizados

1. **Repository Pattern**
   - Abstração do banco de dados
   - Modelos em `models/`

2. **Service Layer**
   - Integrações externas em `services/`
   - Lógica de negócio em `handlers/`

3. **Dependency Injection**
   - Configuração em `core/`
   - Injeção nos serviços

4. **Factory Pattern**
   - Criação de clientes API
   - Instanciação de serviços 

# 🔍 Fluxo de Identificação de Usuários - V1

## 📋 Visão Geral
Este documento detalha o fluxo de identificação de usuários (clientes e corretores) implementado no arquivo `buscar_usuarios_supabase.py`.

## 🔄 Fluxograma do Processo

```mermaid
graph TD
    A[Início - Recebe CPF] --> B{Validar CPF}
    
    B -->|Inválido| C[Retorna Erro de CPF Inválido]
    
    B -->|Válido| D[Formata CPF]
    
    D --> E{Busca Colaborador no Supabase}
    
    E -->|Encontrado| F{Verifica se está Ativo}
    F -->|Ativo| G[Retorna Dados do Colaborador]
    F -->|Inativo| H[Retorna Colaborador Inativo]
    
    E -->|Não Encontrado| I[Processa como Cliente]
    
    I --> J{Busca Cliente por CPF}
    
    J -->|Não Encontrado| K[Retorna Cliente Não Cadastrado]
    
    J -->|Encontrado| L{Verifica Telefone}
    
    L -->|Sem Telefone| M[Solicita Telefone]
    
    L -->|Com Telefone| N{Busca Negociação Ativa}
    
    N -->|Sem Negociação| O[Retorna Cliente sem Negociação]
    
    N -->|Com Negociação| P[Analisa Documentos]
    
    P --> Q[Busca Conversas]
    
    Q --> R[Análise GPT]
    
    R --> S[Retorna Resposta Completa]
```

## 📝 Detalhamento das Etapas

### 1. Entrada do Processo
- Recebe CPF do usuário
- Opcionalmente recebe telefone
- Função principal: `identificar_tipo_usuario(cpf: str, telefone: str = None)`

### 2. Validação Inicial
- Verifica formato do CPF
- Remove caracteres especiais
- Confirma se tem 11 dígitos
- Função: `validar_formatar_cpf(cpf: str)`

### 3. Busca de Colaborador
- Procura primeiro na tabela `system_users`
- Verifica com CPF formatado e depois limpo
- Valida se o colaborador está ativo
- Função: `buscar_usuario_por_cpf(cpf: str)`

### 4. Processamento de Cliente
- Se não for colaborador, busca na tabela `clientes`
- Verifica existência de cadastro
- Função: `buscar_cliente_por_cpf(cpf: str)`

### 5. Análise de Negociação
- Busca negociações ativas pelo telefone
- Analisa documentos pendentes
- Recupera histórico de conversas
- Funções:
  - `buscar_negociacao_ativa(telefone: str)`
  - `analisar_documentos_faltantes(negotiation_id: str)`
  - `buscar_conversas_ia_cliente(negotiation_id: str)`

## 🔄 Tipos de Retorno

### 1. Para Colaboradores
```json
{
    "tipo": "colaborador",
    "cpf_valido": true,
    "dados_usuario": {
        "nome": "Nome do Colaborador",
        "setor": "Setor",
        "funcao": "Função"
    }
}
```

### 2. Para Clientes
```json
{
    "tipo": "cliente",
    "cliente_cadastrado": true,
    "dados_cliente": {},
    "negociacao_ativa": true,
    "analise_documentos": {},
    "analise_gpt": {}
}
```

### 3. Para Erros
```json
{
    "tipo": "erro",
    "cpf_valido": false,
    "mensagem": "Descrição do erro"
}
```

## 🔒 Segurança e Validações

1. **Validação de CPF**
   - Remove caracteres especiais
   - Verifica quantidade de dígitos
   - Formata para padrão XXX.XXX.XXX-XX

2. **Verificação de Acesso**
   - Valida se colaborador está ativo
   - Verifica permissões do usuário

3. **Tratamento de Erros**
   - Logs detalhados de erros
   - Mensagens amigáveis para usuário
   - Rastreamento de exceções

## 📊 Métricas e Logs

- Logs detalhados de cada etapa
- Rastreamento de tempo de processamento
- Registro de erros e exceções
- Monitoramento de performance

## 🔄 Versão Atual

- Versão: 1.0
- Data: Março/2024
- Arquivo: `buscar_usuarios_supabase.py` 