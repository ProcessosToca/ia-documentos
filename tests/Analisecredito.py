#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import requests
import json
import base64
import math
from datetime import datetime
from dotenv import load_dotenv
from colorama import init, Fore, Back, Style

# Imports para PDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, String, Circle, Rect, Line
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart

# Inicializar colorama para cores no terminal
init(autoreset=True)

# Carregar variáveis de ambiente
load_dotenv()

# ============================================================================
# CLASSE ASSERTIVA CLIENT
# ============================================================================

class AssertivaClient:
    def __init__(self):
        self.base_url = os.getenv('ASSERTIVA_BASE_URL', 'https://api.assertivasolucoes.com.br')
        self.auth_url = os.getenv('ASSERTIVA_AUTH_URL', 'https://api.assertivasolucoes.com.br/oauth2/v3/token')
        self.score_url = os.getenv('ASSERTIVA_SCORE_URL', 'https://api.assertivasolucoes.com.br/score/v3/pf/credito')
        self.access_token = None
        self.token_expiry = None

    def authenticate(self):
        """Autentica com a API Assertiva usando OAuth2 com Basic Auth"""
        try:
            print("�� Autenticando com a API Assertiva...")
            
            # Criar Basic Auth com client_id e client_secret
            client_id = os.getenv('ASSERTIVA_CLIENT_ID')
            client_secret = os.getenv('ASSERTIVA_TOKEN')
            
            if not client_id or not client_secret:
                raise Exception("Credenciais não configuradas no arquivo .env")
            
            credentials = f"{client_id}:{client_secret}"
            base64_credentials = base64.b64encode(credentials.encode()).decode()
            
            auth_data = {
                'grant_type': 'client_credentials'
            }

            headers = {
                'Authorization': f'Basic {base64_credentials}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }

            response = requests.post(self.auth_url, data=auth_data, headers=headers)
            response.raise_for_status()

            data = response.json()
            if 'access_token' in data:
                self.access_token = data['access_token']
                # Token expira em 1 hora (3600 segundos)
                self.token_expiry = datetime.now().timestamp() + data.get('expires_in', 3600)
                print("✅ Autenticação realizada com sucesso!")
                return self.access_token
            else:
                raise Exception("Token de acesso não encontrado na resposta")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na autenticação: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Resposta: {e.response.text}")
            raise

    def is_token_valid(self):
        """Verifica se o token ainda é válido"""
        return self.access_token and self.token_expiry and datetime.now().timestamp() < self.token_expiry

    def get_valid_token(self):
        """Obtém um token válido (renova se necessário)"""
        if not self.is_token_valid():
            self.authenticate()
        return self.access_token

    def consultar_score_credito(self, cpf, id_finalidade='2', opcoes='ACOES,POSITIVO'):
        """Consulta score de crédito restritivo por CPF"""
        try:
            print(f"🔍 Consultando score de crédito restritivo para CPF: {cpf}")
            print(f"📋 Finalidade: {id_finalidade} ({'Ciclo de crédito' if id_finalidade == '2' else 'Execução de contrato'})")
            print(f"🔧 Opções: {opcoes}")
            
            token = self.get_valid_token()
            url = f"{self.score_url}/{cpf}?idFinalidade={id_finalidade}&opcoes={opcoes}"
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }

            response = requests.get(url, headers=headers)
            response.raise_for_status()

            print("✅ Consulta realizada com sucesso!")
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Erro na consulta: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Resposta: {e.response.text}")
            raise

    def formatar_cpf(self, cpf):
        """Formata CPF para exibição (XXX.XXX.XXX-XX)"""
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        if len(cpf_limpo) == 11:
            return f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
        return cpf

    def exibir_resultados(self, documento, dados):
        """Exibe os resultados da consulta de forma organizada"""
        print("\n" + "=" * 60)
        documento_formatado = self.formatar_cpf(documento)
        print(f"📊 RESULTADOS DA CONSULTA - CPF: {documento_formatado}")
        print("=" * 60)
        
        if dados and isinstance(dados, dict):
            print(json.dumps(dados, indent=2, ensure_ascii=False))
        else:
            print("Dados recebidos:", dados)
        
        print("=" * 60 + "\n")

# ============================================================================
# CLASSE PDF GENERATOR
# ============================================================================

class PDFGeneratorPro:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
        self.colors = {
            'primary': colors.HexColor('#1a365d'),
            'secondary': colors.HexColor('#2d3748'),
            'accent': colors.HexColor('#3182ce'),
            'success': colors.HexColor('#38a169'),
            'warning': colors.HexColor('#d69e2e'),
            'danger': colors.HexColor('#e53e3e'),
            'light': colors.HexColor('#f7fafc'),
            'gray': colors.HexColor('#4a5568'),
            'light_gray': colors.HexColor('#718096')
        }

    def setup_custom_styles(self):
        """Configura estilos customizados profissionais com tipografia moderna"""
        # Título principal moderno e centralizado
        if 'ModernTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ModernTitle',
                parent=self.styles['Heading1'],
                fontSize=24,
                spaceAfter=8,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#1a365d'),
                fontName='Helvetica-Bold',
                leading=28
            ))

        # Subtítulo elegante
        if 'ModernSubtitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ModernSubtitle',
                parent=self.styles['Heading2'],
                fontSize=14,
                spaceAfter=6,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#4a5568'),
                fontName='Helvetica',
                leading=16
            ))

        # Seções modernas
        if 'ModernSection' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='ModernSection',
                parent=self.styles['Heading2'],
                fontSize=13,
                spaceAfter=12,
                spaceBefore=20,
                textColor=colors.HexColor('#2d3748'),
                fontName='Helvetica-Bold',
                leading=15
            ))

        # Títulos de tabela centralizados
        if 'TableHeader' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableHeader',
                parent=self.styles['Normal'],
                fontSize=11,
                fontName='Helvetica-Bold',
                alignment=TA_CENTER,
                textColor=colors.white,
                leading=13
            ))

        # Dados de tabela
        if 'TableData' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableData',
                parent=self.styles['Normal'],
                fontSize=10,
                fontName='Helvetica',
                leading=12
            ))

        # Valores monetários alinhados à direita
        if 'TableMoney' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='TableMoney',
                parent=self.styles['Normal'],
                fontSize=10,
                fontName='Helvetica-Bold',
                alignment=TA_RIGHT,
                textColor=colors.HexColor('#38a169'),
                leading=12
            ))

        # Rodapé discreto
        if 'Footer' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Footer',
                parent=self.styles['Normal'],
                fontSize=8,
                fontName='Helvetica',
                alignment=TA_RIGHT,
                textColor=colors.HexColor('#718096'),
                leading=10
            ))

    def get_score_color(self, classe):
        """Retorna cor baseada na classe do score com gradientes"""
        colors_map = {
            'A': colors.HexColor('#38a169'),  # Verde
            'B': colors.HexColor('#3182ce'),  # Azul
            'C': colors.HexColor('#d69e2e'),  # Amarelo
            'D': colors.HexColor('#e53e3e'),  # Vermelho
            'E': colors.HexColor('#805ad5')   # Roxo
        }
        return colors_map.get(classe, colors.HexColor('#4a5568'))

    def create_score_gauge(self, score_value, max_score=1000):
        """Cria um gráfico de gauge moderno para o score"""
        drawing = Drawing(400, 180)
        
        # Calcular porcentagem
        percentage = min(score_value / max_score, 1.0)
        
        # Cores baseadas no score com gradiente azul
        if percentage >= 0.8:
            primary_color = colors.HexColor('#10B981')  # Verde esmeralda (ALTO = BOM)
            secondary_color = colors.HexColor('#059669')
        elif percentage >= 0.6:
            primary_color = colors.HexColor('#3B82F6')  # Azul moderno (MÉDIO-ALTO)
            secondary_color = colors.HexColor('#2563EB')
        elif percentage >= 0.4:
            primary_color = colors.HexColor('#F59E0B')  # Âmbar (MÉDIO)
            secondary_color = colors.HexColor('#D97706')
        elif percentage >= 0.2:
            primary_color = colors.HexColor('#F97316')  # Laranja (MÉDIO-BAIXO)
            secondary_color = colors.HexColor('#EA580C')
        else:
            primary_color = colors.HexColor('#EF4444')  # Vermelho (BAIXO = RUIM)
            secondary_color = colors.HexColor('#DC2626')
        
        # Círculo de fundo maior
        drawing.add(Circle(200, 90, 80, fillColor=colors.white, strokeColor=colors.HexColor('#E2E8F0'), strokeWidth=3))
        
        # Círculo interno com gradiente
        drawing.add(Circle(200, 90, 75, fillColor=primary_color, strokeColor=secondary_color, strokeWidth=2))
        
        # Efeito de gradiente (círculo interno mais claro)
        highlight_radius = 65
        drawing.add(Circle(200, 90, highlight_radius, fillColor=colors.HexColor('#FFFFFF'), strokeColor=colors.HexColor('#FFFFFF'), strokeWidth=0))
        
        # Valor do score em destaque no centro
        drawing.add(String(200, 90, f"{score_value} pontos", fontSize=18, fillColor=colors.HexColor('#64748B'), textAnchor='middle', fontName='Helvetica-Bold'))
        
        # Label "Score" abaixo
        drawing.add(String(200, 65, "Score", fontSize=14, fillColor=colors.white, textAnchor='middle', fontName='Helvetica-Bold'))
        
        return drawing

    def create_risk_chart(self, score_data):
        """Cria gráfico de risco ultra-moderno com design 3D e gradientes"""
        drawing = Drawing(450, 180)
        
        # Dados para o gráfico
        score_value = score_data.get('pontos', 0)
        max_score = 1000
        percentage = min(score_value / max_score, 1.0)
        
        # Cores modernas CORRIGIDAS (verde para alto, vermelho para baixo)
        if percentage >= 0.8:
            primary_color = colors.HexColor('#10B981')  # Verde esmeralda (ALTO = BOM)
            secondary_color = colors.HexColor('#059669')
        elif percentage >= 0.6:
            primary_color = colors.HexColor('#3B82F6')  # Azul moderno (MÉDIO-ALTO)
            secondary_color = colors.HexColor('#2563EB')
        elif percentage >= 0.4:
            primary_color = colors.HexColor('#F59E0B')  # Âmbar (MÉDIO)
            secondary_color = colors.HexColor('#D97706')
        elif percentage >= 0.2:
            primary_color = colors.HexColor('#F97316')  # Laranja (MÉDIO-BAIXO)
            secondary_color = colors.HexColor('#EA580C')
        else:
            primary_color = colors.HexColor('#EF4444')  # Vermelho (BAIXO = RUIM)
            secondary_color = colors.HexColor('#DC2626')
        
        # Grid moderno com linhas muito sutis
        for i in range(1, 6):
            y_pos = 30 + (i * 22)
            drawing.add(Line(25, y_pos, 475, y_pos, strokeColor=colors.HexColor('#F1F5F9'), strokeWidth=0.3))
        
        # Barra principal 3D com gradiente
        bar_width = 80
        bar_height = (score_value / max_score) * 110
        bar_x = 250 - (bar_width / 2)
        bar_y = 30 + (110 - bar_height)
        
        # Sombra da barra (mais sutil)
        bar_shadow_offset = 2
        drawing.add(Rect(bar_x + bar_shadow_offset, bar_y + bar_shadow_offset, bar_width, bar_height, 
                        fillColor=colors.HexColor('#E2E8F0'), strokeColor=colors.HexColor('#E2E8F0')))
        
        # Barra principal simples
        drawing.add(Rect(bar_x, bar_y, bar_width, bar_height, 
                        fillColor=primary_color, strokeColor=secondary_color, strokeWidth=1))
        
        # Efeito 3D - borda superior mais clara
        highlight_height = min(bar_height * 0.25, 6)
        drawing.add(Rect(bar_x, bar_y, bar_width, highlight_height, 
                        fillColor=colors.HexColor('#FFFFFF'), strokeColor=colors.HexColor('#FFFFFF'), strokeWidth=0))
        
        # Valor do score na barra
        if bar_height > 25:
            drawing.add(String(250, bar_y + (bar_height / 2), f"Score = {score_value}", 
                              fontSize=12, fillColor=colors.white, textAnchor='middle', fontName='Helvetica-Bold'))
        
        # Indicadores de faixa de risco
        risk_zones = [
            (0, 200, "BAIXO", colors.HexColor('#EF4444')),
            (200, 400, "MÉDIO-BAIXO", colors.HexColor('#F97316')),
            (400, 600, "MÉDIO", colors.HexColor('#F59E0B')),
            (600, 800, "MÉDIO-ALTO", colors.HexColor('#3B82F6')),
            (800, 1000, "ALTO", colors.HexColor('#10B981'))
        ]
        
        zone_width = 450 / 5
        
        for i, (min_val, max_val, label, color) in enumerate(risk_zones):
            zone_x = 25 + (i * zone_width)
            zone_height = 6
            zone_y = 25
            
            # Zona de risco
            drawing.add(Rect(zone_x, zone_y, zone_width, zone_height, 
                            fillColor=color, strokeColor=color))
            
            # Label da zona
            drawing.add(String(zone_x + (zone_width / 2), zone_y - 5, label, 
                              fontSize=8, fillColor=colors.HexColor('#4A5568'), textAnchor='middle', fontName='Helvetica-Bold'))
        
        return drawing

    def formatar_texto_longo(self, texto, max_chars=60):
        """Formata texto longo para caber em tabelas"""
        if not texto or len(texto) <= max_chars:
            return texto
        
        # Dividir em palavras e criar quebras naturais
        palavras = texto.split()
        linhas = []
        linha_atual = ""
        for palavra in palavras:
            if len(linha_atual + " " + palavra) <= max_chars:
                linha_atual += " " + palavra if linha_atual else palavra
            else:
                if linha_atual:
                    linhas.append(linha_atual)
                linha_atual = palavra
        if linha_atual:
            linhas.append(linha_atual)
        return "<br/>".join(linhas)

    def gerar_relatorio(self, cliente, dados_consulta, output_path=None):
        """Gera PDF profissional moderno com margens generosas e encoding UTF-8"""
        try:
            # Definir caminho de saída
            if not output_path:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"relatorio_{cliente['documento'].replace('.', '').replace('-', '').replace('/', '')}_{timestamp}.pdf"
                output_path = os.path.join('relatorios', filename)

            # Criar diretório se não existir
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Criar documento PDF com margens generosas
            doc = SimpleDocTemplate(
                output_path, 
                pagesize=A4,
                leftMargin=1*inch,
                rightMargin=1*inch,
                topMargin=0.8*inch,
                bottomMargin=0.8*inch
            )
            story = []

            # Gerar conteúdo profissional
            story.extend(self.gerar_cabecalho_pro(cliente))
            story.extend(self.gerar_dashboard_executivo(dados_consulta))
            story.extend(self.gerar_analise_score(dados_consulta))
            story.extend(self.gerar_indicadores_financeiros(dados_consulta))
            story.extend(self.gerar_analise_risco(dados_consulta))
            story.extend(self.gerar_rodape_pro(dados_consulta))

            # Construir PDF
            doc.build(story)
            print(f"✅ PDF Profissional gerado com sucesso: {output_path}")
            return output_path

        except Exception as e:
            print(f"❌ Erro ao gerar PDF Profissional: {e}")
            raise

    def gerar_cabecalho_pro(self, cliente):
        """Gera cabeçalho profissional moderno com título centralizado e linha separadora"""
        elements = []

        # Título principal centralizado com fonte moderna
        elements.append(Paragraph('ASSERTIVA SOLUÇÕES', self.styles['ModernTitle']))
        elements.append(Paragraph('Relatório de Análise de Crédito', self.styles['ModernSubtitle']))
        elements.append(Paragraph('Score de Crédito Restritivo', self.styles['ModernSubtitle']))
        
        # Linha horizontal sutil para separar
        elements.append(Paragraph('<hr width="80%" color="#e2e8f0" thickness="1"/>', self.styles['Normal']))
        elements.append(Spacer(1, 20))

        # Dados do cliente com tabela moderna
        elements.append(Paragraph('DADOS DO CLIENTE', self.styles['ModernSection']))

        client_data = [
            ['Nome:', cliente['nome']],
            ['CPF:', cliente['documento']],
            ['Telefone:', cliente['telefone']],
            ['E-mail:', cliente['email']]
        ]
        
        client_table = Table(client_data, colWidths=[2.2*inch, 3.8*inch])
        client_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4a5568')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2d3748')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
        ]))
        
        elements.append(client_table)
        elements.append(Spacer(1, 20))

        return elements

    def gerar_dashboard_executivo(self, dados_consulta):
        """Gera dashboard executivo moderno com tabelas legíveis e efeito zebra"""
        elements = []

        score = dados_consulta.get('resposta', {}).get('score')
        if score:
            # Card principal do score com design moderno
            score_value = score.get('pontos', 0)
            score_class = score.get('classe', 'N/A')
            score_color = self.get_score_color(score_class)
            
            # Dados do score em tabela moderna com quebras de linha
            descricao = self.formatar_texto_longo(score.get('faixa', {}).get('descricao', 'N/A'))
            
            score_data = [
                ['SCORE DE CRÉDITO'],
                ['Pontuação:', f"{score_value} pontos"],
                ['Classe:', f"{score_class}"],
                ['Faixa de Risco:', score.get('faixa', {}).get('titulo', 'N/A')],
                ['Descrição:', Paragraph(descricao, self.styles['Normal'])]
            ]

            score_table = Table(score_data, colWidths=[2.2*inch, 3.8*inch])
            score_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('SPAN', (0, 0), (1, 0)),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#2d3748')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
            ]))

            elements.append(score_table)
            elements.append(Spacer(1, 20))

            # Gráfico de score
            try:
                gauge = self.create_score_gauge(score_value)
                elements.append(gauge)
                elements.append(Spacer(1, 15))
            except Exception as e:
                print(f"Aviso: Não foi possível gerar gráfico: {e}")

        return elements

    def gerar_analise_score(self, dados_consulta):
        """Gera análise detalhada do score"""
        elements = []

        score = dados_consulta.get('resposta', {}).get('score')
        if score:
            # Detalhes técnicos em tabela moderna com quebras de linha
            descricao = self.formatar_texto_longo(score.get('faixa', {}).get('descricao', 'N/A'))
            
            details_data = [
                ['Pontuação Atual:', f"{score.get('pontos', 'N/A')} pontos"],
                ['Classe de Risco:', f"{score.get('classe', 'N/A')}"],
                ['Faixa:', score.get('faixa', {}).get('titulo', 'N/A')],
                ['Descrição:', Paragraph(descricao, self.styles['Normal'])]
            ]

            details_table = Table(details_data, colWidths=[2.2*inch, 3.8*inch])
            details_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#2d3748')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
            ]))

            elements.append(details_table)
            elements.append(Spacer(1, 20))

            # Gráfico de análise centralizado
            try:
                elements.append(Spacer(1, 15))
                chart = self.create_risk_chart(score)
                elements.append(chart)
                elements.append(Spacer(1, 20))
            except Exception as e:
                print(f"Aviso: Não foi possível gerar gráfico de análise: {e}")

        return elements

    def gerar_indicadores_financeiros(self, dados_consulta):
        """Gera indicadores financeiros com design moderno e valores monetários alinhados"""
        elements = []

        renda = dados_consulta.get('resposta', {}).get('rendaPresumida')
        if renda and renda.get('valor'):
            # Card de renda com design moderno
            renda_value = f"R$ {renda['valor']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            renda_data = [
                ['RENDA PRESUMIDA'],
                ['Valor Estimado:', renda_value]
            ]

            renda_table = Table(renda_data, colWidths=[2.2*inch, 3.8*inch])
            renda_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#38a169')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('SPAN', (0, 0), (1, 0)),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#38a169')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
            ]))

            elements.append(renda_table)
            elements.append(Spacer(1, 20))

        return elements

    def gerar_analise_risco(self, dados_consulta):
        """Gera análise de risco com protestos públicos"""
        elements = []

        protestos = dados_consulta.get('resposta', {}).get('protestosPublicos')
        if protestos:
            qtd_protestos = protestos.get('qtdProtestos', 0)
            
            # Determinar nível de risco
            if qtd_protestos == 0:
                risk_level = "BAIXO"
                risk_color = colors.HexColor('#38a169')
                risk_status = "Sem pendências"
            elif qtd_protestos <= 2:
                risk_level = "MÉDIO"
                risk_color = colors.HexColor('#d69e2e')
                risk_status = "Pendências encontradas"
            else:
                risk_level = "ALTO"
                risk_color = colors.HexColor('#e53e3e')
                risk_status = "Múltiplas pendências"

            risk_data = [
                ['PROTESTOS PÚBLICOS'],
                ['Quantidade:', f"{qtd_protestos} protestos"],
                ['Nível de Risco:', risk_level],
                ['Status:', risk_status]
            ]

            if qtd_protestos > 0:
                risk_data.extend([
                    ['Primeira Ocorrência:', protestos.get('primeiraOcorrencia', 'N/A')],
                    ['Última Ocorrência:', protestos.get('ultimaOcorrencia', 'N/A')]
                ])

            risk_table = Table(risk_data, colWidths=[2.2*inch, 3.8*inch])
            risk_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), risk_color),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('SPAN', (0, 0), (1, 0)),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TEXTCOLOR', (0, 1), (0, -1), colors.HexColor('#4a5568')),
                ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#2d3748')),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f7fafc')]),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 10),
            ]))

            elements.append(risk_table)
            elements.append(Spacer(1, 20))

        return elements

    def gerar_rodape_pro(self, dados_consulta):
        """Gera rodapé profissional moderno com data/hora de geração"""
        elements = []
        
        # Linha separadora elegante
        elements.append(Paragraph('<hr width="100%" color="#e2e8f0" thickness="1"/>', self.styles['Normal']))
        elements.append(Spacer(1, 15))

        # Copyright profissional
        elements.append(Paragraph('© 2025 | Relatório gerado automaticamente', self.styles['Footer']))

        return elements

# ============================================================================
# FUNÇÕES PRINCIPAIS
# ============================================================================

def limpar_tela():
    """Limpa a tela do terminal"""
    os.system('cls' if os.name == 'nt' else 'clear')

def exibir_cabecalho():
    """Exibe o cabeçalho do programa"""
    print(f"{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}{'🏢 SISTEMA DE CONSULTA ASSERTIVA - PYTHON':^60}")
    print(f"{Fore.CYAN}{'='*60}")
    print()

def validar_cpf(cpf):
    """Valida formato básico do CPF"""
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    return len(cpf_limpo) == 11

def validar_email(email):
    """Valida formato básico do email"""
    return '@' in email and '.' in email

def validar_telefone(telefone):
    """Valida formato básico do telefone"""
    telefone_limpo = ''.join(filter(str.isdigit, telefone))
    return len(telefone_limpo) >= 10

def obter_dados_cliente():
    """Obtém dados do cliente via terminal"""
    print(f"{Fore.YELLOW}📋 INFORMAÇÕES DO CLIENTE")
    print(f"{Fore.YELLOW}{'-'*40}")
    print()

    # Nome
    while True:
        nome = input(f"{Fore.WHITE}Nome completo do cliente: {Fore.GREEN}").strip()
        if len(nome) >= 3:
            break
        print(f"{Fore.RED}❌ Nome deve ter pelo menos 3 caracteres!")

    # CPF
    while True:
        cpf = input(f"{Fore.WHITE}CPF (apenas números): {Fore.GREEN}").strip()
        if validar_cpf(cpf):
            # Formatar CPF para exibição
            cpf_limpo = ''.join(filter(str.isdigit, cpf))
            cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
            break
        print(f"{Fore.RED}❌ CPF inválido! Digite apenas os números.")

    # Telefone
    while True:
        telefone = input(f"{Fore.WHITE}Telefone: {Fore.GREEN}").strip()
        if validar_telefone(telefone):
            break
        print(f"{Fore.RED}❌ Telefone inválido!")

    # Email
    while True:
        email = input(f"{Fore.WHITE}E-mail: {Fore.GREEN}").strip()
        if validar_email(email):
            break
        print(f"{Fore.RED}❌ E-mail inválido!")

    return {
        'nome': nome,
        'documento': cpf_formatado,
        'documento_limpo': cpf_limpo,
        'tipo': 'CPF',
        'telefone': telefone,
        'email': email
    }

def confirmar_dados(cliente):
    """Confirma os dados do cliente"""
    print(f"\n{Fore.CYAN}📋 DADOS CONFIRMADOS:")
    print(f"{Fore.CYAN}{'-'*40}")
    print(f"{Fore.WHITE}Nome: {Fore.GREEN}{cliente['nome']}")
    print(f"{Fore.WHITE}CPF: {Fore.GREEN}{cliente['documento']}")
    print(f"{Fore.WHITE}Telefone: {Fore.GREEN}{cliente['telefone']}")
    print(f"{Fore.WHITE}E-mail: {Fore.GREEN}{cliente['email']}")
    print()

    while True:
        confirmacao = input(f"{Fore.YELLOW}Os dados estão corretos? (s/n): {Fore.GREEN}").lower().strip()
        if confirmacao in ['s', 'sim', 'y', 'yes']:
            return True
        elif confirmacao in ['n', 'não', 'nao', 'no']:
            return False
        else:
            print(f"{Fore.RED}❌ Digite 's' para sim ou 'n' para não!")

def executar_consulta(cliente):
    """Executa a consulta na API Assertiva"""
    print(f"\n{Fore.BLUE}�� INICIANDO CONSULTA...")
    print(f"{Fore.BLUE}{'-'*40}")
    print()

    try:
        # Criar cliente Assertiva
        client = AssertivaClient()
        
        # Fazer consulta de CPF
        resultado = client.consultar_score_credito(
            cliente['documento_limpo'], 
            '2', 
            'ACOES,POSITIVO'
        )
        
        # Exibir resultados
        client.exibir_resultados(cliente['documento_limpo'], resultado)
        
        return resultado
        
    except Exception as e:
        print(f"{Fore.RED}❌ Erro na consulta: {e}")
        return None

def gerar_pdf(cliente, dados_consulta):
    """Gera o PDF do relatório profissional"""
    print(f"\n{Fore.MAGENTA}📄 GERANDO PDF PROFISSIONAL...")
    print(f"{Fore.MAGENTA}{'-'*40}")
    print()

    try:
        # Criar gerador de PDF profissional
        pdf_gen = PDFGeneratorPro()
        print(f"{Fore.CYAN}🎨 Gerando PDF com gráficos, badges e design avançado...")
        
        # Gerar PDF
        pdf_path = pdf_gen.gerar_relatorio(cliente, dados_consulta)
        
        print(f"{Fore.GREEN}✅ PDF Profissional gerado com sucesso!")
        print(f"{Fore.GREEN}�� Arquivo: {pdf_path}")
        
        return pdf_path
        
    except Exception as e:
        print(f"{Fore.RED}❌ Erro ao gerar PDF: {e}")
        return None

def executar_nova_consulta():
    """Executa uma nova consulta completa"""
    try:
        # Obter dados do cliente
        cliente = obter_dados_cliente()
        
        # Confirmar dados
        if not confirmar_dados(cliente):
            print(f"{Fore.YELLOW}🔄 Reiniciando...")
            input(f"{Fore.YELLOW}Pressione Enter para continuar...")
            return
        
        # Executar consulta
        resultado = executar_consulta(cliente)
        if not resultado:
            print(f"{Fore.RED}❌ Falha na consulta!")
            input(f"{Fore.YELLOW}Pressione Enter para continuar...")
            return
        
        # Gerar PDF automaticamente
        pdf_path = gerar_pdf(cliente, resultado)
        if pdf_path:
            print(f"\n{Fore.GREEN}🎉 Consulta e PDF Profissional concluídos com sucesso!")
        else:
            print(f"\n{Fore.YELLOW}⚠️ Consulta concluída, mas falha na geração do PDF.")
        
        input(f"\n{Fore.YELLOW}Pressione Enter para continuar...")
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}�� Operação cancelada pelo usuário.")
        input(f"{Fore.YELLOW}Pressione Enter para continuar...")
    except Exception as e:
        print(f"\n{Fore.RED}❌ Erro inesperado: {e}")
        input(f"{Fore.YELLOW}Pressione Enter para continuar...")

def main():
    """Função principal"""
    try:
        # Verificar se o arquivo .env existe
        if not os.path.exists('.env'):
            print(f"{Fore.RED}❌ Arquivo .env não encontrado!")
            print(f"{Fore.YELLOW}📝 Crie o arquivo .env com suas credenciais da API Assertiva.")
            return
        
        # Executar consulta completa automaticamente
        executar_nova_consulta()
        
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}👋 Programa encerrado pelo usuário.")
    except Exception as e:
        print(f"\n{Fore.RED}❌ Erro fatal: {e}")

if __name__ == "__main__":
    main()