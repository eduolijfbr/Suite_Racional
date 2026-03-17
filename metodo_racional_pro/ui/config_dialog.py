# -*- coding: utf-8 -*-
"""
Dialog de Configurações e Banco de Dados
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox,
    QRadioButton, QButtonGroup, QTableWidget, QTableWidgetItem,
    QMessageBox, QFileDialog, QHeaderView
)
from qgis.PyQt.QtCore import Qt


class ConfigDialog(QDialog):
    """Dialog de configurações e banco de dados"""
    
    def __init__(self, parent=None):
        super(ConfigDialog, self).__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Configura interface"""
        self.setWindowTitle("Configurações - Banco de Dados")
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # Tipo de conexão
        grp_tipo = QGroupBox("Tipo de Banco de Dados")
        tipo_layout = QVBoxLayout(grp_tipo)
        
        self.btnGrupo = QButtonGroup()
        
        self.rbSQLite = QRadioButton("SQLite Local")
        self.rbSQLite.setChecked(True)
        self.btnGrupo.addButton(self.rbSQLite)
        tipo_layout.addWidget(self.rbSQLite)
        
        self.rbPostgres = QRadioButton("PostgreSQL/PostGIS")
        self.btnGrupo.addButton(self.rbPostgres)
        tipo_layout.addWidget(self.rbPostgres)
        
        layout.addWidget(grp_tipo)
        
        # SQLite
        self.grpSQLite = QGroupBox("Configuração SQLite")
        sqlite_layout = QGridLayout(self.grpSQLite)
        
        sqlite_layout.addWidget(QLabel("Arquivo:"), 0, 0)
        self.txtArquivoSQLite = QLineEdit()
        self.txtArquivoSQLite.setText("drenagem.db")
        sqlite_layout.addWidget(self.txtArquivoSQLite, 0, 1)
        
        self.btnProcurar = QPushButton("📁 Procurar")
        self.btnProcurar.clicked.connect(self.procurar_arquivo)
        sqlite_layout.addWidget(self.btnProcurar, 0, 2)
        
        btn_sqlite_layout = QHBoxLayout()
        self.btnNovoBD = QPushButton("➕ Novo BD")
        self.btnNovoBD.clicked.connect(self.criar_novo_bd)
        btn_sqlite_layout.addWidget(self.btnNovoBD)
        
        self.btnConectar = QPushButton("🔄 Conectar")
        self.btnConectar.clicked.connect(self.conectar_bd)
        btn_sqlite_layout.addWidget(self.btnConectar)
        
        sqlite_layout.addLayout(btn_sqlite_layout, 1, 0, 1, 3)
        
        self.lblStatusSQLite = QLabel("Status: Desconectado")
        sqlite_layout.addWidget(self.lblStatusSQLite, 2, 0, 1, 3)
        
        layout.addWidget(self.grpSQLite)
        
        # PostgreSQL
        self.grpPostgres = QGroupBox("Configuração PostgreSQL")
        pg_layout = QGridLayout(self.grpPostgres)
        
        pg_layout.addWidget(QLabel("Host:"), 0, 0)
        self.txtHost = QLineEdit("localhost")
        pg_layout.addWidget(self.txtHost, 0, 1)
        
        pg_layout.addWidget(QLabel("Porta:"), 0, 2)
        self.txtPorta = QLineEdit("5432")
        pg_layout.addWidget(self.txtPorta, 0, 3)
        
        pg_layout.addWidget(QLabel("Banco:"), 1, 0)
        self.txtBanco = QLineEdit()
        pg_layout.addWidget(self.txtBanco, 1, 1)
        
        pg_layout.addWidget(QLabel("Usuário:"), 1, 2)
        self.txtUsuario = QLineEdit()
        pg_layout.addWidget(self.txtUsuario, 1, 3)
        
        pg_layout.addWidget(QLabel("Senha:"), 2, 0)
        self.txtSenha = QLineEdit()
        self.txtSenha.setEchoMode(QLineEdit.Password)
        pg_layout.addWidget(self.txtSenha, 2, 1)
        
        self.btnConectarPG = QPushButton("🔄 Conectar")
        self.btnConectarPG.clicked.connect(self.conectar_postgres)
        pg_layout.addWidget(self.btnConectarPG, 2, 2, 1, 2)
        
        self.grpPostgres.setEnabled(False)
        layout.addWidget(self.grpPostgres)
        
        # Projetos salvos
        grp_projetos = QGroupBox("Projetos Salvos")
        proj_layout = QVBoxLayout(grp_projetos)
        
        self.tblProjetos = QTableWidget()
        self.tblProjetos.setColumnCount(5)
        self.tblProjetos.setHorizontalHeaderLabels(
            ["ID", "Nome", "Data", "TR", "Vazão (m³/s)"]
        )
        self.tblProjetos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        proj_layout.addWidget(self.tblProjetos)
        
        btn_proj_layout = QHBoxLayout()
        
        self.btnCarregar = QPushButton("📥 Carregar")
        self.btnCarregar.clicked.connect(self.carregar_projeto)
        btn_proj_layout.addWidget(self.btnCarregar)
        
        self.btnExcluir = QPushButton("🗑️ Excluir")
        self.btnExcluir.clicked.connect(self.excluir_projeto)
        btn_proj_layout.addWidget(self.btnExcluir)
        
        self.btnAtualizar = QPushButton("🔄 Atualizar")
        self.btnAtualizar.clicked.connect(self.atualizar_lista)
        btn_proj_layout.addWidget(self.btnAtualizar)
        
        proj_layout.addLayout(btn_proj_layout)
        
        layout.addWidget(grp_projetos)
        
        # Botões
        btn_layout = QHBoxLayout()
        
        self.btnFechar = QPushButton("Fechar")
        self.btnFechar.clicked.connect(self.close)
        btn_layout.addWidget(self.btnFechar)
        
        layout.addLayout(btn_layout)
        
        # Conectar sinais
        self.rbSQLite.toggled.connect(self.alternar_tipo_bd)
        self.rbPostgres.toggled.connect(self.alternar_tipo_bd)
        
    def alternar_tipo_bd(self):
        """Alterna entre SQLite e PostgreSQL"""
        self.grpSQLite.setEnabled(self.rbSQLite.isChecked())
        self.grpPostgres.setEnabled(self.rbPostgres.isChecked())
        
    def procurar_arquivo(self):
        """Abre diálogo para selecionar arquivo SQLite"""
        arquivo, _ = QFileDialog.getSaveFileName(
            self,
            "Selecionar Banco de Dados",
            "",
            "SQLite Database (*.db *.sqlite)"
        )
        if arquivo:
            self.txtArquivoSQLite.setText(arquivo)
            
    def criar_novo_bd(self):
        """Cria novo banco de dados"""
        try:
            from ..banco_dados.gerenciador import GerenciadorBancoDados
            
            arquivo = self.txtArquivoSQLite.text()
            bd = GerenciadorBancoDados(tipo='sqlite', arquivo=arquivo)
            bd.criar_tabelas()
            
            self.lblStatusSQLite.setText("Status: ✓ Banco criado com sucesso")
            self.lblStatusSQLite.setStyleSheet("color: green;")
            
            QMessageBox.information(
                self,
                "Sucesso",
                "Banco de dados criado com sucesso!"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao criar banco: {str(e)}"
            )
            
    def conectar_bd(self):
        """Conecta ao banco SQLite"""
        try:
            from ..banco_dados.gerenciador import GerenciadorBancoDados
            
            arquivo = self.txtArquivoSQLite.text()
            bd = GerenciadorBancoDados(tipo='sqlite', arquivo=arquivo)
            
            self.lblStatusSQLite.setText("Status: ✓ Conectado")
            self.lblStatusSQLite.setStyleSheet("color: green;")
            
            self.atualizar_lista()
            
        except Exception as e:
            self.lblStatusSQLite.setText(f"Status: ✗ Erro: {str(e)}")
            self.lblStatusSQLite.setStyleSheet("color: red;")
            
    def conectar_postgres(self):
        """Conecta ao PostgreSQL"""
        try:
            from ..banco_dados.gerenciador import GerenciadorBancoDados
            
            bd = GerenciadorBancoDados(
                tipo='postgresql',
                host=self.txtHost.text(),
                porta=self.txtPorta.text(),
                banco=self.txtBanco.text(),
                usuario=self.txtUsuario.text(),
                senha=self.txtSenha.text()
            )
            
            QMessageBox.information(
                self,
                "Sucesso",
                "Conectado ao PostgreSQL!"
            )
            
            self.atualizar_lista()
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao conectar: {str(e)}"
            )
            
    def atualizar_lista(self):
        """Atualiza lista de projetos"""
        self.tblProjetos.setRowCount(0)
        
        # Dados de exemplo
        dados_exemplo = [
            ("01", "Rio Paraibuna", "19/12/2024", "25a", "9.67"),
            ("02", "Córrego Independência", "18/12/2024", "10a", "3.45"),
        ]
        
        for row, dados in enumerate(dados_exemplo):
            self.tblProjetos.insertRow(row)
            for col, valor in enumerate(dados):
                self.tblProjetos.setItem(row, col, QTableWidgetItem(valor))
                
    def carregar_projeto(self):
        """Carrega projeto selecionado"""
        row = self.tblProjetos.currentRow()
        if row < 0:
            QMessageBox.warning(
                self,
                "Atenção",
                "Selecione um projeto para carregar"
            )
            return
            
        QMessageBox.information(
            self,
            "Info",
            "Funcionalidade em desenvolvimento"
        )
        
    def excluir_projeto(self):
        """Exclui projeto selecionado"""
        row = self.tblProjetos.currentRow()
        if row < 0:
            QMessageBox.warning(
                self,
                "Atenção",
                "Selecione um projeto para excluir"
            )
            return
            
        resposta = QMessageBox.question(
            self,
            "Confirmar",
            "Deseja realmente excluir este projeto?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if resposta == QMessageBox.StandardButton.Yes:
            self.tblProjetos.removeRow(row)
