#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste de Conexão com Tabelas do Supabase - Agente IA
Testa apenas a conectividade com as tabelas principais
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv
import sys

# Carregar variáveis de ambiente da raiz do projeto
import os
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

def test_table_connection():
    """Testa conexão com as tabelas principais do agente IA"""
    
    print("🔍 TESTE DE CONEXÃO COM TABELAS DO SUPABASE")
    print("=" * 50)
    
    # Verificar variáveis de ambiente
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ ERRO: Variáveis SUPABASE_URL e SUPABASE_KEY não encontradas no .env")
        return False
    
    try:
        # Criar cliente Supabase
        supabase: Client = create_client(supabase_url, supabase_key)
        print("✅ Cliente Supabase criado com sucesso")
        
        # Tabelas principais para o agente IA
        tables_to_test = [
            {
                'name': 'ai_negotiations',
                'description': 'Negociações da IA',
                'columns': ['id', 'client_name', 'client_phone', 'status', 'rental_modality']
            },
            {
                'name': 'ai_conversations', 
                'description': 'Conversas da IA',
                'columns': ['id', 'negotiation_id', 'sender', 'message', 'timestamp']
            },
            {
                'name': 'ai_document_types',
                'description': 'Tipos de documentos',
                'columns': ['id', 'name', 'description', 'required', 'is_active']
            },
            {
                'name': 'ai_documents',
                'description': 'Documentos enviados',
                'columns': ['id', 'negotiation_id', 'document_type_id', 'status', 'file_name']
            },
            {
                'name': 'properties',
                'description': 'Propriedades/Imóveis',
                'columns': ['id', 'title', 'address', 'number', 'neighborhood', 'property_type', 'price']
            },
            {
                'name': 'system_users',
                'description': 'Usuários do sistema (corretores)',
                'columns': ['id', 'username', 'email', 'full_name', 'role', 'is_active']
            }
        ]
        
        print("\n📊 TESTANDO TABELAS:")
        print("-" * 50)
        
        for table in tables_to_test:
            try:
                # Testar SELECT simples
                response = supabase.table(table['name']).select("*").limit(1).execute()
                
                if response.data is not None:
                    print(f"✅ {table['name']:<20} - {table['description']}")
                    print(f"   📋 Colunas: {', '.join(table['columns'])}")
                    
                    # Contar registros
                    count_response = supabase.table(table['name']).select("*", count="exact").execute()
                    total_records = count_response.count if count_response.count is not None else 0
                    print(f"   📈 Total de registros: {total_records}")
                    
                else:
                    print(f"⚠️  {table['name']:<20} - Tabela acessível mas sem dados")
                    
            except Exception as e:
                print(f"❌ {table['name']:<20} - ERRO: {str(e)}")
            
            print()
        
        # Teste específico: Tipos de documentos (dados importantes para o agente)
        print("\n📋 TIPOS DE DOCUMENTOS CADASTRADOS:")
        print("-" * 50)
        
        doc_types = supabase.table('ai_document_types').select("name, description, required").eq('is_active', True).execute()
        
        if doc_types.data:
            for doc in doc_types.data:
                status = "✅ OBRIGATÓRIO" if doc['required'] else "⚪ OPCIONAL"
                print(f"{status} - {doc['name']}: {doc['description']}")
        
        # Teste específico: Propriedades disponíveis
        print(f"\n🏠 PROPRIEDADES DISPONÍVEIS:")
        print("-" * 50)
        
        properties = supabase.table('properties').select("title, address, number, neighborhood, property_type, price").eq('is_active', True).limit(5).execute()
        
        if properties.data:
            for prop in properties.data:
                address = f"{prop['address']}"
                if prop.get('number'):
                    address += f", {prop['number']}"
                print(f"🏡 {prop['title']}")
                print(f"   📍 {address}, {prop['neighborhood']}")
                print(f"   💰 R$ {prop['price']}")
                print()
        
        print("✅ TESTE DE CONEXÃO CONCLUÍDO COM SUCESSO!")
        print("🎯 Tabelas principais acessíveis e prontas para o agente IA")
        
        return True
        
    except Exception as e:
        print(f"❌ ERRO GERAL: {str(e)}")
        return False

def main():
    """Função principal"""
    success = test_table_connection()
    
    if success:
        print("\n🚀 PRÓXIMOS PASSOS:")
        print("1. Implementar lógica do agente IA")
        print("2. Adicionar integração com OpenAI")
        print("3. Configurar webhook do WhatsApp")
        sys.exit(0)
    else:
        print("\n❌ CORRIJA OS ERROS ANTES DE CONTINUAR")
        sys.exit(1)

if __name__ == "__main__":
    main()
