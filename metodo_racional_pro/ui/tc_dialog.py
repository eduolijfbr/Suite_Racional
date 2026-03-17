# -*- coding: utf-8 -*-
"""
Dialog para Cálculo do Tempo de Concentração (Tc)
Com suporte a múltiplos métodos e edição de parâmetros
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox,
    QDoubleSpinBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QDoubleValidator, QFont

import math

# Import dos métodos de cálculo
try:
    from ..hidrologia.metodo_racional import TempoConcentracao
except ImportError:
    TempoConcentracao = None


class TcDialog(QDialog):
    """Dialog para cálculo de Tempo de Concentração com múltiplos métodos"""
    
    # Definição dos métodos disponíveis
    METODOS = {
        'kirpich': {
            'nome': 'Kirpich',
            'descricao': 'Bacias pequenas/rurais',
            'formula': 'Tc = 57 × (L³/H)^0.385',
            'requer': ['distancia', 'desnivel']
        },
        'giandotti': {
            'nome': 'Giandotti',
            'descricao': 'Urbano e rural (recomendado Brasil)',
            'formula': 'Tc = (4√A + 1.5L) / (0.8√H)',
            'requer': ['distancia', 'desnivel', 'area']
        },
        'ventura': {
            'nome': 'Ventura',
            'descricao': 'Bacias urbanas',
            'formula': 'Tc = 0.127 × √(A/S)',
            'requer': ['area', 'declividade']
        },
        'bransby_williams': {
            'nome': 'Bransby-Williams',
            'descricao': 'Conservador / cenários críticos',
            'formula': 'Tc = 14.6 × L / (A^0.1 × S^0.2)',
            'requer': ['distancia', 'area', 'declividade']
        }
    }
    
    def __init__(self, parent=None, distancia=None, desnivel=None, area=None, declividade=None):
        super(TcDialog, self).__init__(parent)
        self.tempo_calculado = None
        self.metodo_usado = None
        
        # Valores iniciais
        self.distancia_inicial = distancia
        self.desnivel_inicial = desnivel
        self.area_inicial = area
        self.declividade_inicial = declividade
        
        self.setup_ui()
        self.carregar_valores_iniciais()
        
    def setup_ui(self):
        """Configura interface"""
        self.setWindowTitle("Calculadora de Tempo de Concentração (Tc)")
        self.setMinimumSize(550, 500)
        
        layout = QVBoxLayout(self)
        
        # Grupo de parâmetros de entrada
        grp_params = QGroupBox("Parâmetros de Entrada")
        grid_params = QGridLayout(grp_params)
        
        # Distância
        grid_params.addWidget(QLabel("Distância (m):"), 0, 0)
        self.txtDistancia = QLineEdit()
        self.txtDistancia.setValidator(QDoubleValidator(0, 999999, 2))
        self.txtDistancia.setToolTip("Comprimento do talvegue em metros")
        grid_params.addWidget(self.txtDistancia, 0, 1)
        
        # Desnível
        grid_params.addWidget(QLabel("Desnível (m):"), 1, 0)
        self.txtDesnivel = QLineEdit()
        self.txtDesnivel.setValidator(QDoubleValidator(0, 9999, 2))
        self.txtDesnivel.setToolTip("Diferença de altitude entre o ponto mais alto e o mais baixo")
        grid_params.addWidget(self.txtDesnivel, 1, 1)
        
        # Área
        grid_params.addWidget(QLabel("Área (km²):"), 2, 0)
        self.txtArea = QLineEdit()
        self.txtArea.setValidator(QDoubleValidator(0, 9999, 6))
        self.txtArea.setToolTip("Área da bacia em km²")
        grid_params.addWidget(self.txtArea, 2, 1)
        
        # Declividade
        grid_params.addWidget(QLabel("Declividade (%):"), 3, 0)
        self.txtDeclividade = QLineEdit()
        self.txtDeclividade.setValidator(QDoubleValidator(0, 100, 4))
        self.txtDeclividade.setToolTip("Declividade média da bacia em %")
        grid_params.addWidget(self.txtDeclividade, 3, 1)
        
        layout.addWidget(grp_params)
        
        # Grupo de seleção de método
        grp_metodo = QGroupBox("Método de Cálculo")
        grid_metodo = QGridLayout(grp_metodo)
        
        grid_metodo.addWidget(QLabel("Método:"), 0, 0)
        self.cmbMetodo = QComboBox()
        for key, info in self.METODOS.items():
            self.cmbMetodo.addItem(f"{info['nome']} - {info['descricao']}", key)
        self.cmbMetodo.currentIndexChanged.connect(self.atualizar_info_metodo)
        grid_metodo.addWidget(self.cmbMetodo, 0, 1)
        
        # Fórmula do método
        self.lblFormula = QLabel()
        self.lblFormula.setStyleSheet("color: #666; font-style: italic;")
        grid_metodo.addWidget(self.lblFormula, 1, 0, 1, 2)
        
        layout.addWidget(grp_metodo)
        
        # Botão de cálculo
        self.btnCalcular = QPushButton("⚡ CALCULAR TEMPO DE CONCENTRAÇÃO")
        self.btnCalcular.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.btnCalcular.clicked.connect(self.calcular_tc)
        layout.addWidget(self.btnCalcular)
        
        # Resultado
        grp_resultado = QGroupBox("Resultado")
        grid_resultado = QGridLayout(grp_resultado)
        
        grid_resultado.addWidget(QLabel("Tempo de Concentração:"), 0, 0)
        self.txtTempo = QLineEdit()
        self.txtTempo.setReadOnly(True)
        self.txtTempo.setStyleSheet("""
            font-weight: bold; 
            font-size: 18px; 
            background-color: #E3F2FD;
            padding: 8px;
        """)
        grid_resultado.addWidget(self.txtTempo, 0, 1)
        grid_resultado.addWidget(QLabel("minutos"), 0, 2)
        
        layout.addWidget(grp_resultado)
        
        # Tabela comparativa
        grp_tabela = QGroupBox("Comparação entre Métodos (clique para selecionar)")
        tabela_layout = QVBoxLayout(grp_tabela)
        
        self.btnGerarTabela = QPushButton("📊 Gerar Tabela Comparativa")
        self.btnGerarTabela.clicked.connect(self.gerar_tabela_comparativa)
        tabela_layout.addWidget(self.btnGerarTabela)
        
        self.tblComparacao = QTableWidget()
        self.tblComparacao.setMaximumHeight(150)
        self.tblComparacao.setSelectionMode(QTableWidget.SingleSelection)
        self.tblComparacao.cellClicked.connect(self.ao_clicar_celula)
        tabela_layout.addWidget(self.tblComparacao)
        
        # Armazenar resultados da tabela para uso no clique
        self.resultados_tabela = []
        
        layout.addWidget(grp_tabela)
        
        # Botões principais
        btn_layout = QHBoxLayout()
        
        self.btnOk = QPushButton("✓ Usar Este Valor")
        self.btnOk.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        self.btnOk.clicked.connect(self.accept)
        btn_layout.addWidget(self.btnOk)
        
        self.btnCancelar = QPushButton("Cancelar")
        self.btnCancelar.clicked.connect(self.reject)
        btn_layout.addWidget(self.btnCancelar)
        
        layout.addLayout(btn_layout)
        
        # Atualizar info inicial
        self.atualizar_info_metodo()
        
    def carregar_valores_iniciais(self):
        """Carrega valores iniciais nos campos"""
        if self.distancia_inicial:
            self.txtDistancia.setText(str(self.distancia_inicial))
        if self.desnivel_inicial:
            self.txtDesnivel.setText(str(self.desnivel_inicial))
        if self.area_inicial:
            self.txtArea.setText(str(self.area_inicial))
        if self.declividade_inicial:
            self.txtDeclividade.setText(str(self.declividade_inicial))
            
    def atualizar_info_metodo(self):
        """Atualiza informações do método selecionado"""
        metodo_key = self.cmbMetodo.currentData()
        if metodo_key and metodo_key in self.METODOS:
            info = self.METODOS[metodo_key]
            self.lblFormula.setText(f"Fórmula: {info['formula']}")
            
    def obter_valores(self):
        """Obtém valores dos campos"""
        valores = {}
        
        try:
            if self.txtDistancia.text():
                valores['distancia'] = float(self.txtDistancia.text())
        except ValueError:
            pass
            
        try:
            if self.txtDesnivel.text():
                valores['desnivel'] = float(self.txtDesnivel.text())
        except ValueError:
            pass
            
        try:
            if self.txtArea.text():
                valores['area'] = float(self.txtArea.text())
        except ValueError:
            pass
            
        try:
            if self.txtDeclividade.text():
                valores['declividade'] = float(self.txtDeclividade.text())
        except ValueError:
            pass
            
        return valores
        
    def validar_metodo(self, metodo_key, valores):
        """Valida se os parâmetros necessários estão disponíveis"""
        if metodo_key not in self.METODOS:
            return False, "Método não encontrado"
            
        info = self.METODOS[metodo_key]
        faltando = []
        
        for param in info['requer']:
            if param not in valores or valores[param] <= 0:
                faltando.append(param)
                
        if faltando:
            return False, f"Parâmetros faltando: {', '.join(faltando)}"
            
        return True, ""
        
    def calcular_tc(self):
        """Calcula tempo de concentração pelo método selecionado"""
        metodo_key = self.cmbMetodo.currentData()
        valores = self.obter_valores()
        
        # Validar
        valido, msg = self.validar_metodo(metodo_key, valores)
        if not valido:
            QMessageBox.warning(self, "Atenção", msg)
            return
            
        try:
            tc = None
            
            if metodo_key == 'kirpich':
                tc = TempoConcentracao.kirpich(
                    valores['distancia'], 
                    valores['desnivel']
                )
            elif metodo_key == 'giandotti':
                tc = TempoConcentracao.giandotti(
                    valores['area'],
                    valores['distancia'],
                    valores['desnivel']
                )
            elif metodo_key == 'ventura':
                tc = TempoConcentracao.ventura(
                    valores['area'],
                    valores['declividade']
                )
            elif metodo_key == 'bransby_williams':
                tc = TempoConcentracao.bransby_williams(
                    valores['area'],
                    valores['distancia'],
                    valores['declividade']
                )
                
            if tc is not None and tc > 0:
                self.tempo_calculado = tc
                self.metodo_usado = metodo_key
                self.txtTempo.setText(f"{tc:.2f}")
            else:
                QMessageBox.warning(
                    self, "Atenção",
                    "Não foi possível calcular o Tc. Verifique os parâmetros."
                )
                
        except Exception as e:
            QMessageBox.critical(
                self, "Erro",
                f"Erro ao calcular: {str(e)}"
            )
            
    def gerar_tabela_comparativa(self):
        """Gera tabela comparando todos os métodos"""
        valores = self.obter_valores()
        
        if not valores:
            QMessageBox.warning(
                self, "Atenção",
                "Preencha pelo menos alguns parâmetros para gerar a comparação."
            )
            return
            
        # Calcular por todos os métodos possíveis
        resultados = []
        
        for key, info in self.METODOS.items():
            valido, _ = self.validar_metodo(key, valores)
            if valido:
                try:
                    if key == 'kirpich':
                        tc = TempoConcentracao.kirpich(valores['distancia'], valores['desnivel'])
                    elif key == 'giandotti':
                        tc = TempoConcentracao.giandotti(valores['area'], valores['distancia'], valores['desnivel'])
                    elif key == 'ventura':
                        tc = TempoConcentracao.ventura(valores['area'], valores['declividade'])
                    elif key == 'bransby_williams':
                        tc = TempoConcentracao.bransby_williams(valores['area'], valores['distancia'], valores['declividade'])
                    else:
                        continue
                        
                    if tc and tc > 0:
                        resultados.append((key, info['nome'], tc))
                except:
                    pass
                    
        if not resultados:
            QMessageBox.warning(
                self, "Atenção",
                "Nenhum método pôde ser calculado com os parâmetros fornecidos."
            )
            return
            
        # Calcular média
        media = sum(tc for _, _, tc in resultados) / len(resultados)
        resultados.append(('media', "MÉDIA", media))
        
        # Armazenar para uso no clique
        self.resultados_tabela = resultados
        
        # Preencher tabela
        self.tblComparacao.clear()
        self.tblComparacao.setRowCount(1)
        self.tblComparacao.setColumnCount(len(resultados))
        
        headers = [nome for _, nome, _ in resultados]
        self.tblComparacao.setHorizontalHeaderLabels(headers)
        
        for i, (key, nome, tc) in enumerate(resultados):
            item = QTableWidgetItem(f"{tc:.2f} min")
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tblComparacao.setItem(0, i, item)
            
        self.tblComparacao.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
    def ao_clicar_celula(self, row, col):
        """Ao clicar em uma célula da tabela, seleciona o valor correspondente"""
        if not self.resultados_tabela or col >= len(self.resultados_tabela):
            return
            
        key, nome, tc = self.resultados_tabela[col]
        
        # Atualizar valores selecionados
        self.tempo_calculado = tc
        self.metodo_usado = key
        self.txtTempo.setText(f"{tc:.2f}")
        
        # Destacar célula selecionada
        for c in range(self.tblComparacao.columnCount()):
            item = self.tblComparacao.item(0, c)
            if item:
                if c == col:
                    item.setBackground(Qt.GlobalColor.green)
                else:
                    item.setBackground(Qt.GlobalColor.white)
        
    def get_tempo(self):
        """Retorna tempo calculado"""
        return self.tempo_calculado
        
    def get_metodo(self):
        """Retorna método usado"""
        return self.metodo_usado
        
    def get_parametros(self):
        """Retorna parâmetros usados"""
        return {
            'metodo': self.metodo_usado,
            'tempo': self.tempo_calculado,
            **self.obter_valores()
        }

