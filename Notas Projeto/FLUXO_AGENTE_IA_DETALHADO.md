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