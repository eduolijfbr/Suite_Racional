# -*- coding: utf-8 -*-
"""
Gerenciamento de Curvas IDF (Intensidade-Duração-Frequência)
"""

import json
import os


class CurvasIDF:
    """Gerenciamento de curvas IDF locais"""
    
    def __init__(self):
        # Banco de curvas IDF pré-carregadas para cidades brasileiras
        self.curvas_brasil = {
            'juiz_de_fora': {
                'K': 1450,
                'a': 0.15,
                'b': 20,
                'c': 0.90,
                'fonte': 'COPASA-MG, 2018',
                'municipio': 'Juiz de Fora',
                'estado': 'MG'
            },
            "juiz_de_fora - Norte Eq.11": {
                "K": 2314.482,
                "a": 0.149,
                "b": 22.129,
                "c": 0.903,
                "fonte": "GEASA, 2025",
                "municipio": "Juiz de Fora",
                "estado": "MG"
            },
            "juiz_de_fora - Sul Eq.10": {
                "K": 1646.3,
                "a": 0.171,
                "b": 15.496,
                "c": 0.822,
                "fonte": "GEASA, 2025",
                "municipio": "Juiz de Fora",
                "estado": "MG"
            },
            'belo_horizonte': {
                'K': 1447,
                'a': 0.12,
                'b': 15,
                'c': 0.85,
                'fonte': 'COPASA-MG',
                'municipio': 'Belo Horizonte',
                'estado': 'MG'
            },
            'sao_paulo': {
                'K': 1540,
                'a': 0.14,
                'b': 16,
                'c': 0.88,
                'fonte': 'DAEE-SP',
                'municipio': 'São Paulo',
                'estado': 'SP'
            },
            'rio_de_janeiro': {
                'K': 1239,
                'a': 0.15,
                'b': 20,
                'c': 0.74,
                'fonte': 'Rio-Águas',
                'municipio': 'Rio de Janeiro',
                'estado': 'RJ'
            },
            'curitiba': {
                'K': 1360,
                'a': 0.16,
                'b': 18,
                'c': 0.82,
                'fonte': 'SUDERHSA-PR',
                'municipio': 'Curitiba',
                'estado': 'PR'
            },
            'porto_alegre': {
                'K': 1297,
                'a': 0.14,
                'b': 12,
                'c': 0.80,
                'fonte': 'DMAE-RS',
                'municipio': 'Porto Alegre',
                'estado': 'RS'
            },
            'brasilia': {
                'K': 1519,
                'a': 0.16,
                'b': 16,
                'c': 0.86,
                'fonte': 'CAESB-DF',
                'municipio': 'Brasília',
                'estado': 'DF'
            },
            'salvador': {
                'K': 1420,
                'a': 0.12,
                'b': 10,
                'c': 0.78,
                'fonte': 'EMBASA-BA',
                'municipio': 'Salvador',
                'estado': 'BA'
            },
            'fortaleza': {
                'K': 1380,
                'a': 0.13,
                'b': 14,
                'c': 0.76,
                'fonte': 'CAGECE-CE',
                'municipio': 'Fortaleza',
                'estado': 'CE'
            },
            'recife': {
                'K': 1500,
                'a': 0.14,
                'b': 12,
                'c': 0.82,
                'fonte': 'COMPESA-PE',
                'municipio': 'Recife',
                'estado': 'PE'
            },
            'manaus': {
                'K': 1650,
                'a': 0.13,
                'b': 15,
                'c': 0.80,
                'fonte': 'INPA',
                'municipio': 'Manaus',
                'estado': 'AM'
            },
            'belem': {
                'K': 1580,
                'a': 0.12,
                'b': 14,
                'c': 0.78,
                'fonte': 'COSANPA-PA',
                'municipio': 'Belém',
                'estado': 'PA'
            },
            'goiania': {
                'K': 1480,
                'a': 0.15,
                'b': 17,
                'c': 0.84,
                'fonte': 'SANEAGO-GO',
                'municipio': 'Goiânia',
                'estado': 'GO'
            },
            'campinas': {
                'K': 1520,
                'a': 0.14,
                'b': 15,
                'c': 0.86,
                'fonte': 'SANASA-SP',
                'municipio': 'Campinas',
                'estado': 'SP'
            },
            'vitoria': {
                'K': 1350,
                'a': 0.13,
                'b': 16,
                'c': 0.79,
                'fonte': 'CESAN-ES',
                'municipio': 'Vitória',
                'estado': 'ES'
            }
        }
        
        # Curvas personalizadas
        self.curvas_personalizadas = {}
        
    def _normalizar_chave(self, nome):
        """Normaliza nome de cidade para comparação"""
        return nome.lower().replace(' ', '_').replace('-', '_').replace('__', '_')
    
    def calcular_intensidade(self, cidade, TR, duracao):
        """
        Calcula intensidade para cidade e parâmetros específicos.
        
        Parâmetros:
            cidade: Nome da cidade (chave do dicionário)
            TR: Tempo de retorno (anos)
            duracao: Duração da chuva (minutos)
            
        Retorna:
            float: Intensidade em mm/h
        """
        params = self.obter_parametros(cidade)
        if not params:
            raise ValueError(f"Curva IDF não encontrada para: {cidade}")
            
        # Calcular intensidade: I = (K * TR^a) / (t + b)^c
        K = params['K']
        a = params['a']
        b = params['b']
        c = params['c']
        
        I = (K * (TR ** a)) / ((duracao + b) ** c)
        
        return I
    
    def adicionar_curva_personalizada(self, nome, parametros):
        """
        Permite adicionar curvas IDF customizadas.
        
        Parâmetros:
            nome: Nome identificador da curva
            parametros: dict com K, a, b, c e opcionalmente fonte, municipio, estado
        """
        campos_obrigatorios = ['K', 'a', 'b', 'c']
        for campo in campos_obrigatorios:
            if campo not in parametros:
                raise ValueError(f"Parâmetro obrigatório ausente: {campo}")
                
        nome_key = nome.lower().replace(' ', '_').replace('-', '_')
        self.curvas_personalizadas[nome_key] = parametros
        
    def remover_curva_personalizada(self, nome):
        """Remove curva personalizada"""
        nome_key = nome.lower().replace(' ', '_').replace('-', '_')
        if nome_key in self.curvas_personalizadas:
            del self.curvas_personalizadas[nome_key]
            
    def listar_cidades(self):
        """Lista todas as cidades disponíveis"""
        cidades = []
        
        for key, params in self.curvas_brasil.items():
            cidades.append({
                'chave': key,
                'municipio': params.get('municipio', key),
                'estado': params.get('estado', ''),
                'fonte': params.get('fonte', '')
            })
            
        for key, params in self.curvas_personalizadas.items():
            cidades.append({
                'chave': key,
                'municipio': params.get('municipio', key),
                'estado': params.get('estado', ''),
                'fonte': params.get('fonte', 'Personalizada')
            })
            
        return cidades
    
    def obter_parametros(self, cidade):
        """Retorna parâmetros da curva IDF de uma cidade.
        Faz busca normalizada para aceitar variações de formatação."""
        cidade_norm = self._normalizar_chave(cidade)
        
        # Busca normalizada em curvas_brasil
        for key, params in self.curvas_brasil.items():
            if self._normalizar_chave(key) == cidade_norm:
                return params
        
        # Busca normalizada em curvas_personalizadas
        for key, params in self.curvas_personalizadas.items():
            if self._normalizar_chave(key) == cidade_norm:
                return params
        
        return None
    
    def gerar_tabela_intensidades(self, cidade, TRs=None, duracoes=None):
        """
        Gera tabela de intensidades para múltiplos TRs e durações.
        
        Parâmetros:
            cidade: Nome da cidade
            TRs: Lista de tempos de retorno (default: [2, 5, 10, 25, 50, 100])
            duracoes: Lista de durações em minutos (default: [5, 10, 15, 30, 60, 120])
            
        Retorna:
            dict: Tabela de intensidades
        """
        if TRs is None:
            TRs = [2, 5, 10, 25, 50, 100]
        if duracoes is None:
            duracoes = [5, 10, 15, 30, 60, 120]
            
        tabela = {
            'TRs': TRs,
            'duracoes': duracoes,
            'intensidades': {}
        }
        
        for tr in TRs:
            tabela['intensidades'][tr] = {}
            for d in duracoes:
                tabela['intensidades'][tr][d] = self.calcular_intensidade(cidade, tr, d)
                
        return tabela
    
    def exportar_curvas(self, caminho):
        """Exporta curvas para arquivo JSON"""
        dados = {
            'curvas_brasil': self.curvas_brasil,
            'curvas_personalizadas': self.curvas_personalizadas
        }
        
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
            
    def importar_curvas(self, caminho):
        """Importa curvas de arquivo JSON"""
        with open(caminho, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            
        if 'curvas_personalizadas' in dados:
            self.curvas_personalizadas.update(dados['curvas_personalizadas'])
