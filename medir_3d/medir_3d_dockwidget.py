from PyQt5.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QComboBox, 
    QPushButton, QLabel, QPlainTextEdit, QLineEdit, QHBoxLayout
)
from PyQt5.QtCore import Qt

class Medir3DDockWidget(QDockWidget):
    def __init__(self, parent=None):
        super(Medir3DDockWidget, self).__init__(parent)
        self.setWindowTitle("Medir 3D")
        
        self.main_widget = QWidget()
        self.layout = QVBoxLayout(self.main_widget)
        
        # Layer selection
        self.layout.addWidget(QLabel("Camada Raster (MDT/MDS):"))
        self.combo_layer = QComboBox()
        self.layout.addWidget(self.combo_layer)
        
        # Action Buttons
        self.btn_medir_distancia = QPushButton("Medir Distância 3D")
        self.layout.addWidget(self.btn_medir_distancia)
        
        self.btn_limpar = QPushButton("Limpar Medições")
        self.layout.addWidget(self.btn_limpar)
        
        self.layout.addWidget(QLabel("Salvar Local:"))
        self.input_nome_projeto = QLineEdit()
        self.input_nome_projeto.setPlaceholderText("Ex: Rua A - Trecho 1")
        self.layout.addWidget(self.input_nome_projeto)
        
        self.btn_salvar = QPushButton("Salvar no Banco de Dados")
        self.layout.addWidget(self.btn_salvar)
        
        # Manhole (PV) features
        pv_layout = QHBoxLayout()
        pv_layout.addWidget(QLabel("Declive(%):"))
        self.input_inclinacao = QLineEdit("1.0")
        pv_layout.addWidget(self.input_inclinacao)
        
        pv_layout.addWidget(QLabel("Dist. Max(m):"))
        self.input_dist_pv = QLineEdit("40")
        pv_layout.addWidget(self.input_dist_pv)

        pv_layout.addWidget(QLabel("Diâmetro(mm):"))
        self.input_diametro = QLineEdit("600")
        pv_layout.addWidget(self.input_diametro)
        
        self.btn_atualizar_pvs = QPushButton("Recalcular PVs")
        pv_layout.addWidget(self.btn_atualizar_pvs)
        
        self.btn_perfil = QPushButton("Ver Perfil")
        pv_layout.addWidget(self.btn_perfil)
        self.layout.addLayout(pv_layout)
        
        # History section
        self.layout.addWidget(QLabel("Histórico de Redes Salvas:"))
        hist_layout = QHBoxLayout()
        self.combo_historico = QComboBox()
        hist_layout.addWidget(self.combo_historico, 1)
        self.btn_carregar_historico = QPushButton("Carregar")
        self.btn_excluir_historico = QPushButton("Excluir")
        hist_layout.addWidget(self.btn_carregar_historico)
        hist_layout.addWidget(self.btn_excluir_historico)
        self.layout.addLayout(hist_layout)
        
        # Results area
        self.layout.addWidget(QLabel("Resultados:"))
        self.txt_resultados = QPlainTextEdit()
        self.txt_resultados.setReadOnly(True)
        self.layout.addWidget(self.txt_resultados)
        
        self.layout.addStretch()
        self.setWidget(self.main_widget)
        
    def add_result(self, text):
        self.txt_resultados.appendPlainText(text)
