# -*- coding: utf-8 -*-
"""
Dialog para Gerenciamento de Curvas IDF
Com suporte a edição e salvamento de parâmetros personalizados
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox,
    QDoubleSpinBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QCheckBox, QInputDialog, QHeaderView
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QDoubleValidator

import os
import json

# Import persistence manager
from .persistence_manager import PersistenceManager


class IDFDialog(QDialog):
    """Dialog para cálculo de intensidade pela curva IDF com edição e salvamento"""
    
    # Arquivo de configuração para salvar parâmetros personalizados
    CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'dados', 'curvas_idf_usuario.json')
    
    def __init__(self, parent=None, duracao_inicial=None, tr_inicial=None):
        super(IDFDialog, self).__init__(parent)
        self.intensidade_calculada = None
        self.duracao_inicial = duracao_inicial
        self.tr_inicial = tr_inicial
        self.modo_edicao = False
        self.setup_ui()
        self.carregar_curvas()
        self.carregar_curvas_usuario()
        
        # Carregar estado salvo do projeto
        self.carregar_estado_salvo()
        
        # Aplicar valores iniciais se fornecidos (sobrescreve estado salvo)
        if duracao_inicial:
            self.spnDuracao.setValue(duracao_inicial)
        if tr_inicial:
            self.spnTR.setValue(tr_inicial)
        
    def setup_ui(self):
        """Configura interface"""
        self.setWindowTitle("Calculadora de Curvas IDF")
        self.setMinimumSize(600, 550)
        
        layout = QVBoxLayout(self)
        
        # Seleção de cidade
        grp_cidade = QGroupBox("Localização")
        grid_cidade = QGridLayout(grp_cidade)
        
        grid_cidade.addWidget(QLabel("Cidade/Curva:"), 0, 0)
        self.cmbCidade = QComboBox()
        self.cmbCidade.setMinimumWidth(300)
        grid_cidade.addWidget(self.cmbCidade, 0, 1)
        
        # Botão para adicionar nova cidade
        self.btnNovaCidade = QPushButton("➕ Nova")
        self.btnNovaCidade.setToolTip("Adicionar nova curva IDF personalizada")
        self.btnNovaCidade.clicked.connect(self.adicionar_nova_curva)
        grid_cidade.addWidget(self.btnNovaCidade, 0, 2)
        
        layout.addWidget(grp_cidade)
        
        # Parâmetros IDF
        grp_params = QGroupBox("Parâmetros da Equação IDF: I = (K × TR^a) / (t + b)^c")
        grid_params = QGridLayout(grp_params)
        
        # Checkbox para habilitar edição
        self.chkEditarParametros = QCheckBox("Habilitar edição dos parâmetros")
        self.chkEditarParametros.stateChanged.connect(self.toggle_edicao)
        grid_params.addWidget(self.chkEditarParametros, 0, 0, 1, 3)
        
        # Parâmetros K, a, b, c
        grid_params.addWidget(QLabel("K:"), 1, 0)
        self.txtK = QLineEdit()
        self.txtK.setValidator(QDoubleValidator(0, 99999, 4))
        self.txtK.setReadOnly(True)
        self.txtK.setToolTip("Parâmetro K da equação IDF")
        grid_params.addWidget(self.txtK, 1, 1)
        grid_params.addWidget(QLabel("(coeficiente)"), 1, 2)
        
        grid_params.addWidget(QLabel("a:"), 2, 0)
        self.txtA = QLineEdit()
        self.txtA.setValidator(QDoubleValidator(0, 10, 4))
        self.txtA.setReadOnly(True)
        self.txtA.setToolTip("Expoente do tempo de retorno")
        grid_params.addWidget(self.txtA, 2, 1)
        grid_params.addWidget(QLabel("(expoente TR)"), 2, 2)
        
        grid_params.addWidget(QLabel("b:"), 3, 0)
        self.txtB = QLineEdit()
        self.txtB.setValidator(QDoubleValidator(0, 1000, 4))
        self.txtB.setReadOnly(True)
        self.txtB.setToolTip("Parâmetro de ajuste da duração")
        grid_params.addWidget(self.txtB, 3, 1)
        grid_params.addWidget(QLabel("(ajuste duração)"), 3, 2)
        
        grid_params.addWidget(QLabel("c:"), 4, 0)
        self.txtC = QLineEdit()
        self.txtC.setValidator(QDoubleValidator(0, 10, 4))
        self.txtC.setReadOnly(True)
        self.txtC.setToolTip("Expoente da duração")
        grid_params.addWidget(self.txtC, 4, 1)
        grid_params.addWidget(QLabel("(expoente duração)"), 4, 2)
        
        # Fonte dos dados
        grid_params.addWidget(QLabel("Fonte:"), 5, 0)
        self.txtFonte = QLineEdit()
        self.txtFonte.setReadOnly(True)
        self.txtFonte.setPlaceholderText("Ex: COPASA-MG, 2018")
        grid_params.addWidget(self.txtFonte, 5, 1, 1, 2)
        
        # Botões de salvar/excluir
        btn_params_layout = QHBoxLayout()
        
        self.btnSalvarParametros = QPushButton("💾 Salvar Parâmetros")
        self.btnSalvarParametros.setEnabled(False)
        self.btnSalvarParametros.clicked.connect(self.salvar_parametros)
        self.btnSalvarParametros.setToolTip("Salvar parâmetros modificados para uso futuro")
        btn_params_layout.addWidget(self.btnSalvarParametros)
        
        self.btnExcluirCurva = QPushButton("🗑️ Excluir Curva")
        self.btnExcluirCurva.setEnabled(False)
        self.btnExcluirCurva.clicked.connect(self.excluir_curva)
        self.btnExcluirCurva.setToolTip("Excluir curva personalizada (apenas curvas do usuário)")
        btn_params_layout.addWidget(self.btnExcluirCurva)
        
        grid_params.addLayout(btn_params_layout, 6, 0, 1, 3)
        
        layout.addWidget(grp_params)
        
        # Cálculo
        grp_calc = QGroupBox("Cálculo de Intensidade")
        grid_calc = QGridLayout(grp_calc)
        
        grid_calc.addWidget(QLabel("Tempo de Retorno (anos):"), 0, 0)
        self.spnTR = QSpinBox()
        self.spnTR.setRange(2, 100)
        self.spnTR.setValue(25)
        grid_calc.addWidget(self.spnTR, 0, 1)
        
        grid_calc.addWidget(QLabel("Duração (min):"), 1, 0)
        self.spnDuracao = QDoubleSpinBox()
        self.spnDuracao.setRange(5, 1440)
        self.spnDuracao.setDecimals(2)
        self.spnDuracao.setValue(30)
        grid_calc.addWidget(self.spnDuracao, 1, 1)
        
        self.btnCalcularIDF = QPushButton("⚡ Calcular Intensidade")
        self.btnCalcularIDF.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.btnCalcularIDF.clicked.connect(self.calcular_intensidade)
        grid_calc.addWidget(self.btnCalcularIDF, 2, 0, 1, 2)
        
        grid_calc.addWidget(QLabel("Intensidade (mm/h):"), 3, 0)
        self.txtIntensidade = QLineEdit()
        self.txtIntensidade.setReadOnly(True)
        self.txtIntensidade.setStyleSheet("""
            font-weight: bold; 
            font-size: 16px; 
            background-color: #E3F2FD;
            padding: 5px;
        """)
        grid_calc.addWidget(self.txtIntensidade, 3, 1)
        
        layout.addWidget(grp_calc)
        
        # Tabela de intensidades para diferentes TRs
        grp_tabela = QGroupBox("Tabela de Intensidades (mm/h)")
        tabela_layout = QVBoxLayout(grp_tabela)
        
        self.btnGerarTabela = QPushButton("📊 Gerar Tabela para Múltiplos TRs")
        self.btnGerarTabela.clicked.connect(self.gerar_tabela_intensidades)
        tabela_layout.addWidget(self.btnGerarTabela)
        
        self.tblIntensidades = QTableWidget()
        self.tblIntensidades.setMaximumHeight(120)
        tabela_layout.addWidget(self.tblIntensidades)
        
        layout.addWidget(grp_tabela)
        
        # Botões principais
        btn_layout = QHBoxLayout()
        
        self.btnOk = QPushButton("✓ Usar Intensidade")
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
        
        # Conectar sinais
        self.cmbCidade.currentIndexChanged.connect(self.atualizar_parametros)
        
    def toggle_edicao(self, state):
        """Habilita/desabilita edição dos parâmetros"""
        self.modo_edicao = state == Qt.CheckState.Checked
        self.txtK.setReadOnly(not self.modo_edicao)
        self.txtA.setReadOnly(not self.modo_edicao)
        self.txtB.setReadOnly(not self.modo_edicao)
        self.txtC.setReadOnly(not self.modo_edicao)
        self.txtFonte.setReadOnly(not self.modo_edicao)
        self.btnSalvarParametros.setEnabled(self.modo_edicao)
        
        # Estilo visual para indicar modo de edição
        estilo_edicao = "background-color: #FFF9C4;" if self.modo_edicao else ""
        self.txtK.setStyleSheet(estilo_edicao)
        self.txtA.setStyleSheet(estilo_edicao)
        self.txtB.setStyleSheet(estilo_edicao)
        self.txtC.setStyleSheet(estilo_edicao)
        self.txtFonte.setStyleSheet(estilo_edicao)
        
        # Verificar se pode excluir (apenas curvas do usuário)
        cidade = self.cmbCidade.currentText()
        self.btnExcluirCurva.setEnabled(
            self.modo_edicao and cidade in self.curvas_usuario
        )
        
    def carregar_curvas(self):
        """Carrega curvas IDF padrão"""
        self.curvas_padrao = {
            'Juiz de Fora - MG': {'K': 1450, 'a': 0.15, 'b': 20, 'c': 0.90, 'fonte': 'COPASA-MG, 2018'},
            'Juiz de Fora - Norte Eq.11': {'K': 2314.482, 'a': 0.149, 'b': 22.129, 'c': 0.903, 'fonte': 'GEASA, 2025'},
            'Juiz de Fora - Sul Eq.10': {'K': 1646.3, 'a': 0.171, 'b': 15.496, 'c': 0.822, 'fonte': 'GEASA, 2025'},
            'Belo Horizonte - MG': {'K': 1447, 'a': 0.12, 'b': 15, 'c': 0.85, 'fonte': 'COPASA-MG'},
            'São Paulo - SP': {'K': 1540, 'a': 0.14, 'b': 16, 'c': 0.88, 'fonte': 'DAEE-SP'},
            'Rio de Janeiro - RJ': {'K': 1239, 'a': 0.15, 'b': 20, 'c': 0.74, 'fonte': 'Rio-Águas'},
            'Curitiba - PR': {'K': 1360, 'a': 0.16, 'b': 18, 'c': 0.82, 'fonte': 'SUDERHSA-PR'},
            'Porto Alegre - RS': {'K': 1297, 'a': 0.14, 'b': 12, 'c': 0.80, 'fonte': 'DMAE-RS'},
            'Brasília - DF': {'K': 1519, 'a': 0.16, 'b': 16, 'c': 0.86, 'fonte': 'CAESB-DF'},
            'Salvador - BA': {'K': 1420, 'a': 0.12, 'b': 10, 'c': 0.78, 'fonte': 'EMBASA-BA'},
            'Fortaleza - CE': {'K': 1380, 'a': 0.13, 'b': 14, 'c': 0.76, 'fonte': 'CAGECE-CE'},
            'Recife - PE': {'K': 1500, 'a': 0.14, 'b': 12, 'c': 0.82, 'fonte': 'COMPESA-PE'},
            'Manaus - AM': {'K': 1650, 'a': 0.13, 'b': 15, 'c': 0.80, 'fonte': 'INPA'},
            'Belém - PA': {'K': 1580, 'a': 0.12, 'b': 14, 'c': 0.78, 'fonte': 'COSANPA-PA'},
            'Goiânia - GO': {'K': 1480, 'a': 0.15, 'b': 17, 'c': 0.84, 'fonte': 'SANEAGO-GO'},
            'Campinas - SP': {'K': 1520, 'a': 0.14, 'b': 15, 'c': 0.86, 'fonte': 'SANASA-SP'},
            'Vitória - ES': {'K': 1350, 'a': 0.13, 'b': 16, 'c': 0.79, 'fonte': 'CESAN-ES'},
        }
        
        self.curvas_usuario = {}
        self.curvas = self.curvas_padrao.copy()
        
    def carregar_curvas_usuario(self):
        """Carrega curvas IDF salvas pelo usuário"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.curvas_usuario = json.load(f)
                    
                # Mesclar com curvas padrão (usuário sobrescreve padrão)
                self.curvas.update(self.curvas_usuario)
                
        except Exception as e:
            print(f"Erro ao carregar curvas do usuário: {e}")
            
        # Atualizar combo
        self.cmbCidade.clear()
        
        # Adicionar curvas padrão
        self.cmbCidade.addItem("--- Curvas Padrão ---")
        self.cmbCidade.model().item(0).setEnabled(False)
        for cidade in sorted(self.curvas_padrao.keys()):
            self.cmbCidade.addItem(cidade)
            
        # Adicionar curvas do usuário se houver
        if self.curvas_usuario:
            self.cmbCidade.addItem("--- Curvas Personalizadas ---")
            idx = self.cmbCidade.count() - 1
            self.cmbCidade.model().item(idx).setEnabled(False)
            for cidade in sorted(self.curvas_usuario.keys()):
                if cidade not in self.curvas_padrao:
                    self.cmbCidade.addItem(f"⭐ {cidade}")
                    
        # Selecionar primeira cidade válida
        self.cmbCidade.setCurrentIndex(1)
        self.atualizar_parametros()
        
    def salvar_curvas_usuario(self):
        """Salva curvas do usuário em arquivo JSON"""
        try:
            # Garantir que o diretório existe
            os.makedirs(os.path.dirname(self.CONFIG_FILE), exist_ok=True)
            
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.curvas_usuario, f, indent=2, ensure_ascii=False)
                
            return True
        except Exception as e:
            QMessageBox.critical(
                self, "Erro",
                f"Erro ao salvar configurações: {str(e)}"
            )
            return False
        
    def atualizar_parametros(self):
        """Atualiza parâmetros conforme cidade selecionada"""
        cidade = self.cmbCidade.currentText()
        
        # Remover prefixo de curva personalizada
        if cidade.startswith("⭐ "):
            cidade = cidade[2:]
            
        if cidade in self.curvas:
            params = self.curvas[cidade]
            self.txtK.setText(str(params['K']))
            self.txtA.setText(str(params['a']))
            self.txtB.setText(str(params['b']))
            self.txtC.setText(str(params['c']))
            self.txtFonte.setText(params.get('fonte', ''))
            
            # Verificar se pode excluir
            self.btnExcluirCurva.setEnabled(
                self.modo_edicao and cidade in self.curvas_usuario
            )
            
    def salvar_parametros(self):
        """Salva parâmetros modificados"""
        try:
            cidade = self.cmbCidade.currentText()
            if cidade.startswith("⭐ "):
                cidade = cidade[2:]
                
            # Validar valores
            K = float(self.txtK.text())
            a = float(self.txtA.text())
            b = float(self.txtB.text())
            c = float(self.txtC.text())
            fonte = self.txtFonte.text()
            
            if K <= 0 or a <= 0 or c <= 0:
                QMessageBox.warning(
                    self, "Atenção",
                    "Os parâmetros K, a e c devem ser maiores que zero."
                )
                return
                
            # Confirmar salvamento
            resposta = QMessageBox.question(
                self, "Confirmar",
                f"Deseja salvar os parâmetros para '{cidade}'?\n\n"
                f"K = {K}\na = {a}\nb = {b}\nc = {c}\n"
                f"Fonte: {fonte}\n\n"
                "Estes parâmetros serão salvos e estarão disponíveis nas próximas sessões.",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if resposta == QMessageBox.Yes:
                # Salvar nos parâmetros do usuário
                self.curvas_usuario[cidade] = {
                    'K': K, 'a': a, 'b': b, 'c': c, 'fonte': fonte
                }
                self.curvas[cidade] = self.curvas_usuario[cidade]
                
                if self.salvar_curvas_usuario():
                    QMessageBox.information(
                        self, "Sucesso",
                        f"Parâmetros salvos para '{cidade}'!"
                    )
                    # Recarregar lista
                    self.carregar_curvas_usuario()
                    
        except ValueError:
            QMessageBox.warning(
                self, "Atenção",
                "Verifique se todos os valores numéricos estão corretos."
            )
            
    def adicionar_nova_curva(self):
        """Adiciona nova curva IDF personalizada"""
        nome, ok = QInputDialog.getText(
            self, "Nova Curva IDF",
            "Nome da cidade/localidade:"
        )
        
        if ok and nome:
            nome = nome.strip()
            if nome in self.curvas:
                QMessageBox.warning(
                    self, "Atenção",
                    f"Já existe uma curva com o nome '{nome}'."
                )
                return
                
            # Adicionar com valores padrão
            self.curvas_usuario[nome] = {
                'K': 1400, 'a': 0.14, 'b': 15, 'c': 0.85, 'fonte': 'Personalizada'
            }
            self.curvas[nome] = self.curvas_usuario[nome]
            
            if self.salvar_curvas_usuario():
                QMessageBox.information(
                    self, "Sucesso",
                    f"Curva '{nome}' adicionada!\n\n"
                    "Habilite a edição para modificar os parâmetros."
                )
                self.carregar_curvas_usuario()
                
                # Selecionar a nova curva
                for i in range(self.cmbCidade.count()):
                    if nome in self.cmbCidade.itemText(i):
                        self.cmbCidade.setCurrentIndex(i)
                        break
                        
    def excluir_curva(self):
        """Exclui curva personalizada"""
        cidade = self.cmbCidade.currentText()
        if cidade.startswith("⭐ "):
            cidade = cidade[2:]
            
        if cidade not in self.curvas_usuario:
            QMessageBox.warning(
                self, "Atenção",
                "Apenas curvas personalizadas podem ser excluídas."
            )
            return
            
        resposta = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Deseja excluir a curva '{cidade}'?\n\n"
            "Esta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if resposta == QMessageBox.Yes:
            del self.curvas_usuario[cidade]
            del self.curvas[cidade]
            
            if self.salvar_curvas_usuario():
                QMessageBox.information(
                    self, "Sucesso",
                    f"Curva '{cidade}' excluída!"
                )
                self.carregar_curvas_usuario()
            
    def calcular_intensidade(self):
        """Calcula intensidade pela equação IDF"""
        try:
            K = float(self.txtK.text())
            a = float(self.txtA.text())
            b = float(self.txtB.text())
            c = float(self.txtC.text())
            TR = self.spnTR.value()
            t = self.spnDuracao.value()
            
            # I = (K * TR^a) / (t + b)^c
            I = (K * (TR ** a)) / ((t + b) ** c)
            
            self.intensidade_calculada = I
            self.txtIntensidade.setText(f"{I:.2f}")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao calcular: {str(e)}"
            )
            
    def gerar_tabela_intensidades(self):
        """Gera tabela de intensidades para múltiplos TRs e durações"""
        try:
            K = float(self.txtK.text())
            a = float(self.txtA.text())
            b = float(self.txtB.text())
            c = float(self.txtC.text())
            
            TRs = [2, 5, 10, 25, 50, 100]
            duracoes = [10, 15, 30, 60, 120]
            
            self.tblIntensidades.clear()
            self.tblIntensidades.setRowCount(len(duracoes))
            self.tblIntensidades.setColumnCount(len(TRs) + 1)
            
            # Cabeçalhos
            headers = ["Duração (min)"] + [f"TR={tr}" for tr in TRs]
            self.tblIntensidades.setHorizontalHeaderLabels(headers)
            
            # Preencher tabela
            for i, t in enumerate(duracoes):
                self.tblIntensidades.setItem(i, 0, QTableWidgetItem(str(t)))
                for j, TR in enumerate(TRs):
                    I = (K * (TR ** a)) / ((t + b) ** c)
                    self.tblIntensidades.setItem(i, j + 1, QTableWidgetItem(f"{I:.1f}"))
                    
            # Ajustar colunas
            self.tblIntensidades.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            
        except Exception as e:
            QMessageBox.warning(
                self, "Erro",
                f"Erro ao gerar tabela: {str(e)}"
            )
            
    def get_intensidade(self):
        """Retorna intensidade calculada"""
        return self.intensidade_calculada
        
    def get_parametros(self):
        """Retorna parâmetros atuais"""
        return {
            'cidade': self.cmbCidade.currentText(),
            'K': float(self.txtK.text()),
            'a': float(self.txtA.text()),
            'b': float(self.txtB.text()),
            'c': float(self.txtC.text()),
            'TR': self.spnTR.value(),
            'duracao': self.spnDuracao.value(),
            'intensidade': self.intensidade_calculada
        }
    
    def carregar_estado_salvo(self):
        """Carrega estado salvo do projeto QGIS"""
        try:
            state = PersistenceManager.load_idf_state()
            if state:
                # Restaurar cidade
                cidade = state.get('cidade')
                if cidade:
                    idx = self.cmbCidade.findText(cidade)
                    if idx >= 0:
                        self.cmbCidade.setCurrentIndex(idx)
                
                # Restaurar TR e duração
                if 'TR' in state:
                    self.spnTR.setValue(state['TR'])
                if 'duracao' in state:
                    self.spnDuracao.setValue(state['duracao'])
                
                # Restaurar intensidade calculada
                if 'intensidade' in state and state['intensidade']:
                    self.intensidade_calculada = state['intensidade']
                    self.txtIntensidade.setText(f"{state['intensidade']:.2f}")
                
                # Restaurar tabela se houver
                if 'tabela' in state and state['tabela']:
                    self._restaurar_tabela(state['tabela'])
        except Exception as e:
            print(f"Erro ao carregar estado do IDF: {e}")
    
    def salvar_estado(self):
        """Salva estado atual no projeto QGIS"""
        try:
            state = {
                'cidade': self.cmbCidade.currentText(),
                'TR': self.spnTR.value(),
                'duracao': self.spnDuracao.value(),
                'intensidade': self.intensidade_calculada,
                'tabela': self._coletar_tabela()
            }
            PersistenceManager.save_idf_state(state)
        except Exception as e:
            print(f"Erro ao salvar estado do IDF: {e}")
    
    def _coletar_tabela(self):
        """Coleta dados da tabela de intensidades"""
        if self.tblIntensidades.rowCount() == 0:
            return None
        
        tabela = []
        for row in range(self.tblIntensidades.rowCount()):
            linha = []
            for col in range(self.tblIntensidades.columnCount()):
                item = self.tblIntensidades.item(row, col)
                linha.append(item.text() if item else '')
            tabela.append(linha)
        return tabela
    
    def _restaurar_tabela(self, dados_tabela):
        """Restaura tabela de intensidades"""
        if not dados_tabela:
            return
        
        self.tblIntensidades.setRowCount(len(dados_tabela))
        self.tblIntensidades.setColumnCount(len(dados_tabela[0]) if dados_tabela else 0)
        
        # Restaurar cabeçalhos
        if dados_tabela:
            headers = ["Duração (min)", "TR=2", "TR=5", "TR=10", "TR=25", "TR=50", "TR=100"]
            self.tblIntensidades.setHorizontalHeaderLabels(headers)
        
        for row_idx, row_data in enumerate(dados_tabela):
            for col_idx, cell_data in enumerate(row_data):
                self.tblIntensidades.setItem(row_idx, col_idx, QTableWidgetItem(cell_data))
        
        self.tblIntensidades.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    
    def closeEvent(self, event):
        """Salva estado ao fechar o dialog"""
        self.salvar_estado()
        super().closeEvent(event)
    
    def accept(self):
        """Sobrescreve accept para salvar antes de aceitar"""
        self.salvar_estado()
        super().accept()

