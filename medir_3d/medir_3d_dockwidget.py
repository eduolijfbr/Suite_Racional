from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QComboBox, 
    QPushButton, QLabel, QPlainTextEdit, QLineEdit, QHBoxLayout,
    QTabWidget, QCheckBox, QGroupBox, QGridLayout
)
from qgis.PyQt.QtCore import Qt

class Medir3DDockWidget(QDockWidget):
    def __init__(self, parent=None):
        super(Medir3DDockWidget, self).__init__(parent)
        self.setWindowTitle("Medir 3D")
        
        self.main_widget = QWidget()
        self.layout = QVBoxLayout(self.main_widget)
        
        # Layer selection (Global)
        self.layout.addWidget(QLabel("Camada Raster (MDT/MDS):"))
        self.combo_layer = QComboBox()
        self.layout.addWidget(self.combo_layer)
        
        # Tabs
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # --- TAB 1: Rede e PVs ---
        self.tab_pvs = QWidget()
        self.tab_pvs_layout = QVBoxLayout(self.tab_pvs)
        
        self.btn_medir_distancia = QPushButton("Medir Distância 3D")
        self.tab_pvs_layout.addWidget(self.btn_medir_distancia)
        
        self.btn_limpar = QPushButton("Limpar Medições")
        self.tab_pvs_layout.addWidget(self.btn_limpar)
        
        self.tab_pvs_layout.addWidget(QLabel("Salvar Local:"))
        self.input_nome_projeto = QLineEdit()
        self.input_nome_projeto.setPlaceholderText("Ex: Rua A - Trecho 1")
        self.tab_pvs_layout.addWidget(self.input_nome_projeto)
        
        self.btn_salvar = QPushButton("Salvar no Banco de Dados")
        self.tab_pvs_layout.addWidget(self.btn_salvar)
        
        pv_layout = QHBoxLayout()
        pv_layout.addWidget(QLabel("Declive Mín(%):"))
        self.input_inclinacao = QLineEdit("1.0")
        pv_layout.addWidget(self.input_inclinacao)
        
        pv_layout.addWidget(QLabel("Dist. Max(m):"))
        self.input_dist_pv = QLineEdit("40")
        pv_layout.addWidget(self.input_dist_pv)

        pv_layout.addWidget(QLabel("Diâmetro(mm):"))
        self.input_diametro = QLineEdit("600")
        pv_layout.addWidget(self.input_diametro)
        self.tab_pvs_layout.addLayout(pv_layout)
        
        btn_pv_layout = QHBoxLayout()
        self.btn_atualizar_pvs = QPushButton("Recalcular PVs")
        btn_pv_layout.addWidget(self.btn_atualizar_pvs)
        
        self.btn_perfil = QPushButton("Ver Perfil")
        btn_pv_layout.addWidget(self.btn_perfil)
        self.tab_pvs_layout.addLayout(btn_pv_layout)
        
        self.tab_pvs_layout.addStretch()
        self.tabs.addTab(self.tab_pvs, "Rede e PVs")
        
        # --- TAB 2: Sarjetas e Bocas de Lobo ---
        self.tab_sarjeta = QWidget()
        self.tab_sarjeta_layout = QVBoxLayout(self.tab_sarjeta)
        
        self.tab_sarjeta_layout.addWidget(QLabel("Camada Bacias (Polígonos):"))
        self.combo_bacias = QComboBox()
        self.tab_sarjeta_layout.addWidget(self.combo_bacias)
        
        self.tab_sarjeta_layout.addWidget(QLabel("Camada Vias (Linhas):"))
        self.combo_vias = QComboBox()
        self.tab_sarjeta_layout.addWidget(self.combo_vias)
        
        # Parâmetros
        group_params = QGroupBox("Parâmetros da Sarjeta")
        grid_params = QGridLayout()
        
        grid_params.addWidget(QLabel("n (Manning):"), 0, 0)
        self.input_manning = QLineEdit("0.016")
        grid_params.addWidget(self.input_manning, 0, 1)
        
        grid_params.addWidget(QLabel("Lâmina Máx (m):"), 0, 2)
        self.input_lamina = QLineEdit("0.13")
        grid_params.addWidget(self.input_lamina, 0, 3)
        
        grid_params.addWidget(QLabel("Caimento Transv (%):"), 1, 0)
        self.input_caimento = QLineEdit("3.0")
        grid_params.addWidget(self.input_caimento, 1, 1)

        grid_params.addWidget(QLabel("Cap. Engol (m3/s):"), 1, 2)
        self.input_engolimento = QLineEdit("0.06")
        grid_params.addWidget(self.input_engolimento, 1, 3)

        grid_params.addWidget(QLabel("Margem Segur (%):"), 2, 0)
        self.input_margem = QLineEdit("80")
        grid_params.addWidget(self.input_margem, 2, 1)

        grid_params.addWidget(QLabel("Distância Máx (m):"), 2, 2)
        self.input_dist_max = QLineEdit("60.0")
        grid_params.addWidget(self.input_dist_max, 2, 3)

        grid_params.addWidget(QLabel("Distância Mín (m):"), 3, 0)
        self.input_dist_min = QLineEdit("15.0")
        grid_params.addWidget(self.input_dist_min, 3, 1)

        grid_params.addWidget(QLabel("Largura da Via (m):"), 3, 2)
        self.input_largura_via = QLineEdit("10.0")
        grid_params.addWidget(self.input_largura_via, 3, 3)

        group_params.setLayout(grid_params)
        self.tab_sarjeta_layout.addWidget(group_params)
        
        # Substituição dinâmica
        self.chk_dinamico = QCheckBox("Substituir gabarito por atributos da camada de Vias")
        self.tab_sarjeta_layout.addWidget(self.chk_dinamico)
        
        self.group_dinamico = QGroupBox("Campos Atributos (Dinâmico)")
        self.group_dinamico.setEnabled(False)
        grid_dinamico = QGridLayout()
        
        grid_dinamico.addWidget(QLabel("n (Manning):"), 0, 0)
        self.combo_campo_n = QComboBox()
        grid_dinamico.addWidget(self.combo_campo_n, 0, 1)
        
        grid_dinamico.addWidget(QLabel("Lâmina Máx:"), 0, 2)
        self.combo_campo_lamina = QComboBox()
        grid_dinamico.addWidget(self.combo_campo_lamina, 0, 3)
        
        grid_dinamico.addWidget(QLabel("Caimento:"), 1, 0)
        self.combo_campo_caimento = QComboBox()
        grid_dinamico.addWidget(self.combo_campo_caimento, 1, 1)
        
        self.group_dinamico.setLayout(grid_dinamico)
        self.tab_sarjeta_layout.addWidget(self.group_dinamico)
        
        # Botões de Ação Sarjeta
        self.btn_calc_sarjeta = QPushButton("Lançar PVs e BLs (Sarjeta)")
        self.tab_sarjeta_layout.addWidget(self.btn_calc_sarjeta)
        
        self.tab_sarjeta_layout.addStretch()
        self.tabs.addTab(self.tab_sarjeta, "Sarjetas (PVs e BLs)")
        
        # --- TAB 3: Otimização de Traçado ---
        self.tab_otimiza = QWidget()
        self.tab_otimiza_layout = QVBoxLayout(self.tab_otimiza)
        
        self.tab_otimiza_layout.addWidget(QLabel("Traçado Econômico Global (MDT + Vias):"))
        self.tab_otimiza_layout.addWidget(QLabel("Nota: A análise cruzará os logradouros com a\ntopografia na bacia selecionada."))
        
        self.btn_calc_otimo = QPushButton("Calcular Traçado Econômico")
        self.btn_calc_otimo.setStyleSheet("background-color: #e1f5fe; font-weight: bold;")
        self.tab_otimiza_layout.addWidget(self.btn_calc_otimo)
        
        self.tab_otimiza_layout.addStretch()
        self.tabs.addTab(self.tab_otimiza, "Otimização")
        
        # --- Global Sections ---
        self.layout.addWidget(QLabel("Histórico de Redes Salvas:"))
        hist_layout = QHBoxLayout()
        self.combo_historico = QComboBox()
        hist_layout.addWidget(self.combo_historico, 1)
        self.btn_carregar_historico = QPushButton("Carregar")
        self.btn_excluir_historico = QPushButton("Excluir")
        hist_layout.addWidget(self.btn_carregar_historico)
        hist_layout.addWidget(self.btn_excluir_historico)
        self.layout.addLayout(hist_layout)
        
        self.layout.addWidget(QLabel("Resultados:"))
        self.txt_resultados = QPlainTextEdit()
        self.txt_resultados.setReadOnly(True)
        self.layout.addWidget(self.txt_resultados)
        
        self.setWidget(self.main_widget)
        
        # Signals
        self.chk_dinamico.toggled.connect(self.group_dinamico.setEnabled)
        
    def add_result(self, text):
        self.txt_resultados.appendPlainText(text)
