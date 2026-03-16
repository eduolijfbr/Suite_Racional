# -*- coding: utf-8 -*-
"""
Gerenciador de Banco de Dados para o Plugin
"""

import sqlite3
import json
import os
from datetime import datetime


class GerenciadorBancoDados:
    """Gerencia conexões e operações de banco de dados"""
    
    def __init__(self, tipo='sqlite', **kwargs):
        """
        Inicializa gerenciador de banco de dados.
        
        Parâmetros:
            tipo: 'sqlite' ou 'postgresql'
            **kwargs: Parâmetros de conexão
        """
        self.tipo = tipo
        self.conexao = None
        
        if tipo == 'sqlite':
            arquivo = kwargs.get('arquivo', 'drenagem.db')
            self.conexao = self._conectar_sqlite(arquivo)
        elif tipo == 'postgresql':
            self.conexao = self._conectar_postgresql(**kwargs)
            
    def _conectar_sqlite(self, arquivo):
        """Conecta ao banco SQLite"""
        conexao = sqlite3.connect(arquivo)
        conexao.row_factory = sqlite3.Row
        return conexao
    
    def _conectar_postgresql(self, **kwargs):
        """Conecta ao PostgreSQL"""
        try:
            import psycopg2
            
            conexao = psycopg2.connect(
                host=kwargs.get('host', 'localhost'),
                port=kwargs.get('porta', 5432),
                database=kwargs.get('banco'),
                user=kwargs.get('usuario'),
                password=kwargs.get('senha')
            )
            return conexao
            
        except ImportError:
            raise Exception("psycopg2 não instalado. Execute: pip install psycopg2-binary")
        except Exception as e:
            raise Exception(f"Erro ao conectar PostgreSQL: {str(e)}")
    
    def criar_tabelas(self):
        """Cria estrutura de tabelas do banco"""
        cursor = self.conexao.cursor()
        
        # Tabela de Projetos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projetos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                municipio TEXT,
                estado TEXT,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_modificacao TIMESTAMP,
                usuario TEXT,
                sistema_coordenadas TEXT,
                extensao_geom TEXT
            )
        ''')
        
        # Tabela de Bacias
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bacias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                projeto_id INTEGER,
                nome TEXT NOT NULL,
                area_km2 REAL,
                perimetro_km REAL,
                comprimento_talvegue_m REAL,
                desnivel_m REAL,
                declividade_perc REAL,
                altitude_max_m REAL,
                altitude_min_m REAL,
                altitude_med_m REAL,
                cn_ponderado REAL,
                tempo_concentracao_min REAL,
                metodo_tc TEXT,
                geometria BLOB,
                FOREIGN KEY (projeto_id) REFERENCES projetos(id)
            )
        ''')
        
        # Tabela de Cálculos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS calculos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bacia_id INTEGER,
                data_calculo TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metodo TEXT DEFAULT 'Racional',
                
                area_km2 REAL,
                coef_escoamento REAL,
                intensidade_mmh REAL,
                tempo_retorno_anos INTEGER,
                duracao_min REAL,
                rugosidade REAL,
                declividade_perc REAL,
                
                vazao_m3s REAL,
                diametro_m REAL,
                velocidade_ms REAL,
                numero_froude REAL,
                lamina_sobre_diametro REAL,
                
                status_velocidade TEXT,
                status_froude TEXT,
                status_geral TEXT,
                observacoes TEXT,
                
                FOREIGN KEY (bacia_id) REFERENCES bacias(id)
            )
        ''')
        
        # Tabela de Parâmetros IDF
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parametros_idf (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                municipio TEXT NOT NULL,
                estado TEXT,
                K REAL,
                a REAL,
                b REAL,
                c REAL,
                fonte TEXT,
                ano INTEGER,
                UNIQUE(municipio, estado)
            )
        ''')
        
        # Tabela de Uso do Solo / CN
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS uso_solo_cn (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo_uso TEXT NOT NULL,
                descricao TEXT,
                cn_a INTEGER,
                cn_b INTEGER,
                cn_c INTEGER,
                cn_d INTEGER,
                fonte TEXT
            )
        ''')
        
        # Tabela de Materiais / Rugosidade
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS materiais_rugosidade (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                material TEXT NOT NULL,
                tipo TEXT,
                rugosidade_min REAL,
                rugosidade_max REAL,
                rugosidade_tipica REAL,
                observacoes TEXT
            )
        ''')
        
        # Tabela de Relatórios Gerados
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS relatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calculo_id INTEGER,
                data_geracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tipo TEXT,
                formato TEXT,
                caminho_arquivo TEXT,
                FOREIGN KEY (calculo_id) REFERENCES calculos(id)
            )
        ''')
        
        self.conexao.commit()
        
        # Inserir dados padrão
        self._inserir_dados_padrao(cursor)
        
    def _inserir_dados_padrao(self, cursor):
        """Insere dados padrão nas tabelas"""
        
        # Materiais e rugosidade
        materiais = [
            ('PEAD', 'tubulação', 0.009, 0.012, 0.010, 'Polietileno de Alta Densidade'),
            ('Concreto', 'tubulação', 0.012, 0.015, 0.013, 'Tubos de concreto'),
            ('Concreto Pré-moldado', 'galeria', 0.013, 0.017, 0.015, 'Galerias celulares'),
            ('PVC', 'tubulação', 0.009, 0.011, 0.010, 'Policloreto de vinila'),
            ('Ferro Fundido', 'tubulação', 0.012, 0.015, 0.013, 'Tubos de ferro fundido'),
            ('Aço', 'tubulação', 0.010, 0.014, 0.012, 'Tubos de aço'),
            ('Concreto Liso', 'canal', 0.012, 0.014, 0.013, 'Canal revestido'),
            ('Pedra Argamassada', 'canal', 0.017, 0.025, 0.020, 'Canal em pedra'),
            ('Gabião', 'canal', 0.025, 0.035, 0.030, 'Canal em gabião'),
            ('Terra Natural', 'canal', 0.025, 0.040, 0.030, 'Canal em terra'),
        ]
        
        for mat in materiais:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO materiais_rugosidade 
                    (material, tipo, rugosidade_min, rugosidade_max, rugosidade_tipica, observacoes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', mat)
            except Exception:
                pass
                
        # Uso do solo e CN
        usos = [
            ('Área Urbana Impermeável', 'Telhados, pavimentos, etc.', 98, 98, 98, 98),
            ('Área Urbana Permeável', 'Jardins, gramados urbanos', 77, 85, 90, 92),
            ('Floresta Densa', 'Mata nativa preservada', 30, 55, 70, 77),
            ('Floresta Rala', 'Vegetação secundária', 45, 66, 77, 83),
            ('Pastagem', 'Pasto em boas condições', 39, 61, 74, 80),
            ('Agricultura', 'Culturas anuais', 67, 78, 85, 89),
            ('Solo Exposto', 'Área sem cobertura vegetal', 77, 86, 91, 94),
            ('Corpos d\'água', 'Rios, lagos, represas', 100, 100, 100, 100),
        ]
        
        for uso in usos:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO uso_solo_cn 
                    (tipo_uso, descricao, cn_a, cn_b, cn_c, cn_d)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', uso)
            except Exception:
                pass
                
        self.conexao.commit()
        
    def salvar_projeto(self, dados_projeto):
        """Salva novo projeto ou atualiza existente"""
        cursor = self.conexao.cursor()
        
        if 'id' in dados_projeto and dados_projeto['id']:
            # Atualizar
            cursor.execute('''
                UPDATE projetos SET
                    nome = ?,
                    descricao = ?,
                    municipio = ?,
                    estado = ?,
                    data_modificacao = ?,
                    usuario = ?,
                    sistema_coordenadas = ?
                WHERE id = ?
            ''', (
                dados_projeto['nome'],
                dados_projeto.get('descricao'),
                dados_projeto.get('municipio'),
                dados_projeto.get('estado'),
                datetime.now(),
                dados_projeto.get('usuario'),
                dados_projeto.get('sistema_coordenadas'),
                dados_projeto['id']
            ))
        else:
            # Inserir
            cursor.execute('''
                INSERT INTO projetos 
                (nome, descricao, municipio, estado, usuario, sistema_coordenadas)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                dados_projeto['nome'],
                dados_projeto.get('descricao'),
                dados_projeto.get('municipio'),
                dados_projeto.get('estado'),
                dados_projeto.get('usuario'),
                dados_projeto.get('sistema_coordenadas')
            ))
            dados_projeto['id'] = cursor.lastrowid
            
        self.conexao.commit()
        return dados_projeto['id']
        
    def salvar_calculo(self, dados_calculo, bacia_id=None):
        """Salva resultado de cálculo"""
        cursor = self.conexao.cursor()
        
        dados_entrada = dados_calculo.get('dados_entrada', {})
        
        # Filtrar dados para serialização JSON (remover numpy arrays e outros não-serializáveis)
        dados_para_json = self._filtrar_dados_serializaveis(dados_calculo)
        
        cursor.execute('''
            INSERT INTO calculos (
                bacia_id, metodo,
                area_km2, coef_escoamento, intensidade_mmh,
                tempo_retorno_anos, duracao_min, rugosidade, declividade_perc,
                vazao_m3s, diametro_m, velocidade_ms,
                numero_froude, lamina_sobre_diametro,
                status_geral, observacoes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            bacia_id,
            'Racional',
            dados_entrada.get('area'),
            dados_entrada.get('coef_escoamento'),
            dados_entrada.get('intensidade'),
            dados_entrada.get('tempo_retorno'),
            dados_entrada.get('tempo'),
            dados_entrada.get('rugosidade'),
            dados_entrada.get('declividade'),
            dados_calculo.get('vazao'),
            dados_calculo.get('diametro'),
            dados_calculo.get('velocidade'),
            dados_calculo.get('froude'),
            dados_calculo.get('lamina'),
            dados_calculo.get('status'),
            json.dumps(dados_para_json)
        ))
        
        self.conexao.commit()
        return cursor.lastrowid
    
    def _filtrar_dados_serializaveis(self, dados, profundidade=0):
        """
        Filtra dados para remover objetos não serializáveis em JSON.
        Remove numpy arrays, objetos QGIS, e outros tipos complexos.
        """
        if profundidade > 10:  # Evitar recursão infinita
            return None
            
        # Tipos que não são serializáveis em JSON
        try:
            import numpy as np
            tipos_numpy = (np.ndarray, np.generic)
        except ImportError:
            tipos_numpy = ()
        
        if dados is None:
            return None
        elif isinstance(dados, (str, int, float, bool)):
            return dados
        elif isinstance(dados, tipos_numpy):
            # Ignorar arrays numpy (são muito grandes e não necessários no JSON)
            return None
        elif isinstance(dados, dict):
            resultado = {}
            # Chaves que devem ser excluídas (contêm dados binários/arrays)
            chaves_excluir = {
                'impermeabilidade_dados', 'rgb_image', 'classification_map', 
                'valid_mask', 'exg', 'saturacao', 'intensidade'
            }
            for k, v in dados.items():
                if k in chaves_excluir:
                    continue
                valor_filtrado = self._filtrar_dados_serializaveis(v, profundidade + 1)
                if valor_filtrado is not None:
                    resultado[k] = valor_filtrado
            return resultado
        elif isinstance(dados, (list, tuple)):
            resultado = []
            for item in dados:
                valor_filtrado = self._filtrar_dados_serializaveis(item, profundidade + 1)
                if valor_filtrado is not None:
                    resultado.append(valor_filtrado)
            return resultado
        else:
            # Tentar converter para string como último recurso
            try:
                json.dumps(dados)  # Testar se é serializável
                return dados
            except (TypeError, ValueError):
                return None
        
    def carregar_projeto(self, projeto_id):
        """Carrega dados completos de um projeto"""
        cursor = self.conexao.cursor()
        
        cursor.execute('SELECT * FROM projetos WHERE id = ?', (projeto_id,))
        projeto = dict(cursor.fetchone())
        
        cursor.execute('SELECT * FROM bacias WHERE projeto_id = ?', (projeto_id,))
        projeto['bacias'] = [dict(row) for row in cursor.fetchall()]
        
        for bacia in projeto['bacias']:
            cursor.execute('SELECT * FROM calculos WHERE bacia_id = ?', (bacia['id'],))
            bacia['calculos'] = [dict(row) for row in cursor.fetchall()]
            
        return projeto
        
    def listar_projetos(self, filtros=None):
        """Lista projetos com filtros opcionais"""
        cursor = self.conexao.cursor()
        
        query = 'SELECT * FROM projetos'
        params = []
        
        if filtros:
            conditions = []
            if 'municipio' in filtros:
                conditions.append('municipio = ?')
                params.append(filtros['municipio'])
            if 'estado' in filtros:
                conditions.append('estado = ?')
                params.append(filtros['estado'])
                
            if conditions:
                query += ' WHERE ' + ' AND '.join(conditions)
                
        query += ' ORDER BY data_criacao DESC'
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
        
    def listar_calculos(self, limite=100):
        """Lista últimos cálculos realizados"""
        cursor = self.conexao.cursor()
        
        cursor.execute('''
            SELECT * FROM calculos 
            ORDER BY data_calculo DESC 
            LIMIT ?
        ''', (limite,))
        
        return [dict(row) for row in cursor.fetchall()]
        
    def exportar_projeto(self, projeto_id, formato='json'):
        """Exporta projeto completo em formato especificado"""
        projeto = self.carregar_projeto(projeto_id)
        
        if formato == 'json':
            return json.dumps(projeto, indent=2, default=str)
        else:
            raise ValueError(f"Formato não suportado: {formato}")
            
    def importar_projeto(self, arquivo):
        """Importa projeto de arquivo"""
        with open(arquivo, 'r', encoding='utf-8') as f:
            dados = json.load(f)
            
        # Remover ID para criar novo
        if 'id' in dados:
            del dados['id']
            
        return self.salvar_projeto(dados)
        
    def fechar(self):
        """Fecha conexão com o banco"""
        if self.conexao:
            self.conexao.close()
            
    def __del__(self):
        """Destrutor - fecha conexão"""
        self.fechar()
