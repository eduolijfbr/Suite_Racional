# -*- coding: utf-8 -*-
"""
Dialog Principal do Plugin Método Racional Pro
Com cálculos automáticos baseados nas camadas selecionadas
"""

from qgis.PyQt import QtWidgets, QtCore, QtGui
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QTabWidget,
    QWidget, QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox,
    QTextEdit, QMessageBox, QFileDialog, QDoubleSpinBox, QSpinBox,
    QCheckBox, QFrame, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QProgressBar, QToolButton, QSizePolicy, QScrollArea
)
from qgis.PyQt.QtGui import QDoubleValidator, QFont, QColor, QPixmap, QImage, QPainter
import numpy as np
import webbrowser
from qgis.core import (
    QgsProject, QgsRasterLayer, QgsVectorLayer,
    QgsMessageLog, Qgis, QgsGeometry, QgsPointXY,
    QgsRasterBandStats, QgsFeatureRequest, QgsWkbTypes,
    QgsCoordinateTransform, QgsCoordinateReferenceSystem,
    QgsFeature, QgsVectorDataProvider
)
from qgis.gui import QgsMapToolEmitPoint

import os
import math
from datetime import datetime

# Import persistence manager
from .persistence_manager import PersistenceManager

# Import QGIS-native impermeability calculator (no external dependencies)
try:
    from ..processamento.impermeabilidade_qgis import calcular_impermeabilidade_qgis
    HAS_RASTER_MODULE = True
except ImportError as e:
    HAS_RASTER_MODULE = False
    print(f"Impermeabilidade QGIS module não disponível: {e}")


class MetodoRacionalDialog(QtWidgets.QDockWidget):
    """Dialog principal do plugin com cálculos automáticos (agora como DockWidget)"""
    
    calculo_concluido = pyqtSignal(dict)
    
    def __init__(self, iface, parent=None):
        """Constructor"""
        super(MetodoRacionalDialog, self).__init__("Método Racional Pro - Drenagem", parent)
        
        self.iface = iface
        self.canvas = iface.mapCanvas()
        
        # Configurar DockWidget
        self.setObjectName("MetodoRacionalProDock")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        # Widget principal e layout
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        
        # Variáveis
        self.camadas = {}
        self.resultados = {}
        self.area_selecionada = None  # Geometria da área selecionada
        
        # Sistema de bloqueio
        self.calculo_bloqueado = False
        self.dados_originais_bloqueados = {}
        
        # Configurar interface
        self.setup_ui()
        self.conectar_sinais()
        
        # Carregar camadas do projeto
        self.carregar_camadas_projeto()
        
        # Carregar estado persistido
        self.carregar_estado_persistido()
        
        # Setar o widget principal no Dock
        self.setWidget(self.main_widget)
        
    def criar_botao_ajuda(self, titulo, dica):
        """Cria um pequeno botão de interrogação com dica"""
        btn = QToolButton()
        btn.setText("?")
        btn.setFixedSize(20, 20)
        btn.setStyleSheet("""
            QToolButton {
                background-color: #9C27B0;
                color: white;
                border-radius: 10px;
                font-weight: bold;
                font-size: 11px;
            }
            QToolButton:hover {
                background-color: #7B1FA2;
            }
        """)
        btn.setToolTip("Clique para ver detalhes técnicos")
        btn.clicked.connect(lambda: self.mostrar_ajuda_formatada(titulo, dica))
        return btn

    def abrir_guia_tecnico(self):
        """Abre o guia técnico completo e limitações"""
        texto = """
            <h2 style='color: #2196F3;'>Nota de Limitação Técnica</h2>
            <ol>
                <li><b>Aplicabilidade do Método:</b> O Método Racional assume que a intensidade da chuva é uniforme e constante sobre toda a bacia durante o tempo de concentração (tc). Este método é estritamente recomendado para bacias de microdrenagem e áreas urbanas pequenas (geralmente inferiores a 50-100 hectares).</li>
                <br>
                <li><b>Macrodrenagem e Áreas Extensas:</b> Para bacias de macrodrenagem ou áreas que excedam os limites de aplicação do método, os resultados devem ser interpretados como estimativas preliminares. Recomenda-se a validação através do Método do Hidrograma Unitário (SCS/NRCS) ou modelagem hidráulica dinâmica (ex: SWMM).</li>
                <br>
                <li><b>Coeficiente de Escoamento (C):</b> Os valores de C baseiam-se em tabelas normatizadas de uso e ocupação do solo. Alterações futuras na impermeabilização da bacia invalidam as vazões de projeto calculadas.</li>
                <br>
                <li><b>Verificação Hidráulica:</b> A análise do Número de Froude (Fr) indica o regime de escoamento. Trechos com Fr próximos à unidade (regime crítico) apresentam instabilidade de lâmina d'água e requerem atenção especial para evitar transbordamentos.</li>
            </ol>
            <h2 style='color: #2196F3;'>Fluxo de Trabalho Recomendado</h2>
            <ol>
                <li><b>Camadas:</b> Selecione o MDT (Cotas) e a Área de Estudo (Polígono da Bacia). Se tiver imagem RGB, selecione para cálculo de C.</li>
                <li><b>Extração:</b> Clique em 'EXTRAIR PARÂMETROS'. O sistema calculará Área, Tc preliminar e C médio.</li>
                <li><b>Precipitação:</b> Clique em 'Calcular IDF' para definir sua cidade e o Tempo de Retorno (TR).</li>
                <li><b>Ajustes:</b> Refine a Rugosidade (n) conforme o material e a Declividade do projeto.</li>
                <li><b>Dimensionamento:</b> Clique em 'CALCULAR' para obter o diâmetro da galeria e as velocidades.</li>
                <li><b>Relatório:</b> Gere o documento final com todas as memórias de cálculo.</li>
            </ol>
            <hr>
            <p><small>Este plugin foi desenvolvido para auxiliar engenheiros no dimensionamento técnico, porém não substitui a análise do responsável técnico.</small></p>
        """
        self.mostrar_ajuda_formatada("Guia Técnico e Limitações", texto)

    def mostrar_ajuda_formatada(self, titulo, texto):
        """Exibe QMessageBox com suporte a HTML"""
        msg = QMessageBox(self)
        msg.setWindowTitle(f"Ajuda: {titulo}")
        msg.setIcon(QMessageBox.Information)
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(texto)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.setWindowFlags(msg.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        msg.exec_()
        
    def setup_ui(self):
        """Configura a interface gráfica"""
        self.main_widget.setMinimumSize(400, 600)
        
        # Layout principal do widget interno
        layout_container = self.main_layout
        layout_container.setSpacing(3)
        layout_container.setContentsMargins(5, 5, 5, 5)
        
        # Título compacto
        titulo = QLabel("MÉTODO RACIONAL PRO")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo.setFont(QFont("Arial", 12, QFont.Bold))
        titulo.setStyleSheet("color: #2196F3; margin: 2px;")
        layout_container.addWidget(titulo)
        
        # Botão de Guia Técnico no topo
        self.btnGuiaTecnico = QPushButton("📘 GUIA TÉCNICO E LIMITAÇÕES")
        self.btnGuiaTecnico.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                font-weight: bold;
                border-radius: 3px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #455A64;
            }
        """)
        self.btnGuiaTecnico.clicked.connect(self.abrir_guia_tecnico)
        layout_container.addWidget(self.btnGuiaTecnico)

        # ScrollArea para telas pequenas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(5)
        
        # Painel esquerdo - Dados de entrada
        painel_dados = self.criar_painel_dados()
        scroll_layout.addWidget(painel_dados)
        
        # Painel direito - Resultados
        painel_resultados = self.criar_painel_resultados()
        scroll_layout.addWidget(painel_resultados)
        
        scroll.setWidget(scroll_content)
        layout_container.addWidget(scroll)
        
        # Painel de informações
        painel_info = self.criar_painel_informacoes()
        layout_container.addWidget(painel_info)
        
        # Aplicar estilo
        self.aplicar_estilo()
        
    def criar_painel_dados(self):
        """Cria painel de dados de entrada"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Grupo de camadas (PRIMEIRO - para calcular dados automaticamente)
        grp_camadas = QGroupBox("Camadas do Projeto")
        grid_camadas = QGridLayout(grp_camadas)
        grid_camadas.setSpacing(3)
        
        grid_camadas.addWidget(QLabel("MDT:"), 0, 0)
        self.cmbMDT = QComboBox()
        self.cmbMDT.setToolTip("<b>MDT (Raster):</b> Modelo Digital de Terreno para extração automática de cotas e cálculo de desnível do talvegue.")
        grid_camadas.addWidget(self.cmbMDT, 0, 1)
        
        grid_camadas.addWidget(QLabel("Área de Estudo:"), 1, 0)
        self.cmbAreaEstudo = QComboBox()
        self.cmbAreaEstudo.setToolTip("<b>Área de Estudo:</b> Polígono que delimita a bacia. Selecione uma feição no mapa para extrair área e parâmetros específicos.")
        grid_camadas.addWidget(self.cmbAreaEstudo, 1, 1)
        
        grid_camadas.addWidget(QLabel("Imagem:"), 2, 0)
        self.cmbImagem = QComboBox()
        self.cmbImagem.setToolTip("<b>Imagem (Raster):</b> Imagem RGB para classificação multiespectral automática do coeficiente de impermeabilidade (C).")
        grid_camadas.addWidget(self.cmbImagem, 2, 1)
        
        grid_camadas.addWidget(QLabel("Curvas de Nível:"), 3, 0)
        self.cmbCurvasNivel = QComboBox()
        self.cmbCurvasNivel.setToolTip("<b>Curvas de Nível:</b> Alternativa ao MDT. Verifique se a camada possui campo numérico de elevação.")
        grid_camadas.addWidget(self.cmbCurvasNivel, 3, 1)
        grid_camadas.addWidget(QLabel("Cursos d'água:"), 4, 0)
        self.cmbCursosAgua = QComboBox()
        self.cmbCursosAgua.setToolTip("<b>Talvegue:</b> Linhas de drenagem para medir o comprimento exato do curso d'água principal.")
        grid_camadas.addWidget(self.cmbCursosAgua, 4, 1)
        
        grid_camadas.addWidget(QLabel("Exutório (Pontos):"), 5, 0)
        self.cmbExutorio = QComboBox()
        self.cmbExutorio.setToolTip("Camada de pontos para gravar o exutório (ponto mais baixo)")
        grid_camadas.addWidget(self.cmbExutorio, 5, 1)
        
        # Botão para extrair parâmetros automaticamente
        self.btnExtrairParametros = QPushButton("🔄 EXTRAIR PARÂMETROS")
        self.btnExtrairParametros.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.btnExtrairParametros.setMaximumHeight(28)
        self.btnExtrairParametros.setToolTip("Calcula automaticamente os parâmetros baseado nas camadas e seleção")
        self.btnExtrairParametros.setToolTip("Calcula automaticamente os parâmetros baseado nas camadas e seleção")
        grid_camadas.addWidget(self.btnExtrairParametros, 6, 0, 1, 2)
        
        layout.addWidget(grp_camadas)
        
        # Grupo de dados de entrada (calculados automaticamente ou manuais)
        grp_dados = QGroupBox("Dados (calculados automaticamente ou preencha manualmente)")
        grid = QGridLayout(grp_dados)
        grid.setSpacing(4)
        
        # Dicas detalhadas para cada campo (Rich Text HTML)
        text_limitacao = """
            <hr>
            <p style='color: #d32f2f;'><b>⚠️ NOTA DE LIMITAÇÃO TÉCNICA:</b></p>
            <small>
            <b>1. Aplicabilidade:</b> Recomendado para microdrenagem e áreas pequenas (< 50-100 ha).<br>
            <b>2. Macrodrenagem:</b> Para áreas extensas, os resultados são estimativas preliminares. Recomenda-se validação via SCS/NRCS ou SWMM.<br>
            <b>3. Coeficiente C:</b> Baseado em tabelas normatizadas. Alterações futuras na bacia invalidam os cálculos.<br>
            <b>4. Froude:</b> Verifique instabilidades em regimes próximos ao crítico (Fr ≈ 1).
            </small>
        """

        dicas = {
            "txtDistancia": f"""
                <h3>DISTÂNCIA DO TALVEGUE (L)</h3>
                <p>Comprimento do curso d'água principal da bacia, medido do ponto mais distante até a seção de controle.</p>
                <ul>
                    <li><b>Automático:</b> Extraído da camada de 'Cursos d'água' ou pela maior reta interna.</li>
                </ul>
                {text_limitacao}
            """,
            "txtDesnivel": f"""
                <h3>DESNÍVEL (H)</h3>
                <p>Diferença de altitude entre o ponto mais alto e o mais baixo da bacia.</p>
                <p><b>Fontes:</b> MDT (Raster) ou Curvas de Nível (Vetor).</p>
                {text_limitacao}
            """,
            "txtTempo": f"""
                <h3>TEMPO DE CONCENTRAÇÃO (Tc)</h3>
                <p>Tempo para que toda a bacia contribua no exutório.</p>
                <p><b>Kirpich:</b> Tc = 57 &times; (L&sup3;/H)<sup>0.385</sup></p>
                {text_limitacao}
            """,
            "txtImpermeabilidade": """
                <h3>COEFICIENTE DE ESCOAMENTO (C)</h3>
                <p>Fração da chuva que gera escoamento superficial.</p>
                <table border='1' cellspacing='0' cellpadding='3' style='border-collapse: collapse; width: 100%; font-size: 11px;'>
                    <tr style='background-color: #f2f2f2;'><th>Tipo de Superfície</th><th>Coeficiente C</th></tr>
                    <tr><td>Asfalto / Concreto</td><td>0.70 - 0.95</td></tr>
                    <tr><td>Telhados</td><td>0.75 - 0.95</td></tr>
                    <tr><td>Zonas Comerciais</td><td>0.50 - 0.90</td></tr>
                    <tr><td>Residencial Densa</td><td>0.50 - 0.75</td></tr>
                    <tr><td>Parques / Jardins</td><td>0.10 - 0.25</td></tr>
                    <tr><td>Florestas</td><td>0.05 - 0.20</td></tr>
                </table>
                <p><small><b>Nota 3:</b> Os valores de C baseiam-se em tabelas normatizadas. Alterações na impermeabilização invalidam as vazões de projeto.</small></p>
            """,
            "txtArea": f"""
                <h3>ÁREA DA BACIA (A)</h3>
                <p>Área total contribuinte (km&sup2;).</p>
                <p><b>Nota 1 (Aplicabilidade):</b> O Método Racional assume intensidade de chuva uniforme e constante sobre toda a bacia durante o Tc. Recomendado para áreas < 50-100 hectares.</p>
                {text_limitacao}
            """,
            "txtRugosidade": """
                <h3>COEFICIENTE DE MANNING (n)</h3>
                <table border='1' cellspacing='0' cellpadding='3' style='border-collapse: collapse; width: 100%; font-size: 11px;'>
                    <tr style='background-color: #f2f2f2;'><th>Material</th><th>n</th></tr>
                    <tr><td>PVC / PEAD</td><td>0.009 - 0.011</td></tr>
                    <tr><td>Concreto Liso</td><td>0.011 - 0.013</td></tr>
                    <tr><td>Concreto Rugoso</td><td>0.014 - 0.017</td></tr>
                    <tr><td>Canais Terra</td><td>0.018 - 0.025</td></tr>
                </table>
            """,
            "txtDeclividade": f"""
                <h3>DECLIVIDADE (S)</h3>
                <p>Inclinação longitudinal (%).</p>
                <ul>
                    <li><b>Mínima:</b> 0.3% (Autolimpeza).</li>
                    <li><b>Máxima:</b> 5.0% (Evitar erosão).</li>
                </ul>
                {text_limitacao}
            """,
        }
        
        # Campos de entrada - iniciam VAZIOS
        campos = [
            ("DISTÂNCIA:", "txtDistancia", "m"),
            ("DESNÍVEL:", "txtDesnivel", "m"),
            ("TEMPO:", "txtTempo", "min"),
            ("IMPERMEAB.:", "txtImpermeabilidade", ""),
            ("ÁREA:", "txtArea", "km²"),
            ("RUGOSIDADE:", "txtRugosidade", ""),
            ("DECLIVIDADE:", "txtDeclividade", "%"),
        ]
        
        for i, (label, nome, unidade) in enumerate(campos):
            lbl = QLabel(label)
            lbl.setMinimumWidth(90)
            grid.addWidget(lbl, i, 0)
            
            txt = QLineEdit()
            txt.setObjectName(nome)
            txt.setValidator(QDoubleValidator(0, 999999, 6))
            txt.setPlaceholderText("Auto")
            txt.setMaximumHeight(25)
            setattr(self, nome, txt)
            grid.addWidget(txt, i, 1)
            
            # Unidade (sempre na coluna 2)
            if unidade:
                lbl_un = QLabel(unidade)
                lbl_un.setFixedWidth(30)
                grid.addWidget(lbl_un, i, 2)
            else:
                # Espaçador vazio para manter alinhamento
                lbl_un = QLabel("")
                lbl_un.setFixedWidth(30)
                grid.addWidget(lbl_un, i, 2)
            
            # Botão de ajuda (sempre na coluna 3, alinhado verticalmente)
            btn_ajuda = self.criar_botao_ajuda(label[:-1], dicas.get(nome, ""))
            grid.addWidget(btn_ajuda, i, 3)
            
            # Botões especiais no lado direito (coluna 4)
            if nome == "txtTempo":
                self.btnCalcularTc = QPushButton("⏱️")
                self.btnCalcularTc.setToolTip("Abrir calculadora de Tempo de Concentração (Tc)")
                self.btnCalcularTc.setFixedWidth(30)
                self.btnCalcularTc.setMaximumHeight(25)
                self.btnCalcularTc.setStyleSheet("""
                    QPushButton {
                        background-color: #9C27B0;
                        color: white;
                        font-weight: bold;
                        border-radius: 3px;
                    }
                    QPushButton:hover {
                        background-color: #7B1FA2;
                    }
                """)
                self.btnCalcularTc.clicked.connect(self.abrir_dialog_tc)
                grid.addWidget(self.btnCalcularTc, i, 4)
            elif nome == "txtImpermeabilidade":
                self.btnVisualizarImper = QPushButton("👁️")
                self.btnVisualizarImper.setToolTip("Visualizar detalhes da classificação e imagem")
                self.btnVisualizarImper.setFixedWidth(30)
                self.btnVisualizarImper.setMaximumHeight(25)
                self.btnVisualizarImper.setEnabled(False)  # Habilitado apenas após cálculo
                self.btnVisualizarImper.clicked.connect(self.visualizar_detalhes_impermeabilidade)
                grid.addWidget(self.btnVisualizarImper, i, 4)
        
        # Valores padrão apenas para rugosidade e declividade
        self.txtRugosidade.setText("0.013")
        self.txtRugosidade.setPlaceholderText("0.013")
        self.txtDeclividade.setText("0.5")
        self.txtDeclividade.setPlaceholderText("0.5")
        

        layout.addWidget(grp_dados)
        
        # Grupo de precipitação
        grp_precip = QGroupBox("Precipitação")
        grid_precip = QGridLayout(grp_precip)
        
        grid_precip.addWidget(QLabel("Tempo de Retorno:"), 0, 0)
        self.txtTempoRetorno = QLineEdit()
        self.txtTempoRetorno.setReadOnly(True)
        self.txtTempoRetorno.setPlaceholderText("Defina no cálculo IDF")
        self.txtTempoRetorno.setText("25 anos")
        grid_precip.addWidget(self.txtTempoRetorno, 0, 1)
        
        grid_precip.addWidget(QLabel("Cidade (IDF):"), 1, 0)
        self.txtCidadeIDF = QLineEdit()
        self.txtCidadeIDF.setReadOnly(True)
        self.txtCidadeIDF.setPlaceholderText("Defina no cálculo IDF")
        self.txtCidadeIDF.setText("Juiz de Fora - MG")
        grid_precip.addWidget(self.txtCidadeIDF, 1, 1)
        
        grid_precip.addWidget(QLabel("Intensidade (mm/h):"), 2, 0)
        self.txtIntensidade = QLineEdit()
        self.txtIntensidade.setValidator(QDoubleValidator(0, 999, 2))
        self.txtIntensidade.setPlaceholderText("Calculado pela curva IDF")
        grid_precip.addWidget(self.txtIntensidade, 2, 1)
        
        self.btnIDF = QPushButton("📊 Calcular IDF")
        grid_precip.addWidget(self.btnIDF, 2, 2)
        
        layout.addWidget(grp_precip)
        
        # Botões de ação
        btn_layout = QHBoxLayout()
        
        self.btnCalcular = QPushButton("CALCULAR")
        self.btnCalcular.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 6px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btnCalcular.setMaximumHeight(30)
        btn_layout.addWidget(self.btnCalcular)
        
        self.btnLimpar = QPushButton("LIMPAR")
        self.btnLimpar.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                padding: 6px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        self.btnLimpar.setMaximumHeight(30)
        btn_layout.addWidget(self.btnLimpar)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
        return widget
        
    def criar_painel_resultados(self):
        """Cria painel de resultados"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Grupo de resultados
        self.grpResultados = QGroupBox("Resultados")
        grid = QGridLayout(self.grpResultados)
        grid.setSpacing(3)
        
        # Campos de resultado
        resultados = [
            ("DIÂMETRO:", "txtDiametro", "m"),
            ("LADO DA GALERIA:", "txtGaleria", "m"),
            ("ÁREA DA SEÇÃO:", "txtAreaSecao", "m²"),
            ("VELOC. ESCOAMENTO:", "txtVelocidade", "m/s"),
            ("VAZÃO:", "txtVazao", "m³/s"),
        ]
        
        for i, (label, nome, unidade) in enumerate(resultados):
            lbl = QLabel(label)
            lbl.setMinimumWidth(140)
            grid.addWidget(lbl, i, 0)
            
            txt = QLineEdit()
            txt.setObjectName(nome)
            txt.setReadOnly(True)
            txt.setStyleSheet("background-color: #f5f5f5;")
            setattr(self, nome, txt)
            grid.addWidget(txt, i, 1)
            
            grid.addWidget(QLabel(unidade), i, 2)
        
        layout.addWidget(self.grpResultados)
        
        # Botão gravar
        self.btnGravarCalculos = QPushButton("GRAVAR CÁLCULOS")
        self.btnGravarCalculos.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        self.btnGravarCalculos.setMaximumHeight(28)
        layout.addWidget(self.btnGravarCalculos)
        
        # Grupo de bloqueio
        grp_bloqueio = QGroupBox("BLOQUEAR/DESBLOQUEAR DADOS")
        bloq_layout = QVBoxLayout(grp_bloqueio)
        
        self.cmbBloqueio = QComboBox()
        self.cmbBloqueio.addItems(["DESBLOQUEADO", "BLOQUEADO"])
        bloq_layout.addWidget(self.cmbBloqueio)
        
        layout.addWidget(grp_bloqueio)
        grp_bloqueio.setVisible(False)
        
        # Grupo remover
        grp_remover = QGroupBox("Remover dados")
        rem_layout = QVBoxLayout(grp_remover)
        rem_layout.setContentsMargins(5, 10, 5, 5)
        
        self.btnRemover = QPushButton("REMOVER")
        self.btnRemover.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        self.btnRemover.setMaximumHeight(26)
        rem_layout.addWidget(self.btnRemover)
        
        layout.addWidget(grp_remover)
        
        # Verificações técnicas
        grp_verif = QGroupBox("Verificações Técnicas")
        verif_layout = QVBoxLayout(grp_verif)
        
        self.lblStatusVelocidade = QLabel("⏳ Aguardando cálculo...")
        verif_layout.addWidget(self.lblStatusVelocidade)
        
        self.lblStatusFroude = QLabel("⏳ Aguardando cálculo...")
        verif_layout.addWidget(self.lblStatusFroude)
        
        self.lblStatusLamina = QLabel("⏳ Aguardando cálculo...")
        verif_layout.addWidget(self.lblStatusLamina)
        
        self.lblStatusArea = QLabel("⏳ Aguardando cálculo...")
        verif_layout.addWidget(self.lblStatusArea)
        

        # Info do Exutório
        self.lblInfoExutorio = QLabel("⏳ Aguardando cálculo...")
        self.lblInfoExutorio.setWordWrap(True)
        verif_layout.addWidget(self.lblInfoExutorio)
        # self.lblInfoExutorio.setVisible(False)  # Mantido visível para mostrar a cota
        
        layout.addWidget(grp_verif)
        
        # Botões de exportação
        exp_layout = QHBoxLayout()
        
        self.btnGerarRelatorio = QPushButton("📄 Relatório")
        exp_layout.addWidget(self.btnGerarRelatorio)
        
        self.btnExportar = QPushButton("📤 Exportar")
        exp_layout.addWidget(self.btnExportar)
        
        layout.addLayout(exp_layout)
        self.btnExportar.setVisible(False)
        layout.addStretch()
        
        return widget
        
    def criar_painel_informacoes(self):
        """Cria painel de informações sobre materiais"""
        grp = QGroupBox("Informações:")
        grp.setStyleSheet("""
            QGroupBox {
                border: 2px solid #2196F3;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                color: #2196F3;
                font-weight: bold;
            }
        """)
        
        layout = QVBoxLayout(grp)
        
        self.lblInfoStatus = QLabel(
            "<b>Status:</b> Selecione as camadas e clique em 'EXTRAIR PARÂMETROS' "
            "para calcular automaticamente os dados da área selecionada."
        )
        self.lblInfoStatus.setWordWrap(True)
        layout.addWidget(self.lblInfoStatus)
        
        return grp
        
    def aplicar_estilo(self):
        """Aplica estilo visual ao dialog - versão compacta"""
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f4f8;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
            }
            QLineEdit {
                padding: 3px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border: 2px solid #2196F3;
            }
            QComboBox {
                padding: 3px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)
        
    def conectar_sinais(self):
        """Conecta sinais dos widgets"""
        # Botões principais
        self.btnCalcular.clicked.connect(self.executar_calculo)
        self.btnLimpar.clicked.connect(self.limpar_formulario)
        self.btnGravarCalculos.clicked.connect(self.salvar_calculo)
        self.btnGerarRelatorio.clicked.connect(self.gerar_relatorio)
        self.btnExportar.clicked.connect(self.exportar_resultados)
        self.btnRemover.clicked.connect(self.remover_dados)
        self.btnIDF.clicked.connect(self.calcular_intensidade_idf)
        
        # Botão de extração automática
        self.btnExtrairParametros.clicked.connect(self.extrair_parametros_automaticos)
        
        # Mudança de camadas - recalcular automaticamente e salvar
        self.cmbAreaEstudo.currentIndexChanged.connect(self.on_area_estudo_changed)
        self.cmbMDT.currentIndexChanged.connect(self.on_camada_changed)
        self.cmbImagem.currentIndexChanged.connect(self.on_camada_changed)
        self.cmbCursosAgua.currentIndexChanged.connect(self.on_camada_changed)
        self.cmbCurvasNivel.currentIndexChanged.connect(self.on_camada_changed)
        self.cmbExutorio.currentIndexChanged.connect(self.on_camada_changed)
        # self.txtCidadeIDF.textChanged.connect(self.on_camada_changed)
        # self.txtTempoRetorno.textChanged.connect(self.on_camada_changed)
        
        # Sinal de bloqueio
        self.cmbBloqueio.currentIndexChanged.connect(self.on_bloqueio_changed)
        
    def carregar_camadas_projeto(self):
        """Carrega camadas disponíveis no projeto QGIS"""
        # Bloquear sinais de TODOS os combos para evitar que auto-salvamento sobrescreva com vazio
        self.cmbMDT.blockSignals(True)
        self.cmbCurvasNivel.blockSignals(True)
        self.cmbImagem.blockSignals(True)
        self.cmbAreaEstudo.blockSignals(True)
        self.cmbCursosAgua.blockSignals(True)
        self.cmbExutorio.blockSignals(True)
        try:
            # Limpar combos
            self.cmbMDT.clear()
            self.cmbCurvasNivel.clear()
            self.cmbImagem.clear()
            self.cmbAreaEstudo.clear()
            self.cmbCursosAgua.clear()
            self.cmbExutorio.clear()
            
            # Adicionar opção vazia
            self.cmbMDT.addItem("-- Selecione --", None)
            self.cmbCurvasNivel.addItem("-- Selecione --", None)
            self.cmbImagem.addItem("-- Selecione --", None)
            self.cmbAreaEstudo.addItem("-- Selecione --", None)
            self.cmbCursosAgua.addItem("-- Selecione --", None)
            self.cmbExutorio.addItem("-- Selecione --", None)
            
            projeto = QgsProject.instance()
            
            for layer in projeto.mapLayers().values():
                # Camadas raster -> MDT e Imagem
                if isinstance(layer, QgsRasterLayer):
                    self.cmbMDT.addItem(layer.name(), layer)
                    self.cmbImagem.addItem(layer.name(), layer)
                    
                # Camadas vetoriais
                elif isinstance(layer, QgsVectorLayer):
                    geom_type = layer.geometryType()
                    
                    # Linhas -> Curvas de nível e Cursos d'água
                    if geom_type == QgsWkbTypes.LineGeometry:
                        self.cmbCurvasNivel.addItem(layer.name(), layer)
                        self.cmbCursosAgua.addItem(layer.name(), layer)
                        
                    # Polígonos -> Área de estudo
                    elif geom_type == QgsWkbTypes.PolygonGeometry:
                        self.cmbAreaEstudo.addItem(layer.name(), layer)
                        
                    # Pontos -> Exutório
                    elif geom_type == QgsWkbTypes.PointGeometry:
                        self.cmbExutorio.addItem(layer.name(), layer)
            
            # Carregar seleções salvas do projeto
            self.carregar_selecoes_projeto()
            
        finally:
            # Desbloquear sinais
            self.cmbMDT.blockSignals(False)
            self.cmbCurvasNivel.blockSignals(False)
            self.cmbImagem.blockSignals(False)
            self.cmbAreaEstudo.blockSignals(False)
            self.cmbCursosAgua.blockSignals(False)
            self.cmbExutorio.blockSignals(False)
            # QLineEdit não precisa de blockSignals aqui
            
        # Forçar atualização da lógica da área de estudo (conectar sinais de seleção)
        if self.cmbAreaEstudo.currentIndex() > 0:
            self.on_area_estudo_changed(self.cmbAreaEstudo.currentIndex())
        
    def salvar_selecoes_projeto(self):
        """Salva as camadas selecionadas nas variáveis do projeto QGIS"""
        # Salvar nome de cada camada selecionada
        camadas_config = {
            'mdt': self.cmbMDT.currentText() if self.cmbMDT.currentIndex() > 0 else '',
            'area_estudo': self.cmbAreaEstudo.currentText() if self.cmbAreaEstudo.currentIndex() > 0 else '',
            'imagem': self.cmbImagem.currentText() if self.cmbImagem.currentIndex() > 0 else '',
            'curvas_nivel': self.cmbCurvasNivel.currentText() if self.cmbCurvasNivel.currentIndex() > 0 else '',
            'cursos_agua': self.cmbCursosAgua.currentText() if self.cmbCursosAgua.currentIndex() > 0 else '',
            'exutorio': self.cmbExutorio.currentText() if self.cmbExutorio.currentIndex() > 0 else '',
            'cidade_idf': self.txtCidadeIDF.text(),
            'tempo_retorno': self.txtTempoRetorno.text(),
        }
        
        PersistenceManager.save('camadas_config', camadas_config)
            
    def carregar_selecoes_projeto(self):
        """Carrega as camadas salvas do projeto QGIS"""
        camadas_config = PersistenceManager.load('camadas_config', default={}, value_type=dict)
        if not camadas_config:
            return

        # Carregar MDT
        mdt_salvo = camadas_config.get('mdt', '')
        if mdt_salvo:
            idx = self.cmbMDT.findText(mdt_salvo)
            if idx >= 0:
                self.cmbMDT.setCurrentIndex(idx)
                
        # Carregar Área de Estudo
        area_salva = camadas_config.get('area_estudo', '')
        if area_salva:
            idx = self.cmbAreaEstudo.findText(area_salva)
            if idx >= 0:
                self.cmbAreaEstudo.setCurrentIndex(idx)
                
        # Carregar Imagem (tenta nova chave 'imagem' ou legacy 'uso_solo')
        imagem_salva = camadas_config.get('imagem', '') or camadas_config.get('uso_solo', '')
        if imagem_salva:
            idx = self.cmbImagem.findText(imagem_salva)
            if idx >= 0:
                self.cmbImagem.setCurrentIndex(idx)
                
        # Carregar Curvas de Nível
        curvas_salvas = camadas_config.get('curvas_nivel', '')
        if curvas_salvas:
            idx = self.cmbCurvasNivel.findText(curvas_salvas)
            if idx >= 0:
                self.cmbCurvasNivel.setCurrentIndex(idx)
                
        # Carregar Cursos d'água
        cursos_salvos = camadas_config.get('cursos_agua', '')
        if cursos_salvos:
            idx = self.cmbCursosAgua.findText(cursos_salvos)
            if idx >= 0:
                self.cmbCursosAgua.setCurrentIndex(idx)
                
        cidade_salva = camadas_config.get('cidade_idf', '')
        if cidade_salva:
            self.txtCidadeIDF.setText(cidade_salva)
                
        # Carregar Tempo de Retorno
        tr_salvo = camadas_config.get('tempo_retorno', '')
        if tr_salvo:
            self.txtTempoRetorno.setText(tr_salvo)

        # Carregar Exutório
        exutorio_salvo = camadas_config.get('exutorio', '')
        if exutorio_salvo:
            idx = self.cmbExutorio.findText(exutorio_salvo)
            if idx >= 0:
                self.cmbExutorio.setCurrentIndex(idx)
                    
    def on_area_estudo_changed(self, index):
        """Chamado quando a área de estudo muda"""
        # Desconectar sinal anterior se houver
        if hasattr(self, 'current_layer_area') and self.current_layer_area:
            try:
                self.current_layer_area.selectionChanged.disconnect(self.on_feature_selection_changed)
            except:
                pass
        
        layer = self.cmbAreaEstudo.currentData()
        self.current_layer_area = layer
        
        if layer:
            # Conectar sinal de seleção
            layer.selectionChanged.connect(self.on_feature_selection_changed)
            
        if index > 0:
            self.atualizar_info_selecao()
            
        # Salvar seleção no projeto
        self.salvar_selecoes_projeto()
        
        # Carregar dados da feição selecionada (se houver)
        self.on_feature_selection_changed()

    def on_feature_selection_changed(self, selected=None, deselected=None, clearAndSelect=None):
        """Chamado quando a seleção de feições muda"""
        self.atualizar_info_selecao()
        
        layer = self.cmbAreaEstudo.currentData()
        if not layer:
            return
            
        feature_id = PersistenceManager.get_current_feature_id(layer)
        layer_name = layer.name()
        
        if feature_id:
            # Tentar carregar dados específicos desta feição
            dados = PersistenceManager.load_feature_data(feature_id, layer_name)
            if dados:
                self._restaurar_dados(dados)
                self.iface.messageBar().pushMessage(
                    "Info",
                    f"Dados recuperados para a área selecionada.",
                    level=Qgis.Info,
                    duration=2
                )
            else:
                # Se não tem dados salvos para esta feição, limpar campos de DADOS
                # MAS MANTER seleções de camadas e IDF (cidade/TR)
                self.limpar_dados_calculo()
        else:
            # Nenhuma feição selecionada -> Limpar dados
            self.limpar_dados_calculo()
            
    def limpar_dados_calculo(self):
        """Limpa apenas os campos de dados e resultados, mantendo configurações"""
        # Limpar inputs numéricos
        self.txtDistancia.clear()
        self.txtDesnivel.clear()
        self.txtTempo.clear()
        self.txtImpermeabilidade.clear()
        self.txtIntensidade.clear()
        self.txtTempoRetorno.setText("25 anos")
        self.txtCidadeIDF.setText("Juiz de Fora - MG")
        
        # Manter valores padrão
        self.txtRugosidade.setText("0.013")
        self.txtDeclividade.setText("0.5")
        
        # Limpar resultados
        self.txtDiametro.clear()
        self.txtVazao.clear()
        self.txtVelocidade.clear()
        self.txtGaleria.clear()
        if hasattr(self, 'txtAreaSecao'): self.txtAreaSecao.clear()
        
        # Resetar verificações
        self.lblStatusVelocidade.setText("⏳ Aguardando cálculo...")
        self.lblStatusVelocidade.setStyleSheet("")
        self.lblStatusFroude.setText("⏳ Aguardando cálculo...")
        self.lblStatusFroude.setStyleSheet("")
        self.lblStatusLamina.setText("⏳ Aguardando cálculo...")
        self.lblStatusLamina.setStyleSheet("")
        
        self.lblStatusArea.setText("⏳ Aguardando cálculo...")
        self.lblStatusArea.setStyleSheet("")
        
        self.lblInfoExutorio.setText("⏳ Aguardando cálculo...")
        self.lblInfoExutorio.setStyleSheet("")
        
        self.resultados = {}
            
    def on_camada_changed(self, index):
        """Chamado quando qualquer camada muda"""
        # Salvar seleção no projeto automaticamente
        self.salvar_selecoes_projeto()
    
    def on_bloqueio_changed(self, index):
        """Gerencia estado de bloqueio/desbloqueio dos cálculos"""
        if index == 1:  # BLOQUEADO
            self.calculo_bloqueado = True
            # Salvar dados originais para preservar durante bloqueio
            self.dados_originais_bloqueados = self._coletar_todos_dados()
            # Desabilitar botão de gravar
            self.btnGravarCalculos.setEnabled(False)
            self.btnGravarCalculos.setStyleSheet("""
                QPushButton {
                    background-color: #9E9E9E;
                    color: white;
                    font-weight: bold;
                    padding: 5px 10px;
                    border-radius: 4px;
                }
            """)
            self.lblInfoStatus.setText(
                "<b>Status:</b> 🔒 Cálculo BLOQUEADO. Alterações são apenas para simulação e não serão salvas."
            )
            self.lblInfoStatus.setStyleSheet("color: #FF5722;")
        else:  # DESBLOQUEADO
            self.calculo_bloqueado = False
            # Restaurar dados originais
            if self.dados_originais_bloqueados:
                self._restaurar_dados(self.dados_originais_bloqueados)
            self.dados_originais_bloqueados = {}
            # Habilitar botão de gravar
            self.btnGravarCalculos.setEnabled(True)
            self.btnGravarCalculos.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    padding: 5px 10px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #388E3C;
                }
            """)
            self.lblInfoStatus.setText(
                "<b>Status:</b> 🔓 Desbloqueado. Alterações podem ser salvas."
            )
            self.lblInfoStatus.setStyleSheet("color: green;")
        
        # Salvar estado de bloqueio
        PersistenceManager.save_lock_state(self.calculo_bloqueado, self.dados_originais_bloqueados)

    def _filtrar_resultados_impermeabilidade(self, dados):
        """Filtra dicionário de resultados de impermeabilidade para ser serializável"""
        if not dados or not isinstance(dados, dict):
            return None
            
        # Chaves para manter (scallars e strings)
        chaves_manter = [
            'coeficiente', 'percentual', 'total_pixels', 
            'impermeable_pixels', 'vegetation_pixels', 'shadow_pixels',
            'percent_vegetation', 'percent_shadow',
            'impermeabilidade_imagem', 'impermeabilidade_relatorio',
            'impermeabilidade_imagem_original'
        ]
        
        resultado = {}
        for k in chaves_manter:
            if k in dados:
                resultado[k] = dados[k]
        
        return resultado

    def _salvar_resultados_impermeabilidade_em_disco(self):
        """Salva as imagens e relatório de impermeabilidade em disco para persistência"""
        if not self.resultados or 'impermeabilidade_dados' not in self.resultados:
            return None, None
            
        try:
            # Criar diretório para salvar resultados
            projeto = QgsProject.instance()
            projeto_path = projeto.fileName()
            
            if projeto_path:
                # Salvar na mesma pasta do projeto
                output_dir = os.path.dirname(projeto_path)
                output_subdir = os.path.join(output_dir, "impermeabilidade_resultados")
            else:
                # Salvar em diretório temporário se projeto não foi salvo
                import tempfile
                output_subdir = os.path.join(tempfile.gettempdir(), "metodo_racional_pro", "impermeabilidade_resultados")
            
            # Criar diretório se não existir
            os.makedirs(output_subdir, exist_ok=True)
            
            # Usar funções do módulo QGIS nativo para salvar
            from ..processamento.impermeabilidade_qgis import (
                salvar_imagem_original,
                salvar_imagem_classificacao_simples,
                salvar_relatorio_txt_simples
            )
            
            dados_imper = self.resultados['impermeabilidade_dados']
            
            # 1. Salvar Imagem Original
            imagem_orig_path = salvar_imagem_original(
                dados_imper['rgb_image'], 
                dados_imper['valid_mask'], 
                output_subdir
            )
            
            # 2. Salvar Imagem Classificada
            imagem_path = salvar_imagem_classificacao_simples(
                dados_imper['rgb_image'], 
                dados_imper['classification_map'], 
                dados_imper['valid_mask'], 
                output_subdir
            )
            
            # 3. Salvar Relatório TXT
            relatorio_path = salvar_relatorio_txt_simples(dados_imper, output_subdir)
            
            # Atualizar caminhos no dicionário para que sejam persistidos
            if imagem_path: dados_imper['impermeabilidade_imagem'] = imagem_path
            if imagem_orig_path: dados_imper['impermeabilidade_imagem_original'] = imagem_orig_path
            if relatorio_path: dados_imper['impermeabilidade_relatorio'] = relatorio_path
            
            return imagem_path, relatorio_path
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Erro ao salvar resultados de impermeabilidade em disco: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)
            return None, None

    def _coletar_todos_dados(self):
        """Coleta todos os dados do formulário para salvar"""
        # Buscar dados de Tc que foram salvos por abrir_dialog_tc
        dados_tc = self.resultados.get('dados_entrada', {})
        
        result = {
            'distancia': self.txtDistancia.text(),
            'desnivel': self.txtDesnivel.text(),
            'tempo': self.txtTempo.text(),
            'area': self.txtArea.text(),
            'impermeabilidade': self.txtImpermeabilidade.text(),
            'rugosidade': self.txtRugosidade.text(),
            'declividade': self.txtDeclividade.text(),
            'intensidade': self.txtIntensidade.text(),
            'diametro': self.txtDiametro.text(),
            'vazao': self.txtVazao.text(),
            'velocidade': self.txtVelocidade.text(),
            'galeria': self.txtGaleria.text(),
            'area_secao': self.txtAreaSecao.text() if hasattr(self, 'txtAreaSecao') else '',
            'froude': self.resultados.get('froude', ''),
            'lamina': self.resultados.get('lamina', ''),
            'tempo_retorno': self.txtTempoRetorno.text(),
            'cidade_idf': self.txtCidadeIDF.text(),
            # Nomes das camadas
            'camada_mdt': self.cmbMDT.currentText() if self.cmbMDT.currentIndex() > 0 else '',
            'camada_area': self.cmbAreaEstudo.currentText() if self.cmbAreaEstudo.currentIndex() > 0 else '',
            'camada_imagem': self.cmbImagem.currentText() if self.cmbImagem.currentIndex() > 0 else '',
            'camada_curvas': self.cmbCurvasNivel.currentText() if self.cmbCurvasNivel.currentIndex() > 0 else '',
            'camada_cursos': self.cmbCursosAgua.currentText() if self.cmbCursosAgua.currentIndex() > 0 else '',
            'camada_exutorio': self.cmbExutorio.currentText() if self.cmbExutorio.currentIndex() > 0 else '',
            # Dados do Exutório para recuperação
            'exutorio_ponto': self.resultados.get('exutorio_ponto', None),
            'exutorio_cota': self.resultados.get('exutorio_cota', None),
            # Dados de Impermeabilidade filtrados (sem numpy arrays)
            'impermeabilidade_dados': self._filtrar_resultados_impermeabilidade(self.resultados.get('impermeabilidade_dados')),
            # Dados de Tc previamente capturados por abrir_dialog_tc
            'metodo_tc': dados_tc.get('metodo_tc', 'manual'),
            'tabela_tc': dados_tc.get('tabela_tc', []),
            'parametros_tc_full': dados_tc.get('parametros_tc_full', {}),
        }
        return result
    
    def _restaurar_dados(self, dados):
        """Restaura dados do formulário"""
        if not dados:
            return
            
        # Bloquear sinais para evitar recursão ao atualizar combos
        self.cmbMDT.blockSignals(True)
        self.cmbAreaEstudo.blockSignals(True)
        self.cmbImagem.blockSignals(True)
        self.cmbCurvasNivel.blockSignals(True)
        self.cmbCursosAgua.blockSignals(True)
        self.cmbExutorio.blockSignals(True)
        # self.txtTempoRetorno.blockSignals(True)
        # self.txtCidadeIDF.blockSignals(True)
        
        try:
            self.txtDistancia.setText(dados.get('distancia', ''))
            self.txtDesnivel.setText(dados.get('desnivel', ''))
            self.txtTempo.setText(dados.get('tempo', ''))
            self.txtArea.setText(dados.get('area', ''))
            self.txtImpermeabilidade.setText(dados.get('impermeabilidade', ''))
            self.txtRugosidade.setText(dados.get('rugosidade', '0.013'))
            self.txtDeclividade.setText(dados.get('declividade', '0.5'))
            self.txtIntensidade.setText(dados.get('intensidade', ''))
            self.txtDiametro.setText(dados.get('diametro', ''))
            self.txtVazao.setText(dados.get('vazao', ''))
            self.txtVelocidade.setText(dados.get('velocidade', ''))
            self.txtGaleria.setText(dados.get('galeria', ''))
            if hasattr(self, 'txtAreaSecao'): self.txtAreaSecao.setText(dados.get('area_secao', ''))
            
            if 'tempo_retorno' in dados:
                self.txtTempoRetorno.setText(dados['tempo_retorno'])
            elif 'tr_index' in dados:
                # Fallback para dados antigos se necessário, mas como mudamos a UI...
                pass
                
            if 'cidade_idf' in dados:
                self.txtCidadeIDF.setText(dados['cidade_idf'])
            elif 'cidade_index' in dados:
                pass
                
            # Camadas são restauradas globalmente por carregar_selecoes_projeto
            # para evitar conflitos ao trocar de feição no mesmo projeto
                
            # Restaurar resultados para as verificações técnicas
            try:
                self.resultados = {
                    'vazao': float(dados.get('vazao')) if dados.get('vazao') else 0,
                    'diametro': float(dados.get('diametro')) if dados.get('diametro') else 0,
                    'velocidade': float(dados.get('velocidade')) if dados.get('velocidade') else 0,
                    'froude': float(dados.get('froude')) if dados.get('froude') else 0,
                    'lamina': float(dados.get('lamina')) if dados.get('lamina') else 0.85,
                    'exutorio_cota': dados.get('exutorio_cota'),
                    'exutorio_ponto': dados.get('exutorio_ponto'),
                    'impermeabilidade_dados': dados.get('impermeabilidade_dados'),
                    'dados_entrada': {
                        'area': float(dados.get('area')) if dados.get('area') else 0,
                        'distancia': float(dados.get('distancia')) if dados.get('distancia') else 0,
                        'desnivel': float(dados.get('desnivel')) if dados.get('desnivel') else 0,
                    }
                }
                
                # Habilitar botão de impermeabilidade se houver dados
                has_imper = self.resultados.get('impermeabilidade_dados') is not None
                if hasattr(self, 'btnVisualizarImper'):
                    self.btnVisualizarImper.setEnabled(has_imper)
                
                if self.resultados.get('vazao', 0) > 0 or self.resultados.get('exutorio_cota') is not None:
                    self.atualizar_status_verificacoes()
                else:
                    # Garantir que se não houver cálculo nem exutório, os status fiquem em espera
                    self.lblStatusVelocidade.setText("⏳ Aguardando cálculo...")
                    self.lblStatusVelocidade.setStyleSheet("")
                    self.lblStatusFroude.setText("⏳ Aguardando cálculo...")
                    self.lblStatusFroude.setStyleSheet("")
                    self.lblStatusLamina.setText("⏳ Aguardando cálculo...")
                    self.lblStatusLamina.setStyleSheet("")
                    self.lblStatusArea.setText("⏳ Aguardando cálculo...")
                    self.lblStatusArea.setStyleSheet("")
                    self.lblInfoExutorio.setText("⏳ Aguardando cálculo...")
                    self.lblInfoExutorio.setStyleSheet("")
            except:
                pass
        finally:
            self.cmbMDT.blockSignals(False)
            self.cmbAreaEstudo.blockSignals(False)
            self.cmbImagem.blockSignals(False)
            self.cmbCurvasNivel.blockSignals(False)
            self.cmbCursosAgua.blockSignals(False)
            self.cmbExutorio.blockSignals(False)
            # QLineEdit não precisa de blockSignals aqui
            # self.txtTempoRetorno.blockSignals(False)
            # self.txtCidadeIDF.blockSignals(False)
    
    def carregar_estado_persistido(self):
        """Carrega estado salvo do projeto QGIS"""
        try:
            # Guardar índice antes para verificar mudança
            idx_antes = self.cmbAreaEstudo.currentIndex()
            
            # Carregar estado do dialog principal
            state = PersistenceManager.load_main_dialog_state()
            if state:
                self._restaurar_dados(state)
            
            # Se a área de estudo mudou durante a restauração (e sinais estavam bloqueados),
            # precisamos atualizar o listener manualmente
            idx_depois = self.cmbAreaEstudo.currentIndex()
            if idx_depois != idx_antes and idx_depois > 0:
                self.on_area_estudo_changed(idx_depois)
            
            # Carregar estado de bloqueio
            is_locked, original_data = PersistenceManager.load_lock_state()
            if is_locked:
                self.calculo_bloqueado = True
                self.dados_originais_bloqueados = original_data or {}
                self.cmbBloqueio.setCurrentIndex(1)
        except Exception as e:
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"Erro ao carregar estado persistido: {str(e)}",
                'MetodoRacionalPro',
                Qgis.Warning
            )
    
    def salvar_estado_formulario(self):
        """Salva estado atual do formulário no projeto"""
        if self.calculo_bloqueado:
            # Não salvar se estiver bloqueado (modo simulação)
            return
        
        dados = self._coletar_todos_dados()
        
        # Salvar estado global (último usado)
        PersistenceManager.save_main_dialog_state(dados)
        
        # Salvar específico da feição
        layer = self.cmbAreaEstudo.currentData()
        if layer:
            feature_id = PersistenceManager.get_current_feature_id(layer)
            if feature_id:
                PersistenceManager.save_feature_data(feature_id, layer.name(), dados)

        
    def atualizar_info_selecao(self):
        """Atualiza informações sobre a seleção atual"""
        layer = self.cmbAreaEstudo.currentData()
        if layer is None:
            self.lblInfoStatus.setText(
                "<b>Status:</b> Selecione uma camada de área de estudo."
            )
            return
            
        # Verificar se há feições selecionadas
        selected_count = layer.selectedFeatureCount()
        total_count = layer.featureCount()
        
        if selected_count > 0:
            self.lblInfoStatus.setText(
                f"<b>Status:</b> {selected_count} feição(ões) selecionada(s) de {total_count} total. "
                f"Clique em 'EXTRAIR PARÂMETROS' para calcular."
            )
        else:
            self.lblInfoStatus.setText(
                f"<b>Status:</b> Nenhuma feição selecionada. Serão usadas todas as {total_count} feições. "
                f"Selecione feições específicas no mapa ou clique em 'EXTRAIR PARÂMETROS'."
            )
            
    def extrair_parametros_automaticos(self):
        """Extrai parâmetros automaticamente das camadas selecionadas"""
        
        # Check if the panel is visible before extracting data
        if not self.isVisible():
            return
            
        try:
            self.setCursor(Qt.CursorShape.WaitCursor)
            
            # Obter camada de área de estudo
            layer_area = self.cmbAreaEstudo.currentData()
            if layer_area is None:
                QMessageBox.warning(
                    self, "Atenção",
                    "Selecione uma camada de Área de Estudo."
                )
                return
            
            # VERIFICAÇÃO DE SELEÇÃO: O sistema deve verificar se tem alguma área selecionada
            if layer_area.selectedFeatureCount() == 0:
                self.iface.messageBar().pushMessage(
                    "Aviso", 
                    "Por favor, selecione no mínimo uma área (polígono) no mapa para realizar o cálculo automático.",
                    level=Qgis.Warning, duration=3
                )
                return

                
            # Obter geometria da área (selecionada ou todas)
            geometria_area = self.obter_geometria_area(layer_area)
            if geometria_area is None or geometria_area.isEmpty():
                QMessageBox.warning(
                    self, "Atenção",
                    "Não foi possível obter a geometria da área de estudo."
                )
                return
                
            self.area_selecionada = geometria_area
            
            # 1. Calcular ÁREA
            area_m2 = geometria_area.area()
            area_km2 = area_m2 / 1_000_000
            self.txtArea.setText(f"{area_km2:.6f}")
            
            # 2. Calcular DISTÂNCIA (talvegue ou maior reta inscrita)
            distancia = self.calcular_distancia(geometria_area)
            if distancia > 0:
                self.txtDistancia.setText(f"{distancia:.2f}")
                
            # 3. Calcular DESNÍVEL (prioridade: MDT > Curvas de Nível > Manual)
            layer_mdt = self.cmbMDT.currentData()
            layer_curvas = self.cmbCurvasNivel.currentData()
            
            if layer_mdt:
                # Usar MDT como fonte primária
                desnivel = self.calcular_desnivel_mdt(layer_mdt, geometria_area)
                if desnivel > 0:
                    self.txtDesnivel.setText(f"{desnivel:.2f}")
            elif layer_curvas:
                # Fallback: usar curvas de nível
                desnivel = self.calcular_desnivel_curvas_nivel(layer_curvas, geometria_area)
                if desnivel > 0:
                    self.txtDesnivel.setText(f"{desnivel:.2f}")
            # Se nenhum disponível, manter campo vazio para entrada manual
                    
            # 4. Calcular IMPERMEABILIDADE da imagem raster (usa módulo nativo QGIS)
            layer_imagem = self.cmbImagem.currentData()
            if layer_imagem:
                try:
                    source_crs = layer_area.crs()
                    
                    # Calcular usando módulo nativo QGIS (suporta XYZ Tiles, WMS, etc.)
                    resultado_imagem = calcular_impermeabilidade_qgis(
                        layer_imagem, geometria_area, 
                        source_crs=source_crs
                    )
                    
                    if resultado_imagem is not None:
                        # Armazenar resultados detalhados para uso posterior
                        if 'impermeabilidade_dados' not in self.resultados:
                            self.resultados['impermeabilidade_dados'] = {}
                        self.resultados['impermeabilidade_dados'] = resultado_imagem
                        
                        # Exibir coeficiente no campo
                        coef = resultado_imagem['coeficiente']
                        if coef >= 0:  # Aceitar zero como valor válido
                            self.txtImpermeabilidade.setText(f"{coef:.4f}")
                            
                            # Log de informação detalhada
                            QgsMessageLog.logMessage(
                                f"Impermeabilidade calculada: {resultado_imagem['percentual']:.2f}% "
                                f"(Vegetação: {resultado_imagem['percent_vegetation']:.2f}%, "
                                f"Sombra: {resultado_imagem['percent_shadow']:.2f}%)",
                                'MetodoRacionalPro',
                                Qgis.Info
                            )
                            
                            if hasattr(self, 'btnVisualizarImper'):
                                self.btnVisualizarImper.setEnabled(True)
                                
                            # NOVO: Salvar em disco IMEDIATAMENTE para persistir entre seleções
                            self._salvar_resultados_impermeabilidade_em_disco()
                            self.salvar_estado_formulario()
                    else:
                        # Caso a área não sobreponha a imagem
                        QMessageBox.warning(
                            self, "Aviso", 
                            "A área de estudo não parece sobrepor a imagem selecionada ou não contém pixels válidos."
                        )
                        if hasattr(self, 'btnVisualizarImper'):
                            self.btnVisualizarImper.setEnabled(False)
                except Exception as e:
                    import traceback
                    QgsMessageLog.logMessage(
                        f"Erro ao calcular impermeabilidade: {str(e)}\n{traceback.format_exc()}",
                        'MetodoRacionalPro',
                        Qgis.Warning
                    )
                    self.iface.messageBar().pushMessage(
                        "Erro", f"Falha no cálculo de impermeabilidade: {str(e)}",
                        level=Qgis.Warning, duration=5
                    )
            
            # 5. Salvar metadados das camadas selecionadas para documentação
            camadas_usadas = {}
            if self.cmbAreaEstudo.currentText():
                camadas_usadas['Área de Estudo'] = self.cmbAreaEstudo.currentText()
            if self.cmbMDT.currentText() and self.txtDesnivel.text() and layer_mdt:
                camadas_usadas['MDT'] = self.cmbMDT.currentText()
            elif self.cmbCurvasNivel.currentText() and self.txtDesnivel.text() and layer_curvas:
                camadas_usadas['Curvas de Nível'] = self.cmbCurvasNivel.currentText()
            if self.cmbImagem.currentText() and layer_imagem:
                camadas_usadas['Imagem (Impermeabilidade)'] = self.cmbImagem.currentText()
            if self.cmbCursosAgua.currentText():
                camadas_usadas["Cursos d'água"] = self.cmbCursosAgua.currentText()
                
            self.resultados['camadas_usadas'] = camadas_usadas
            
            # Atualizar status
            self.lblInfoStatus.setText(
                f"<b>Status:</b> ✓ Parâmetros extraídos com sucesso! "
                    )
                    
            # 5. Calcular TEMPO DE CONCENTRAÇÃO
            self.calcular_tempo_concentracao()
            
            # 6. Identificar EXUTÓRIO (prioridade: MDT > Curvas de Nível)
            ponto_baixo = None
            cota_baixa = None
            
            if layer_mdt:
                ponto_baixo, cota_baixa = self.encontrar_ponto_baixo_mdt(layer_mdt, geometria_area)
            
            # Se não encontrou no MDT ou não tinha MDT, tenta Curvas de Nível
            if not ponto_baixo and layer_curvas:
                ponto_baixo, cota_baixa = self.encontrar_ponto_baixo_curvas_nivel(layer_curvas, geometria_area)
            
            if ponto_baixo:
                # Armazenar ponto (sempre no CRS da Área de Estudo para consistência)
                self.resultados['exutorio_ponto'] = {'x': ponto_baixo.x(), 'y': ponto_baixo.y()}
                self.resultados['exutorio_cota'] = cota_baixa
                QgsMessageLog.logMessage(f"Exutório identificado: Z={cota_baixa:.2f}", 'MetodoRacionalPro', Qgis.Info)
            
            # Garantir que a área está nos resultados para atualizar o indicador técnico
            if 'dados_entrada' not in self.resultados:
                self.resultados['dados_entrada'] = {}
            self.resultados['dados_entrada']['area'] = area_km2
                    
            # Atualizar toda a seção de verificações técnicas (Exutório, Área, etc.)
            self.atualizar_status_verificacoes()
            
            # Auto-salvar estado após extração
            self.salvar_estado_formulario()
            
            # Atualizar status
            self.lblInfoStatus.setText(
                f"<b>Status:</b> ✓ Parâmetros extraídos com sucesso! "
                f"Área: {area_km2:.4f} km². Verifique os valores e clique em CALCULAR."
            )
            self.lblInfoStatus.setStyleSheet("color: green;")
            
            self.iface.messageBar().pushMessage(
                "Sucesso",
                "Parâmetros extraídos automaticamente!",
                level=Qgis.Success,
                duration=3
            )
            
        except Exception as e:
            QMessageBox.critical(
                self, "Erro",
                f"Erro ao extrair parâmetros: {str(e)}"
            )
            QgsMessageLog.logMessage(
                f"Erro ao extrair parâmetros: {str(e)}",
                'MetodoRacionalPro',
                Qgis.Critical
            )
        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            # Resetar barra de progresso se houver (opcional, dependendo da UI)
            self.iface.messageBar().clearWidgets()
            
    def visualizar_detalhes_impermeabilidade(self):
        """Abre caixa de diálogo com os detalhes da impermeabilização"""
        if 'impermeabilidade_dados' not in self.resultados:
            QMessageBox.warning(self, "Aviso", "Nenhum dado de impermeabilidade disponível. Execute a extração de parâmetros primeiro.")
            return
            
        dialog = DetalhesImpermeabilidadeDialog(self.resultados['impermeabilidade_dados'], self)
        dialog.exec_()

    def obter_geometria_area(self, layer):
        """
        Obtém a geometria da área de estudo de forma otimizada.
        Usa unaryUnion para processamento nativo rápido.
        """
        geometrias = []
        
        # Obter feições (selecionadas ou todas)
        features = layer.selectedFeatures() if layer.selectedFeatureCount() > 0 else layer.getFeatures()
        
        for feature in features:
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                geometrias.append(geom)
                    
        if not geometrias:
            return None
            
        if len(geometrias) == 1:
            return geometrias[0]
        
        # Otimização: Usar unaryUnion (mais rápido para muitos polígonos)
        try:
            return QgsGeometry.unaryUnion(geometrias)
        except:
            # Fallback seguro
            resultado = geometrias[0]
            for geom in geometrias[1:]:
                resultado = resultado.combine(geom)
            return resultado
            
    def calcular_distancia(self, geometria_area):
        """
        Calcula a distância do talvegue.
        Prioridade:
        1. Curso d'água selecionado/dentro da área
        2. Maior reta inscrita no polígono
        """
        # Tentar usar curso d'água
        layer_cursos = self.cmbCursosAgua.currentData()
        if layer_cursos:
            distancia_curso = self.calcular_distancia_curso_agua(layer_cursos, geometria_area)
            if distancia_curso > 0:
                return distancia_curso
                
        # Fallback: calcular maior reta inscrita
        return self.calcular_maior_reta_inscrita(geometria_area)
        
    def calcular_distancia_curso_agua(self, layer_cursos, geometria_area):
        """
        Calcula distância usando curso d'água.
        Otimizado com FilterRect para evitar ler toda a camada.
        """
        comprimento_total = 0
        bbox = geometria_area.boundingBox()
        
        # Usar request com filtro espacial (MUITO mais rápido em camadas grandes)
        request = QgsFeatureRequest().setFilterRect(bbox)
        
        # Se houver seleção, filtrar nela. Caso contrário, usar o request espacial.
        if layer_cursos.selectedFeatureCount() > 0:
            features = layer_cursos.selectedFeatures()
        else:
            features = layer_cursos.getFeatures(request)
            
        for feature in features:
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                # Teste rápido de interseção antes de fazer o clip (intersection) caro
                if geom.intersects(geometria_area):
                    geom_clip = geom.intersection(geometria_area)
                    if geom_clip and not geom_clip.isEmpty():
                        comprimento_total += geom_clip.length()
                            
        return comprimento_total
        
    def calcular_maior_reta_inscrita(self, geometria_area):
        """
        Calcula a maior reta que pode ser inscrita no polígono.
        Otimizado com simplificação de geometria e amostragem de vértices.
        """
        if geometria_area.isEmpty():
            return 0
            
        bbox = geometria_area.boundingBox()
        
        # Simplificar geometria para acelerar cálculos (tolerância baseada no tamanho)
        # 1% da maior dimensão do bounding box
        tolerancia = max(bbox.width(), bbox.height()) * 0.01
        geom_simplificada = geometria_area.simplify(tolerancia)
        if geom_simplificada is None or geom_simplificada.isEmpty():
            geom_simplificada = geometria_area
            
        # Obter vértices
        vertices = []
        if geom_simplificada.isMultipart():
            for part in geom_simplificada.asMultiPolygon():
                for ring in part: vertices.extend(ring)
        else:
            polygon = geom_simplificada.asPolygon()
            if polygon:
                for ring in polygon: vertices.extend(ring)
                    
        if len(vertices) < 2:
            return math.sqrt(bbox.width()**2 + bbox.height()**2) * 0.7
            
        # Limitar número de vértices para no máximo 50 para evitar O(N²) lento
        if len(vertices) > 50:
            step = len(vertices) // 50
            vertices_amostra = vertices[::step][:50]
        else:
            vertices_amostra = vertices
            
        maior_distancia = 0
        for i, p1 in enumerate(vertices_amostra):
            for p2 in vertices_amostra[i+1:]:
                # Teste rápido de distância Euclidiana antes do teste espacial caro
                dist_sq = (p2.x() - p1.x())**2 + (p2.y() - p1.y())**2
                if dist_sq <= maior_distancia**2:
                    continue
                    
                linha = QgsGeometry.fromPolylineXY([p1, p2])
                # Checagem espacial simplificada
                if geometria_area.contains(linha) or linha.within(geometria_area):
                    maior_distancia = math.sqrt(dist_sq)
                        
        if maior_distancia == 0:
            maior_distancia = math.sqrt(bbox.width()**2 + bbox.height()**2) * 0.6
            
        return maior_distancia
        
    def calcular_desnivel_mdt(self, layer_mdt, geometria_area):
        """
        Calcula o desnível do MDT de forma eficiente.
        Usa estatísticas de banda para aproximação e amostragem esparsa.
        """
        try:
            bbox = geometria_area.boundingBox()
            provider = layer_mdt.dataProvider()
            
            # Passo 1: Usar as estatísticas nativas do QGIS para o bounding box
            # Isso é muito rápido e serve como uma excelente aproximação ou base
            stats = provider.bandStatistics(1, QgsRasterBandStats.All, bbox)
            
            # Se a área for pequena ou o polígono cobrir quase todo o bbox, usamos isso
            ratio = geometria_area.area() / bbox.area()
            if ratio > 0.8:
                return stats.maximumValue - stats.minimumValue
            
            # Passo 2: Amostragem esparsa apenas se necessário (polígono irregular)
            # Definir amostragem de no máximo 400 pontos (20x20)
            nx, ny = 20, 20
            dx = bbox.width() / nx
            dy = bbox.height() / ny
            
            alt_min = float('inf')
            alt_max = float('-inf')
            pontos_validos = 0
            
            for i in range(nx + 1):
                x = bbox.xMinimum() + i * dx
                for j in range(ny + 1):
                    y = bbox.yMinimum() + j * dy
                    ponto = QgsPointXY(x, y)
                    # Checagem rápida de bounding box antes do contains caro
                    if geometria_area.contains(QgsGeometry.fromPointXY(ponto)):
                        result = provider.sample(ponto, 1)
                        if result[1]:
                            valor = result[0]
                            if valor != provider.sourceNoDataValue(1):
                                alt_min = min(alt_min, valor)
                                alt_max = max(alt_max, valor)
                                pontos_validos += 1
            
            if pontos_validos < 5:
                return stats.maximumValue - stats.minimumValue
                
            return alt_max - alt_min
            
        except Exception as e:
            return 0
    
    def calcular_desnivel_curvas_nivel(self, layer_curvas, geometria_area):
        """
        Calcula o desnível usando curvas de nível vetoriais com suporte a CRS.
        """
        try:
            # Gerenciar sistemas de coordenadas (CRS)
            layer_area = self.cmbAreaEstudo.currentData()
            if layer_area and layer_area.crs() != layer_curvas.crs():
                transform = QgsCoordinateTransform(layer_area.crs(), layer_curvas.crs(), QgsProject.instance())
                geometria_proj = QgsGeometry(geometria_area)
                geometria_proj.transform(transform)
                bbox = geometria_proj.boundingBox()
                geometria_final = geometria_proj
            else:
                bbox = geometria_area.boundingBox()
                geometria_final = geometria_area

            # Campos comuns que podem conter a elevação
            campos_elevacao = ['ELEVATION', 'ELEV', 'Z', 'COTA', 'ALTITUDE', 
                               'NIVEL', 'HEIGHT', 'ALT', 'CONTOUR', 'CURVA',
                               'elevation', 'elev', 'z', 'cota', 'altitude',
                               'nivel', 'height', 'alt', 'contour', 'curva']
            
            campo_elev = None
            fields = layer_curvas.fields()
            for field in fields:
                if field.name() in campos_elevacao:
                    campo_elev = field.name()
                    break
            
            if campo_elev is None:
                for field in fields:
                    nome_lower = field.name().lower()
                    if any(key in nome_lower for key in ['elev', 'cota', 'alt', 'z', 'nivel', 'height']):
                        campo_elev = field.name()
                        break
            
            if campo_elev is None:
                return 0
            
            request = QgsFeatureRequest().setFilterRect(bbox)
            alt_min = float('inf')
            alt_max = float('-inf')
            curvas_validas = 0
            
            for feature in layer_curvas.getFeatures(request):
                geom = feature.geometry()
                if geom and not geom.isEmpty():
                    if geom.intersects(geometria_final):
                        try:
                            valor = float(feature[campo_elev])
                            alt_min = min(alt_min, valor)
                            alt_max = max(alt_max, valor)
                            curvas_validas += 1
                        except (TypeError, ValueError):
                            continue
            
            if curvas_validas == 0:
                return 0
                
            desnivel = alt_max - alt_min
            QgsMessageLog.logMessage(
                f"Desnível curvas: {desnivel:.2f}m ({curvas_validas} curvas)",
                'MetodoRacionalPro',
                Qgis.Info
            )
            return desnivel
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Erro ao calcular desnível: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)
            return 0
            
    def calcular_impermeabilidade(self, layer_uso, geometria_area):
        """
        Calcula o coeficiente de impermeabilidade ponderado pela área.
        Baseado na interseção do uso do solo com a área de estudo.
        """
        try:
            # Tabela de coeficientes de escoamento por tipo de uso
            # Pode ser ajustada conforme necessidade
            coef_padrao = {
                # Palavras-chave e seus coeficientes
                'urbano': 0.85,
                'impermeavel': 0.95,
                'asfalto': 0.95,
                'concreto': 0.95,
                'telhado': 0.90,
                'comercial': 0.85,
                'industrial': 0.85,
                'residencial': 0.65,
                'gramado': 0.25,
                'jardim': 0.25,
                'parque': 0.20,
                'floresta': 0.15,
                'mata': 0.15,
                'vegetacao': 0.20,
                'agricultura': 0.40,
                'cultivo': 0.40,
                'pastagem': 0.35,
                'pasto': 0.35,
                'solo_exposto': 0.60,
                'agua': 1.00,
                'rio': 1.00,
                'lago': 1.00,
            }
            
            area_total = geometria_area.area()
            if area_total <= 0:
                return 0.5  # Valor padrão
                
            soma_ponderada = 0
            area_coberta = 0
            
            # Otimização: Cache de campos para evitar busca por string em cada loop
            fields = layer_uso.fields()
            campo_coef_idx = -1
            campos_tipo_idx = []
            
            for i, field in enumerate(fields):
                nome = field.name().lower()
                if any(k in nome for k in ['coef', 'c_', 'impermeab', 'runoff', 'cn']):
                    campo_coef_idx = i
                    break
            
            if campo_coef_idx == -1:
                for i, field in enumerate(fields):
                    nome = field.name().lower()
                    if any(k in nome for k in ['tipo', 'uso', 'class', 'descr', 'nome']):
                        campos_tipo_idx.append(i)

            # Iterar apenas sobre feições dentro do bounding box da bacia
            request = QgsFeatureRequest().setFilterRect(geometria_area.boundingBox())
            
            # Permitir que a interface respire (não trave)
            from qgis.PyQt.QtCore import QCoreApplication
            QCoreApplication.processEvents()
            
            for feature in layer_uso.getFeatures(request):
                geom = feature.geometry()
                if geom and not geom.isEmpty():
                    if geom.intersects(geometria_area):
                        intersecao = geom.intersection(geometria_area)
                        if intersecao and not intersecao.isEmpty():
                            area_inter = intersecao.area()
                            coef = None
                            
                            # Usar índices de campo pré-calculados
                            if campo_coef_idx != -1:
                                try:
                                    coef = float(feature[campo_coef_idx])
                                    if coef > 1: coef = coef / 100
                                except: pass
                                        
                            if coef is None and campos_tipo_idx:
                                for idx in campos_tipo_idx:
                                    try:
                                        valor = str(feature[idx]).lower()
                                        for chave, c in coef_padrao.items():
                                            if chave in valor:
                                                coef = c
                                                break
                                    except: pass
                                    if coef: break
                                        
                            if coef is None: coef = 0.5
                                
                            soma_ponderada += coef * area_inter
                            area_coberta += area_inter
                            
            if area_coberta > 0:
                return soma_ponderada / area_coberta
                
            return 0
        except Exception as e:
            QgsMessageLog.logMessage(f"Erro C: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)
            return 0

    def encontrar_ponto_baixo_mdt(self, layer_mdt, geometria_area):
        """
        Encontra o ponto de menor cota dentro da área usando o MDT.
        Retorna (QgsPointXY, altitude) ou (None, None).
        """
        try:
            bbox = geometria_area.boundingBox()
            provider = layer_mdt.dataProvider()
            
            # Definir passo de amostragem (resolução do raster ou grade fixa)
            # Para performance, vamos usar uma grade de até 100x100 pontos
            # ou a resolução nativa, o que for maior (menos pontos)
            cols = provider.xSize()
            rows = provider.ySize()
            
            # Transformar bbox para coordenadas do raster (se necessário) seria complexo
            # Vamos simplificar: sampling regular no bbox
            
            w = bbox.width()
            h = bbox.height()
            
            # Grade de busca - aumentar a densidade para melhor precisão
            nx = 50
            ny = 50
            dx = w / nx
            dy = h / ny
            
            min_val = float('inf')
            min_ponto = None
            
            # Otimização: ler bloco de dados se possível, mas sample é mais simples de implementar agora
            # Para precisão real, o ideal seria ler o raster block, mas vamos de sample por enquanto
            # Se for muito lento, mudamos para readBlock
            
            for i in range(nx + 1):
                x = bbox.xMinimum() + i * dx
                for j in range(ny + 1):
                    y = bbox.yMinimum() + j * dy
                    ponto = QgsPointXY(x, y)
                    
                    if geometria_area.contains(QgsGeometry.fromPointXY(ponto)):
                        val, res = provider.sample(ponto, 1)
                        if res and val != provider.sourceNoDataValue(1):
                            if val < min_val:
                                min_val = val
                                min_ponto = ponto
                                
            return min_ponto, min_val
            
        except Exception as e:
            return None, None
    
    def encontrar_ponto_baixo_curvas_nivel(self, layer_curvas, geometria_area):
        """
        Encontra o ponto de menor cota dentro da área usando curvas de nível.
        Retorna (QgsPointXY, altitude) ou (None, None).
        """
        try:
            # Gerenciar sistemas de coordenadas (CRS)
            layer_area = self.cmbAreaEstudo.currentData()
            transform_back = None
            if layer_area and layer_area.crs() != layer_curvas.crs():
                transform = QgsCoordinateTransform(layer_area.crs(), layer_curvas.crs(), QgsProject.instance())
                transform_back = QgsCoordinateTransform(layer_curvas.crs(), layer_area.crs(), QgsProject.instance())
                geometria_proj = QgsGeometry(geometria_area)
                geometria_proj.transform(transform)
                bbox = geometria_proj.boundingBox()
                geometria_final = geometria_proj
            else:
                bbox = geometria_area.boundingBox()
                geometria_final = geometria_area

            fields = layer_curvas.fields()

            # === Detecção do campo de elevação (3 estratégias) ===
            campos_elevacao_exatos = [
                'ELEVATION', 'ELEV', 'Z', 'COTA', 'ALTITUDE',
                'NIVEL', 'HEIGHT', 'ALT', 'CONTOUR', 'CURVA',
                'elevation', 'elev', 'z', 'cota', 'altitude',
                'nivel', 'height', 'alt', 'contour', 'curva'
            ]
            campo_elev = None

            # Estratégia 1: nome exato
            for field in fields:
                if field.name() in campos_elevacao_exatos:
                    campo_elev = field.name()
                    break

            # Estratégia 2: substring no nome (exclui 'z' sozinho para evitar falsos positivos)
            if campo_elev is None:
                for field in fields:
                    n = field.name().lower()
                    if any(k in n for k in ['elev', 'cota', 'alt', 'nivel', 'height', 'contour']):
                        campo_elev = field.name()
                        break

            # Estratégia 3: primeiro campo numérico não-PK
            if campo_elev is None:
                pks = layer_curvas.primaryKeyAttributes()
                for i, field in enumerate(fields):
                    if i not in pks and field.type() in [2, 6]:  # 2=Int, 6=Double
                        campo_elev = field.name()
                        QgsMessageLog.logMessage(
                            f"Exutório/Curvas: campo '{campo_elev}' usado como fallback numérico "
                            f"(campos disponíveis: {[f.name() for f in fields]})",
                            'MetodoRacionalPro', Qgis.Warning
                        )
                        break

            if campo_elev is None:
                QgsMessageLog.logMessage(
                    f"Exutório/Curvas: nenhum campo de elevação detectado. "
                    f"Campos disponíveis: {[f.name() for f in fields]}",
                    'MetodoRacionalPro', Qgis.Critical
                )
                return None, None

            QgsMessageLog.logMessage(
                f"Exutório/Curvas: usando campo '{campo_elev}'",
                'MetodoRacionalPro', Qgis.Info
            )

            # === Percorrer feições e encontrar a de menor cota ===
            request = QgsFeatureRequest().setFilterRect(bbox)
            min_cota = float('inf')
            min_curva_geom = None
            n_processadas = 0

            for feature in layer_curvas.getFeatures(request):
                geom = feature.geometry()
                if not geom or geom.isEmpty():
                    continue
                if not geom.intersects(geometria_final):
                    continue
                n_processadas += 1
                try:
                    valor = feature[campo_elev]
                    if valor is None:
                        continue
                    valor = float(valor)
                    if valor < min_cota:
                        geom_clip = geom.intersection(geometria_final)
                        if geom_clip and not geom_clip.isEmpty():
                            min_cota = valor
                            min_curva_geom = geom_clip
                except (TypeError, ValueError):
                    continue

            QgsMessageLog.logMessage(
                f"Exutório/Curvas: {n_processadas} feições intersectam a área. "
                f"Cota mínima: {min_cota if min_cota != float('inf') else 'não encontrada'}",
                'MetodoRacionalPro', Qgis.Info
            )

            if min_curva_geom is None:
                QgsMessageLog.logMessage(
                    "Exutório/Curvas: nenhuma curva válida encontrada na área de estudo",
                    'MetodoRacionalPro', Qgis.Warning
                )
                return None, None

            # === Extrair ponto representativo ===
            try:
                # Tentar centróide primeiro (aceitar intersects — contains é muito restritivo para linhas)
                centroid = min_curva_geom.centroid()
                if centroid and not centroid.isEmpty():
                    ponto_c = centroid.asPoint()
                    if geometria_final.intersects(centroid) or geometria_final.contains(centroid):
                        pt_final = transform_back.transform(ponto_c) if transform_back else ponto_c
                        QgsMessageLog.logMessage(
                            f"Exutório/Curvas: ponto via centróide, Z={min_cota:.2f}",
                            'MetodoRacionalPro', Qgis.Info
                        )
                        return QgsPointXY(pt_final), min_cota

                # Fallback: primeiro vértice da linha clipada
                ponto_v = None
                if min_curva_geom.isMultipart():
                    lines = min_curva_geom.asMultiPolyline()
                    if lines and lines[0]:
                        ponto_v = lines[0][0]
                else:
                    vertices = min_curva_geom.asPolyline()
                    if vertices:
                        ponto_v = vertices[0]

                if ponto_v:
                    pt_final = transform_back.transform(ponto_v) if transform_back else ponto_v
                    QgsMessageLog.logMessage(
                        f"Exutório/Curvas: ponto via 1º vértice, Z={min_cota:.2f}",
                        'MetodoRacionalPro', Qgis.Info
                    )
                    return QgsPointXY(pt_final), min_cota

            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Exutório/Curvas: erro geométrico ao extrair ponto: {str(e)}",
                    'MetodoRacionalPro', Qgis.Warning
                )

            return None, None

        except Exception as e:
            QgsMessageLog.logMessage(
                f"Exutório/Curvas: erro crítico: {str(e)}",
                'MetodoRacionalPro', Qgis.Critical
            )
            return None, None
            
    def gravar_exutorio(self, ponto, cota):
        """
        Grava o ponto do exutório na camada selecionada.
        
        Args:
            ponto: QgsPointXY com as coordenadas do ponto mais baixo
            cota: float com a elevação/cota do ponto
        """
        layer = self.cmbExutorio.currentData()
        if not layer:
            QgsMessageLog.logMessage(
                "gravar_exutorio: Nenhuma camada de exutório selecionada",
                'MetodoRacionalPro',
                Qgis.Warning
            )
            return False
        
        try:
            # Verificar se a camada suporta adição de feições
            caps = layer.dataProvider().capabilities()
            if not (caps & QgsVectorDataProvider.AddFeatures):
                QgsMessageLog.logMessage(
                    f"gravar_exutorio: Camada '{layer.name()}' não suporta adição de feições",
                    'MetodoRacionalPro',
                    Qgis.Warning
                )
                return False
            
            # Iniciar edição
            was_editing = layer.isEditable()
            if not was_editing:
                layer.startEditing()
            
            # Gerenciar sistemas de coordenadas (CRS) para gravação
            layer_area = self.cmbAreaEstudo.currentData()
            ponto_final = ponto
            if layer_area and layer_area.crs() != layer.crs():
                transform = QgsCoordinateTransform(layer_area.crs(), layer.crs(), QgsProject.instance())
                ponto_final = transform.transform(ponto)
            
            # Criar feição baseada nos campos da camada
            feat = QgsFeature(layer.fields())
            feat.setGeometry(QgsGeometry.fromPointXY(ponto_final))
            
            # Identificar campo de cota/elevação
            idx_cota = -1
            fields = layer.fields()
            pks = layer.primaryKeyAttributes()
            
            for i, field in enumerate(fields):
                nome = field.name().lower()
                # Pular campos PK e IDs conhecidos para evitar o erro 'null value in column id'
                if i in pks or any(pk_name == nome for pk_name in ['id', 'fid', 'pk', 'objectid']):
                    continue
                
                if any(x in nome for x in ['cota', 'z', 'alt', 'elev', 'altura']):
                    idx_cota = i
                    break
            
            # Se não encontrou cota específica, usar primeiro numérico que não seja PK
            if idx_cota < 0:
                for i, field in enumerate(fields):
                    if i not in pks and field.type() in [2, 6]: # Int, Double
                        idx_cota = i
                        break
            
            # Preencher APENAS o atributo de cota.
            # O QGIS/Provedor cuidará de omitir campos PK se não forem preenchidos e tiverem default no DB.
            if idx_cota >= 0:
                feat.setAttribute(idx_cota, float(cota))
                QgsMessageLog.logMessage(
                    f"gravar_exutorio: Preenchendo atributo '{fields[idx_cota].name()}' com {cota:.2f}",
                    'MetodoRacionalPro',
                    Qgis.Info
                )
            
            # Adicionar feição via camada (gerencia IDs temporários e commits de forma mais segura)
            success = layer.addFeature(feat)
            
            if success:
                layer.commitChanges()
                layer.triggerRepaint()
                QgsMessageLog.logMessage(
                    f"gravar_exutorio: Ponto gravado com sucesso em '{layer.name()}'",
                    'MetodoRacionalPro',
                    Qgis.Info
                )
                return True
            else:
                layer.rollBack()
                QgsMessageLog.logMessage(
                    f"gravar_exutorio: Falha ao adicionar feição em '{layer.name()}'",
                    'MetodoRacionalPro',
                    Qgis.Warning
                )
                return False
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Erro ao gravar exutório: {str(e)}",
                'MetodoRacionalPro',
                Qgis.Critical
            )
            try:
                layer.rollBack()
            except:
                pass
            return False
            
    def calcular_tempo_concentracao(self):
        """
        Calcula o tempo de concentração usando método de Kirpich.
        Tc = 57 * (L³ / H)^0.385
        """
        try:
            distancia_str = self.txtDistancia.text()
            desnivel_str = self.txtDesnivel.text()
            
            if not distancia_str or not desnivel_str:
                return
                
            L = float(distancia_str)  # metros
            H = float(desnivel_str)   # metros
            
            if L <= 0 or H <= 0:
                return
                
            # Converter para km
            L_km = L / 1000
            
            # Kirpich
            Tc = 57 * ((L_km ** 3) / H) ** 0.385
            
            self.txtTempo.setText(f"{Tc:.2f}")
            
        except Exception as e:
            QgsMessageLog.logMessage(
                f"Erro ao calcular tempo de concentração: {str(e)}",
                'MetodoRacionalPro',
                Qgis.Warning
            )
            
    def abrir_dialog_tc(self):
        """Abre janela de cálculo do Tempo de Concentração"""
        try:
            from .tc_dialog import TcDialog
            
            # Obter valores atuais para passar ao dialog
            distancia = self.txtDistancia.text() if self.txtDistancia.text() else None
            desnivel = self.txtDesnivel.text() if self.txtDesnivel.text() else None
            area = self.txtArea.text() if self.txtArea.text() else None
            declividade = self.txtDeclividade.text() if self.txtDeclividade.text() else None
            
            # Abrir dialog Tc com parâmetros
            dlg = TcDialog(
                parent=self,
                distancia=distancia,
                desnivel=desnivel,
                area=area,
                declividade=declividade
            )
            
            # Se o usuário confirmar, usar o tempo calculado
            if dlg.exec_():
                tempo = dlg.get_tempo()
                if tempo:
                    self.txtTempo.setText(f"{tempo:.2f}")
                    
                # Registrar método usado para auditoria
                metodo = dlg.get_metodo()
                parametros_tc = dlg.get_parametros()
                
                # Se houver tabela de comparação, capturar
                tabela_tc = getattr(dlg, 'resultados_tabela', [])
                
                if metodo:
                    # Armazenar nos resultados para conferência futura
                    if 'dados_entrada' not in self.resultados:
                        self.resultados['dados_entrada'] = {}
                    
                    self.resultados['dados_entrada']['metodo_tc'] = metodo
                    self.resultados['dados_entrada']['tempo_concentracao'] = tempo
                    self.resultados['dados_entrada']['tabela_tc'] = tabela_tc
                    self.resultados['dados_entrada']['parametros_tc_full'] = parametros_tc
                        
                    QgsMessageLog.logMessage(
                        f"Tc calculado: {tempo:.2f} min (método: {metodo})",
                        'MetodoRacionalPro',
                        Qgis.Info
                    )
                    
                    self.iface.messageBar().pushMessage(
                        "Info",
                        f"Tempo de Concentração: {tempo:.2f} min ({metodo if metodo else 'manual'})",
                        level=Qgis.Info,
                        duration=3
                    )
            
        except Exception as e:
            QMessageBox.warning(
                self, "Erro",
                f"Erro ao abrir calculadora de Tc: {str(e)}"
            )
            
    def calcular_intensidade_idf(self):
        """Abre janela de cálculo IDF com os dados atuais"""
        try:
            from .idf_dialog import IDFDialog
            
            # Obter valores atuais para passar ao dialog
            duracao_inicial = None
            tr_inicial = None
            
            tempo_str = self.txtTempo.text()
            if tempo_str:
                try:
                    duracao_inicial = float(tempo_str)
                except:
                    pass
                    
            tr_texto = self.txtTempoRetorno.text()
            try:
                tr_inicial = int(tr_texto.split()[0])
            except:
                tr_inicial = 25
            
            # Abrir dialog IDF com parâmetros
            dlg = IDFDialog(
                parent=self,
                duracao_inicial=duracao_inicial,
                tr_inicial=tr_inicial
            )
            
            # Se o usuário confirmar, usar a intensidade calculada
            if dlg.exec_():
                intensidade = dlg.get_intensidade()
                if intensidade:
                    self.txtIntensidade.setText(f"{intensidade:.2f}")
                    
                    # Atualizar também o tempo de retorno e cidade se mudaram
                    parametros = dlg.get_parametros()
                    if parametros:
                        # Sincronizar TR
                        tr_dlg = parametros.get('TR', 25)
                        self.txtTempoRetorno.setText(f"{tr_dlg} anos")
                        
                        # Sincronizar Cidade
                        cidade_dlg = parametros.get('cidade')
                        if cidade_dlg:
                            # Se tiver o prefixo de estrela, remover
                            if cidade_dlg.startswith("⭐ "):
                                cidade_dlg = cidade_dlg[2:]
                            self.txtCidadeIDF.setText(cidade_dlg)
                                
                        # Atualizar tempo de concentração se mudou
                        duracao_dlg = parametros.get('duracao')
                        if duracao_dlg and duracao_dlg != duracao_inicial:
                            self.txtTempo.setText(f"{duracao_dlg:.2f}")
                        
                        # Salvar seleções após mudança via dialog
                        self.salvar_selecoes_projeto()
            
        except Exception as e:
            QMessageBox.warning(
                self, "Erro",
                f"Erro ao abrir calculadora IDF: {str(e)}"
            )
            
    def validar_entrada(self):
        """Valida dados de entrada"""
        campos_obrigatorios = [
            (self.txtDistancia, "Distância"),
            (self.txtDesnivel, "Desnível"),
            (self.txtTempo, "Tempo"),
            (self.txtArea, "Área"),
            (self.txtImpermeabilidade, "Impermeabilidade"),
            (self.txtRugosidade, "Rugosidade"),
            (self.txtDeclividade, "Declividade"),
        ]
        
        for campo, nome in campos_obrigatorios:
            if not campo.text():
                QMessageBox.warning(
                    self,
                    "Atenção",
                    f"Informe o campo: {nome}\n\n"
                    f"Dica: Use 'EXTRAIR PARÂMETROS' para calcular automaticamente."
                )
                campo.setFocus()
                return False
                
            try:
                valor = float(campo.text())
                if valor < 0:
                    QMessageBox.warning(
                        self,
                        "Atenção",
                        f"O campo {nome} deve ser positivo"
                    )
                    return False
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Atenção",
                    f"Valor inválido no campo: {nome}"
                )
                return False
                
        return True
        
    def coletar_dados_formulario(self):
        """Coleta dados do formulário"""
        tr_texto = self.txtTempoRetorno.text()
        tr = int(tr_texto.split()[0])
        
        intensidade = None
        if self.txtIntensidade.text():
            intensidade = float(self.txtIntensidade.text())
        
        # Obter cidade IDF para cálculo de múltiplos TRs
        cidade_idf = self.txtCidadeIDF.text().split(' - ')[0].lower().replace(' ', '_')
        
        return {
            'distancia': float(self.txtDistancia.text()),
            'desnivel': float(self.txtDesnivel.text()),
            'tempo': float(self.txtTempo.text()),
            'area': float(self.txtArea.text()),
            'impermeabilidade': float(self.txtImpermeabilidade.text()),
            'rugosidade': float(self.txtRugosidade.text()),
            'declividade': float(self.txtDeclividade.text()),
            'coef_escoamento': float(self.txtImpermeabilidade.text()),
            'intensidade': intensidade,
            'tempo_retorno': tr,
            'cidade_idf': cidade_idf
        }
        
    def executar_calculo(self):
        """Executa cálculo do Método Racional"""
        try:
            if not self.validar_entrada():
                return
                
            dados = self.coletar_dados_formulario()
            
            self.setCursor(Qt.CursorShape.WaitCursor)
            
            # Importar módulo de cálculo
            from ..hidrologia.metodo_racional import MetodoRacional
            
            metodo = MetodoRacional()
            
            # Calcular intensidade se não informada
            if not dados['intensidade']:
                from ..hidrologia.curvas_idf import CurvasIDF
                idf = CurvasIDF()
                cidade = self.txtCidadeIDF.text().split(' - ')[0].lower().replace(' ', '_')
                dados['intensidade'] = idf.calcular_intensidade(
                    cidade, 
                    dados['tempo_retorno'], 
                    dados['tempo']
                )
                self.txtIntensidade.setText(f"{dados['intensidade']:.2f}")
            
            # Calcular vazão
            Q = metodo.calcular_vazao(
                C=dados['coef_escoamento'],
                I=dados['intensidade'],
                A=dados['area']
            )
            
            # Dimensionar conduto
            resultado_dim = metodo.dimensionar_conduto(
                Q=Q,
                declividade=dados['declividade'] / 100,
                rugosidade=dados['rugosidade']
            )
            
            # Armazenar resultados (ATUALIZAR em vez de SOBRESCREVER para preservar Exutório/Área)
            # Preservar dados de Tc que foram salvos por abrir_dialog_tc
            dados_entrada_existente = self.resultados.get('dados_entrada', {})
            for tc_key in ['metodo_tc', 'tabela_tc', 'parametros_tc_full', 'tempo_concentracao']:
                if tc_key in dados_entrada_existente and tc_key not in dados:
                    dados[tc_key] = dados_entrada_existente[tc_key]
            
            resultados_novos = {
                'vazao': Q,
                'diametro': resultado_dim['diametro'],
                'velocidade': resultado_dim['velocidade'],
                'froude': resultado_dim['numero_froude'],
                'lamina': resultado_dim.get('lamina_altura', 0.85),
                'area_secao': resultado_dim.get('area_secao', 0),
                'lado_galeria': resultado_dim.get('lado_galeria', 0),
                'status': resultado_dim['status'],
                'dados_entrada': dados
            }
            
            # Preservar explicitamente dados do exutório se existirem
            ex_cota = self.resultados.get('exutorio_cota')
            ex_ponto = self.resultados.get('exutorio_ponto')
            
            self.resultados.update(resultados_novos)
            
            if ex_cota is not None:
                self.resultados['exutorio_cota'] = ex_cota
            if ex_ponto is not None:
                self.resultados['exutorio_ponto'] = ex_ponto
            
            # Exibir resultados
            self.exibir_resultados()
            
            # Alerta de área excedente aqui no fluxo de cálculo
            area = dados.get('area', 0)
            if area > 2.0:
                QMessageBox.warning(
                    self, "Aviso Técnico",
                    f"A área da bacia ({area:.2f} km²) excede o limite recomendado de 2 km² para o Método Racional.\n\n"
                    "Considere utilizar métodos para grandes bacias como I-Pai-Wu ou modelagem hidrológica."
                )
            
            self.calculo_concluido.emit(self.resultados)
            
            # Auto-salvar estado após cálculo bem-sucedido
            self.salvar_estado_formulario()
            
            self.iface.messageBar().pushMessage(
                "Sucesso",
                f"Cálculo realizado! Vazão: {Q:.2f} m³/s, Diâmetro: {resultado_dim['diametro']:.2f} m",
                level=Qgis.Success,
                duration=5
            )
            
        except Exception as e:
            self.iface.messageBar().pushMessage(
                "Erro",
                f"Erro ao calcular: {str(e)}",
                level=Qgis.Critical
            )
            QgsMessageLog.logMessage(
                f"Erro no cálculo: {str(e)}",
                'MetodoRacionalPro',
                Qgis.Critical
            )
            
        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            
    def exibir_resultados(self):
        """Exibe resultados na interface"""
        self.txtDiametro.setText(f"{self.resultados['diametro']:.2f}")
        self.txtVazao.setText(f"{self.resultados['vazao']:.2f}")
        self.txtVelocidade.setText(f"{self.resultados['velocidade']:.2f}")
        
        # Lado da galeria quadrada
        lado_galeria = self.resultados.get('lado_galeria', self.resultados['diametro'])
        self.txtGaleria.setText(f"{lado_galeria:.2f} x {lado_galeria:.2f}")
            
        if hasattr(self, 'txtAreaSecao') and 'area_secao' in self.resultados:
            self.txtAreaSecao.setText(f"{self.resultados['area_secao']:.2f}")
        
        # Atualizar verificações
        self.atualizar_status_verificacoes()
        
    def obter_diametro_comercial(self, diametro_calculado):
        """Retorna diâmetro comercial mais próximo"""
        import math
        diametros_comerciais = [
            0.30, 0.40, 0.50, 0.60, 0.80, 1.00, 1.20, 
            1.50, 1.75, 2.00, 2.50, 3.00
        ]
        for d in diametros_comerciais:
            if d >= diametro_calculado:
                return d
        
        # Para diâmetros maiores que 3.00, arredondar para o próximo múltiplo de 0.50
        return math.ceil(diametro_calculado * 2) / 2.0
        
    def atualizar_status_verificacoes(self):
        """Atualiza indicadores de verificação"""
        vazao = self.resultados.get('vazao', 0)
        velocidade = self.resultados.get('velocidade', 0)
        froude = self.resultados.get('froude', 0)
        lamina = self.resultados.get('lamina', 0)
        area = self.resultados.get('dados_entrada', {}).get('area', 0)
        
        # Verificação de velocidade (Apenas se houver cálculo)
        if vazao > 0:
            if 0.6 <= velocidade <= 5.0:
                self.lblStatusVelocidade.setText(f"✓ Velocidade adequada ({velocidade:.2f} m/s)")
                self.lblStatusVelocidade.setStyleSheet("color: green; font-weight: bold;")
            elif velocidade < 0.6:
                self.lblStatusVelocidade.setText(f"⚠ Velocidade baixa ({velocidade:.2f} m/s) - risco de sedimentação")
                self.lblStatusVelocidade.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.lblStatusVelocidade.setText(f"⚠ Velocidade alta ({velocidade:.2f} m/s) - risco de erosão")
                self.lblStatusVelocidade.setStyleSheet("color: red; font-weight: bold;")
                
            # Verificação de Froude
            if froude < 1:
                self.lblStatusFroude.setText(f"✓ Subcrítico (Fr={froude:.2f})")
                self.lblStatusFroude.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.lblStatusFroude.setText(f"⚠ Supercrítico (Fr={froude:.2f})")
                self.lblStatusFroude.setStyleSheet("color: orange; font-weight: bold;")
                
            # Verificação de lâmina
            lamina_perc = lamina * 100
            if 50 <= lamina_perc <= 85:
                self.lblStatusLamina.setText(f"✓ Lâmina d'água: {lamina_perc:.0f}%")
                self.lblStatusLamina.setStyleSheet("color: green; font-weight: bold;")
            elif lamina_perc < 50:
                self.lblStatusLamina.setText(f"ℹ Lâmina d'água: {lamina_perc:.0f}% (capacidade ociosa)")
                self.lblStatusLamina.setStyleSheet("color: blue; font-weight: bold;")
            else:
                self.lblStatusLamina.setText(f"⚠ Lâmina d'água: {lamina_perc:.0f}% (limite)")
                self.lblStatusLamina.setStyleSheet("color: orange; font-weight: bold;")
        else:
            # Resetar se não houver cálculo
            for lbl in [self.lblStatusVelocidade, self.lblStatusFroude, self.lblStatusLamina]:
                lbl.setText("⏳ Aguardando cálculo...")
                lbl.setStyleSheet("")

        # Verificação de área (Independente do cálculo de vazão)
        if area > 0:
            if area <= 2.0:
                self.lblStatusArea.setText(f"✓ Área adequada ({area:.2f} km²)")
                self.lblStatusArea.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.lblStatusArea.setText(f"⚠ Área excedente ({area:.2f} km²)")
                self.lblStatusArea.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.lblStatusArea.setText("⏳ Aguardando cálculo...")
            self.lblStatusArea.setStyleSheet("")
            
        # Verificação do Exutório (Elevada para status técnico padrão)
        exutorio_cota = self.resultados.get('exutorio_cota')
        if exutorio_cota is not None:
            self.lblInfoExutorio.setText(f"✓ Exutório: Z={exutorio_cota:.2f} m")
            self.lblInfoExutorio.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lblInfoExutorio.setText("⏳ Aguardando cálculo...")
            self.lblInfoExutorio.setStyleSheet("")
            
    def limpar_formulario(self):
        """Limpa todos os campos do formulário"""
        # Limpar campos de entrada
        self.txtDistancia.clear()
        self.txtDesnivel.clear()
        self.txtTempo.clear()
        self.txtArea.clear()
        self.txtImpermeabilidade.clear()
        self.txtIntensidade.clear()
        
        # Manter valores padrão
        self.txtRugosidade.setText("0.013")
        self.txtDeclividade.setText("0.5")
        
        # Limpar resultados
        self.txtDiametro.clear()
        self.txtVazao.clear()
        self.txtVelocidade.clear()
        self.txtGaleria.clear()
        
        # Resetar verificações
        self.lblStatusVelocidade.setText("⏳ Aguardando cálculo...")
        self.lblStatusVelocidade.setStyleSheet("")
        self.lblStatusFroude.setText("⏳ Aguardando cálculo...")
        self.lblStatusFroude.setStyleSheet("")
        self.lblStatusLamina.setText("⏳ Aguardando cálculo...")
        self.lblStatusLamina.setStyleSheet("")
        
        self.lblStatusArea.setText("⏳ Aguardando cálculo...")
        self.lblStatusArea.setStyleSheet("")

        self.lblInfoExutorio.setText("⏳ Aguardando cálculo...")
        self.lblInfoExutorio.setStyleSheet("")
        
        # Resetar status
        self.lblInfoStatus.setText(
            "<b>Status:</b> Selecione as camadas e clique em 'EXTRAIR PARÂMETROS'."
        )
        self.lblInfoStatus.setStyleSheet("")
        
        self.resultados = {}
        self.area_selecionada = None
        
    def salvar_calculo(self):
        """Salva cálculo no banco de dados e persiste estado"""
        if not self.resultados:
            QMessageBox.warning(
                self,
                "Atenção",
                "Realize um cálculo antes de salvar"
            )
            return
            
        # Permitir gravação mesmo se simulado (bloqueado) se o usuário desejar
        # if self.calculo_bloqueado: ... (removido check de bloqueio conforme solicitado implicitamente para gravar dados)
            
        try:
            from ..banco_dados.gerenciador import GerenciadorBancoDados
            
            # Salvar imagem e relatório de impermeabilidade (se houver dados)
            imagem_path, relatorio_path = self._salvar_resultados_impermeabilidade_em_disco()
            
            bd = GerenciadorBancoDados()
            bd.criar_tabelas()
            bd.salvar_calculo(self.resultados, bacia_id=None)
            
            # Salvar estado no projeto QGIS
            self.salvar_estado_formulario()
            
            # Gravar Ponto do Exutório na Camada Vetorial (Se houver ponto calculado)
            exutorio_gravado = False
            pt_dict = self.resultados.get('exutorio_ponto', None)
            cota = self.resultados.get('exutorio_cota', None)
            
            if pt_dict and isinstance(pt_dict, dict) and 'x' in pt_dict and 'y' in pt_dict and cota is not None:
                try:
                    ponto = QgsPointXY(float(pt_dict['x']), float(pt_dict['y']))
                    layer_exutorio = self.cmbExutorio.currentData()
                    
                    if layer_exutorio:
                        self.gravar_exutorio(ponto, cota)
                        exutorio_gravado = True
                        QgsMessageLog.logMessage(
                            f"Exutório gravado: X={ponto.x():.2f}, Y={ponto.y():.2f}, Z={cota:.2f}",
                            'MetodoRacionalPro',
                            Qgis.Info
                        )
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Erro ao processar dados do exutório: {str(e)}",
                        'MetodoRacionalPro',
                        Qgis.Warning
                    )
            
            # Mensagem de sucesso com detalhes
            msg_sucesso = "Cálculo salvo com sucesso!"
            if exutorio_gravado:
                msg_sucesso += "\n\nPonto do exutório gravado na camada selecionada."
            elif pt_dict and not self.cmbExutorio.currentData():
                msg_sucesso += "\n\nNota: Nenhuma camada de exutório selecionada."
            
            if imagem_path and relatorio_path:
                msg_sucesso += f"\n\nArquivos de impermeabilidade salvos em:\n{os.path.dirname(imagem_path)}"
            
            QMessageBox.information(
                self,
                "Sucesso",
                msg_sucesso
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao salvar: {str(e)}"
            )
            
    def gerar_relatorio(self):
        """Gera relatório técnico em DOCX, ODT ou HTML"""
        if not self.resultados:
            QMessageBox.warning(
                self,
                "Atenção",
                "Realize um cálculo antes de gerar relatório"
            )
            return
        
        # Verificar se python-docx está disponível
        try:
            from docx import Document
            docx_disponivel = True
        except ImportError:
            docx_disponivel = False
        
        # Montar filtros de arquivo - ODT sempre disponível
        if docx_disponivel:
            filtros = "Word Document (*.docx);;LibreOffice/OpenOffice (*.odt);;HTML (*.html);;Todos (*.*)"
        else:
            filtros = "LibreOffice/OpenOffice (*.odt);;HTML (*.html);;Todos (*.*)"
            
        caminho, filtro_selecionado = QFileDialog.getSaveFileName(
            self,
            "Salvar Relatório",
            "relatorio_drenagem",
            filtros
        )
        
        if caminho:
            try:
                # Capturar screenshot do Map Canvas (qgis.utils.iface)
                import os
                import tempfile
                from qgis.utils import iface
                
                imagem_mapa_path = None
                if iface and iface.mapCanvas():
                    temp_dir = tempfile.gettempdir()
                    imagem_mapa_path = os.path.join(temp_dir, f"mapa_qgis_{datetime.now().strftime('%Y%m%d%H%M%S')}.png")
                    iface.mapCanvas().saveAsImage(imagem_mapa_path)
                
                # Preparar dados estruturados para o relatório
                dados_relatorio = dict(self.resultados)
                
                # 1. Dados de entrada (formatados para o gerador)
                dados_entrada = self._coletar_todos_dados()
            
                # Garantir mapeamento entre 'impermeabilidade' (UI) e 'coef_escoamento' (Generator)
                if 'impermeabilidade' in dados_entrada and 'coef_escoamento' not in dados_entrada:
                    dados_entrada['coef_escoamento'] = dados_entrada['impermeabilidade']

                # --- Normalizar cidade_idf para chave compatível com CurvasIDF ---
                # Ex: "Juiz de Fora - MG" → "juiz_de_fora"
                # Ex: "Juiz de Fora - Norte Eq.11" → "juiz_de_fora_-_norte_eq.11"
                cidade_idf_raw = dados_entrada.get('cidade_idf', '')
                # Tentar encontrar pela remoção do sufixo ' - UF'
                partes = cidade_idf_raw.split(' - ')
                if len(partes) >= 2:
                    # Se a segunda parte tem 2 chars (estado), usar só o nome da cidade
                    # Se tem mais (ex: "Norte Eq.11"), manter composição completa
                    if len(partes[1].strip()) <= 3:  # UF como 'MG', 'SP', 'RJ'
                        cidade_idf_normalizada = partes[0].strip().lower().replace(' ', '_')
                    else:
                        # Nome composto como "Juiz de Fora - Norte Eq.11"
                        cidade_idf_normalizada = cidade_idf_raw.strip().lower().replace(' ', '_')
                else:
                    cidade_idf_normalizada = cidade_idf_raw.strip().lower().replace(' ', '_')
                dados_entrada['cidade_idf'] = cidade_idf_normalizada

                # --- Normalizar tempo_retorno para inteiro ---
                # Pode vir como "25 anos" ou "25"
                tr_raw = str(dados_entrada.get('tempo_retorno', '25'))
                try:
                    dados_entrada['tempo_retorno'] = int(tr_raw.split()[0])
                except (ValueError, IndexError):
                    dados_entrada['tempo_retorno'] = 25
                    
                # Converter strings para números onde necessário
                try:
                    chaves_numericas = [
                        'area', 'distancia', 'desnivel', 'tempo', 'coef_escoamento', 
                        'rugosidade', 'declividade', 'intensidade',
                        'vazao', 'diametro', 'velocidade', 'froude', 'lamina'
                    ]
                    for key in chaves_numericas:
                        if key in dados_entrada:
                            val = str(dados_entrada.get(key, '0')).replace(',', '.')
                            dados_relatorio[key] = float(val) if val else 0.0
                            # Atualizar também no dados_entrada para cálculos internos do gerador
                            dados_entrada[key] = dados_relatorio[key]
                except Exception as e:
                    QgsMessageLog.logMessage(f"Erro na conversão numérica para relatório: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)
            
                # Garantir lado_galeria como float
                # Pode vir de self.resultados (float) ou precisa ser parseado de "0.96 x 0.96"
                lado_val = dados_relatorio.get('lado_galeria', 0)
                if not lado_val or lado_val == 0:
                    galeria_text = dados_entrada.get('galeria', '')
                    if galeria_text and 'x' in str(galeria_text):
                        try:
                            lado_val = float(str(galeria_text).split('x')[0].strip().replace(',', '.'))
                        except (ValueError, TypeError):
                            lado_val = 0
                    elif galeria_text:
                        try:
                            lado_val = float(str(galeria_text).replace(',', '.'))
                        except (ValueError, TypeError):
                            lado_val = 0
                dados_relatorio['lado_galeria'] = lado_val
            
                # Preservar dados de Tc e Metodologia no nível raiz
                if 'metodo_tc' in dados_entrada:
                    dados_relatorio['metodo_tc'] = dados_entrada['metodo_tc']
                if 'tabela_tc' in dados_entrada:
                    dados_relatorio['tabela_tc'] = dados_entrada['tabela_tc']
                if 'parametros_tc_full' in dados_entrada:
                    dados_relatorio['parametros_tc_full'] = dados_entrada['parametros_tc_full']

                # Elevar impermeabilidade_dados ao nível raiz do relatorio
                imp_dados = dados_entrada.get('impermeabilidade_dados')
                if imp_dados:
                    dados_relatorio['impermeabilidade_dados'] = imp_dados
            
                dados_relatorio['dados_entrada'] = dados_entrada
                
                # 2. Camadas usadas
                camadas = {
                    'MDT (Topografia)': dados_entrada.get('camada_mdt'),
                    'Área de Estudo': dados_entrada.get('camada_area'),
                    'Imagem de Satélite': dados_entrada.get('camada_imagem'),
                    'Curvas de Nível': dados_entrada.get('camada_curvas'),
                    'Cursos d\'Água': dados_entrada.get('camada_cursos'),
                    'Exutório': dados_entrada.get('camada_exutorio')
                }
                # Remover as vazias
                dados_relatorio['camadas_usadas'] = {k: v for k, v in camadas.items() if v}
                
                # 3. Coordenadas do Centroide
                try:
                    from qgis.core import QgsCoordinateTransform, QgsProject, QgsCoordinateReferenceSystem
                    
                    camada_area_obj = None
                    # Tentar encontrar a camada de área de estudo no projeto
                    camada_area_nome = dados_entrada.get('camada_area')
                    if camada_area_nome:
                        for layer in QgsProject.instance().mapLayers().values():
                            if layer.name() == camada_area_nome:
                                camada_area_obj = layer
                                break
                    
                    if camada_area_obj:
                        geom = self.obter_geometria_area(camada_area_obj)
                        if geom and not geom.isEmpty():
                            centroide = geom.centroid().asPoint()
                            
                            # Transformar para WGS84 (EPSG:4326) para o relatório (Lat/Long)
                            crs_src = camada_area_obj.crs()
                            crs_dest = QgsCoordinateReferenceSystem("EPSG:4326")
                            xform = QgsCoordinateTransform(crs_src, crs_dest, QgsProject.instance())
                            
                            ponto_wgs84 = xform.transform(centroide)
                            dados_relatorio['coordenadas'] = f"Lat: {ponto_wgs84.y():.6f}, Long: {ponto_wgs84.x():.6f}"
                        else:
                            dados_relatorio['coordenadas'] = "Não disponível (geometria vazia)"
                    else:
                        dados_relatorio['coordenadas'] = "Não disponível (camada não encontrada)"
                except Exception as e:
                    QgsMessageLog.logMessage(f"Erro ao calcular centroide: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)
                    dados_relatorio['coordenadas'] = "Erro no cálculo"

                # 4. Imagem do Mapa
                if imagem_mapa_path and os.path.exists(imagem_mapa_path):
                    dados_relatorio['imagem_mapa'] = imagem_mapa_path

                from ..relatorios.gerador_docx import GeradorRelatorio
                
                gerador = GeradorRelatorio()
                gerador.gerar_relatorio_completo(dados_relatorio, caminho)
                
                # Verificar extensão final do arquivo
                import os
                _, ext = os.path.splitext(caminho)
                ext = ext.lower()
                
                if ext == '.odt':
                    QMessageBox.information(
                        self,
                        "Sucesso",
                        f"Relatório gerado em ODT:\n{caminho}\n\n"
                        f"Dica: Abra no LibreOffice, OpenOffice ou Word para editar e complementar."
                    )
                elif ext == '.html':
                    QMessageBox.information(
                        self,
                        "Sucesso",
                        f"Relatório gerado em HTML:\n{caminho}\n\n"
                        f"Dica: Abra no navegador ou no Word/LibreOffice para visualizar."
                    )
                elif ext == '.docx' and not docx_disponivel:
                    # Fallback para ODT
                    caminho_real = caminho.replace('.docx', '.odt')
                    QMessageBox.information(
                        self,
                        "Sucesso",
                        f"Relatório gerado em ODT (python-docx não disponível):\n{caminho_real}\n\n"
                        f"Dica: Abra no LibreOffice, OpenOffice ou Word para editar."
                    )
                else:
                    QMessageBox.information(
                        self,
                        "Sucesso",
                        f"Relatório gerado: {caminho}\n\n"
                        f"Dica: Abra no Word para editar e complementar."
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Erro ao gerar relatório: {str(e)}"
                )
                
    def exportar_resultados(self):
        """Exporta resultados em múltiplos formatos"""
        if not self.resultados:
            QMessageBox.warning(
                self,
                "Atenção",
                "Realize um cálculo antes de exportar"
            )
            return
            
        formatos = ["GeoPackage (*.gpkg)", "Shapefile (*.shp)", "GeoJSON (*.geojson)", 
                   "CSV (*.csv)", "Excel (*.xlsx)"]
        
        caminho, filtro = QFileDialog.getSaveFileName(
            self,
            "Exportar Resultados",
            "",
            ";;".join(formatos)
        )
        
        if caminho:
            try:
                from ..relatorios.exportador import ExportadorResultados
                
                exportador = ExportadorResultados()
                exportador.exportar(self.resultados, caminho)
                
                QMessageBox.information(
                    self,
                    "Sucesso",
                    f"Resultados exportados: {caminho}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Erro ao exportar: {str(e)}"
                )
                
    def remover_dados(self):
        """Remove dados permanentemente"""
        resposta = QMessageBox.question(
            self,
            "Confirmar Remoção",
            "Deseja realmente remover os dados permanentemente?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if resposta == QMessageBox.Yes:
            self.limpar_formulario()
            QMessageBox.information(
                self,
                "Info",
                "Dados removidos com sucesso"
            )

    def closeEvent(self, event):
        """Salva estado ao fechar o plugin"""
        self.salvar_estado_formulario()
        self.salvar_selecoes_projeto()
        super(MetodoRacionalDialog, self).closeEvent(event)


class DetalhesImpermeabilidadeDialog(QDialog):
    """
    Diálogo para exibir detalhes do cálculo de impermeabilidade.
    Mostra a imagem classificada e estatísticas detalhadas.
    """
    def __init__(self, resultados, parent=None):
        super().__init__(parent)
        self.resultados = resultados
        self.setWindowTitle("Detalhes de Impermeabilidade")
        self.resize(1000, 700)
        self.configurar_ui()
        self.exibir_dados()
        
    def configurar_ui(self):
        layout = QVBoxLayout(self)
        
        # Cabeçalho
        header = QFrame()
        header.setStyleSheet("background-color: #e3f2fd; border-radius: 5px; padding: 10px;")
        h_layout = QHBoxLayout(header)
        
        lbl_titulo = QLabel("Análise de Impermeabilidade do Solo")
        lbl_titulo.setFont(QFont("Arial", 14, QFont.Bold))
        h_layout.addWidget(lbl_titulo)
        
        h_layout.addStretch()
        
        self.lbl_percentual = QLabel()
        self.lbl_percentual.setFont(QFont("Arial", 16, QFont.Bold))
        self.lbl_percentual.setStyleSheet("color: #1976D2;")
        h_layout.addWidget(self.lbl_percentual)
        
        layout.addWidget(header)
        
        # Área para imagem (sem rolagem, com redimensionamento automático)
        image_container = QFrame()
        image_container.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 5px;")
        img_layout = QVBoxLayout(image_container)
        img_layout.setContentsMargins(5, 5, 5, 5)
        
        self.lbl_imagem = QLabel()
        self.lbl_imagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Importante: não usar setScaledContents(True) diretamente pois distorce a proporção
        # Faremos o redimensionamento manual mantendo aspect ratio
        img_layout.addWidget(self.lbl_imagem)
        
        layout.addWidget(image_container, 1) # Stretch factor 1 para ocupar espaço central
        
        # Painel de estatísticas
        stats_group = QGroupBox("Estatísticas da Classificação")
        stats_layout = QGridLayout(stats_group)
        
        # Labels de estatísticas
        self.stats_labels = {}
        items = [
            ("Área Total (pixels):", "total"),
            ("Área Impermeável:", "impermeavel"),
            ("Área Vegetada:", "vegetacao"),
            ("Área Sombra/Água:", "sombra")
        ]
        
        for i, (label, key) in enumerate(items):
            stats_layout.addWidget(QLabel(label), i, 0)
            val_lbl = QLabel()
            val_lbl.setFont(QFont("Arial", 10, QFont.Bold))
            stats_layout.addWidget(val_lbl, i, 1)
            self.stats_labels[key] = val_lbl
            
        # Legenda
        legenda = QFrame()
        legenda.setStyleSheet("border: 1px solid #ddd; padding: 5px;")
        l_layout = QHBoxLayout(legenda)
        l_layout.addWidget(QLabel("Legenda:"))
        
        def create_legend_item(color, text):
            lbl = QLabel(f"  {text}  ")
            lbl.setStyleSheet(f"background-color: {color}; color: white; border-radius: 3px; font-weight: bold;")
            return lbl
            
        l_layout.addWidget(create_legend_item("#000000", "Impermeável"))
        l_layout.addWidget(create_legend_item("#228B22", "Vegetação"))
        l_layout.addWidget(create_legend_item("#1E90FF", "Sombra/Água"))
        l_layout.addStretch()
        
        stats_layout.addWidget(legenda, 0, 2, 4, 1)
        
        layout.addWidget(stats_group)
        
        # Botão fechar
        btn_fechar = QPushButton("Fechar")
        btn_fechar.setMinimumHeight(30)
        btn_fechar.clicked.connect(self.accept)
        layout.addWidget(btn_fechar)
        
    def exibir_dados(self):
        if not self.resultados:
            return
            
        # Atualizar percentual
        perc = self.resultados.get('percentual', 0)
        self.lbl_percentual.setText(f"{perc:.2f}%")
        
        # Atualizar estatísticas
        total = self.resultados.get('total_pixels', 0)
        imp = self.resultados.get('impermeable_pixels', 0)
        veg = self.resultados.get('vegetation_pixels', 0)
        shadow = self.resultados.get('shadow_pixels', 0)
        
        self.stats_labels['total'].setText(f"{total:,}")
        self.stats_labels['impermeavel'].setText(f"{imp:,} ({self.resultados.get('percentual', 0):.2f}%)")
        self.stats_labels['vegetacao'].setText(f"{veg:,} ({self.resultados.get('percent_vegetation', 0):.2f}%)")
        self.stats_labels['sombra'].setText(f"{shadow:,} ({self.resultados.get('percent_shadow', 0):.2f}%)")
        
        # Gerar imagem visual
        self.gerar_imagem_visualizacao()
        
    def gerar_imagem_visualizacao(self):
        """Gera imagem composta para visualização"""
        try:
            rgb = self.resultados.get('rgb_image')
            classification = self.resultados.get('classification_map')
            valid_mask = self.resultados.get('valid_mask')
            
            # Se não houver dados numpy (sessão recarregada), tentar carregar de arquivos
            if rgb is None or classification is None:
                path_orig = self.resultados.get('impermeabilidade_imagem_original')
                path_class = self.resultados.get('impermeabilidade_imagem')
                
                if path_orig and path_class and os.path.exists(path_orig) and os.path.exists(path_class):
                    # Carregar imagens salvas
                    pix_orig = QPixmap(path_orig)
                    pix_class = QPixmap(path_class)
                    
                    if not pix_orig.isNull() and not pix_class.isNull():
                        w_orig = pix_orig.width()
                        w_class = pix_class.width()
                        h_orig = pix_orig.height()
                        h_class = pix_class.height()
                        
                        final_width = w_orig + w_class + 20
                        final_height = max(h_orig, h_class) + 40
                        
                        pixmap = QPixmap(final_width, final_height)
                        pixmap.fill(Qt.GlobalColor.white)
                        
                        painter = QPainter(pixmap)
                        painter.setPen(Qt.GlobalColor.black)
                        painter.setFont(QFont("Arial", 12, QFont.Bold))
                        painter.drawText(10, 25, "Original (RGB) - Carregado de Arquivo")
                        painter.drawText(w_orig + 30, 25, "Classificação - Carregado de Arquivo")
                        
                        painter.drawPixmap(0, 35, pix_orig)
                        painter.drawPixmap(w_orig + 20, 35, pix_class)
                        painter.end()
                        
                        # REDIMENSIONAMENTO: Aplicar escala também para imagens carregadas de arquivo
                        target_width = self.width() - 40
                        target_height = self.height() - 280
                        
                        scaled_pixmap = pixmap.scaled(
                            target_width, target_height,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        
                        self.lbl_imagem.setPixmap(scaled_pixmap)
                        return
                
                self.lbl_imagem.setText("Imagens não disponíveis (os arrays numpy foram limpos para persistência e os arquivos não foram encontrados)")
                return
                
            # Converter RGB para QImage
            # RGB shape é (3, H, W) -> precisa ser (H, W, 3)
            rgb_transposed = np.moveaxis(rgb, 0, -1).astype(np.uint8)
            h_rgb, w_rgb, ch = rgb_transposed.shape
            bytes_per_line = ch * w_rgb
            
            # Criar QImage a partir do buffer tobytes() para evitar problemas de memória/alinhamento
            qimg_rgb = QImage(rgb_transposed.tobytes(), w_rgb, h_rgb, bytes_per_line, QImage.Format_RGB888).copy()
            
            # Criar Imagem de Classificação
            # Mapear classes para cores
            # 0=Imper (Preto), 1=Veg (Verde), 2=Sombra (Azul)
            h, w = classification.shape
            class_color = np.zeros((h, w, 3), dtype=np.uint8)
            
            # Background (branco onde inválido)
            class_color[:] = [255, 255, 255] 
            
            # Aplicar cores onde máscara válida
            mask_imper = (classification == 0) & valid_mask
            mask_veg = (classification == 1) & valid_mask
            mask_shadow = (classification == 2) & valid_mask
            
            class_color[mask_imper] = [50, 50, 50]    # Cinza Escuro
            class_color[mask_veg] = [34, 139, 34]     # Verde Floresta
            class_color[mask_shadow] = [30, 144, 255] # Azul Dodger
            
            # QImage para classificação
            qimg_class = QImage(class_color.tobytes(), w, h, 3 * w, QImage.Format_RGB888).copy()
            
            # Combinar imagens em uma QPixmap
            final_width = w_rgb + w + 20 # 20px gap
            final_height = max(h_rgb, h) + 40 # +40 para titulos
            
            pixmap = QPixmap(final_width, final_height)
            pixmap.fill(Qt.GlobalColor.white)
            
            painter = QPainter(pixmap)
            
            # Títulos
            painter.setPen(Qt.GlobalColor.black)
            font = QFont("Arial", 12, QFont.Bold)
            painter.setFont(font)
            painter.drawText(10, 25, "Original (RGB)")
            painter.drawText(w_rgb + 30, 25, "Classificação")
            
            # Imagens
            painter.drawImage(0, 35, qimg_rgb)
            painter.drawImage(w_rgb + 20, 35, qimg_class)
            
            painter.end()
            
            # REDIMENSIONAMENTO: Garantir que caiba na Label sem barras de rolagem
            # Altura disponível aproximada: Altura Janela (700) - Header (~60) - Stats (~200) - Margens (~40)
            target_width = self.width() - 40
            target_height = self.height() - 280 # Folga generosa para estatísticas
            
            scaled_pixmap = pixmap.scaled(
                target_width, target_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.lbl_imagem.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self.lbl_imagem.setText(f"Erro ao gerar visualização: {str(e)}")
            import traceback
            traceback.print_exc()
