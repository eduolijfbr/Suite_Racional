# -*- coding: utf-8 -*-
"""
Dialog de Ajuda do Plugin Método Racional Pro
Exibe o manual do usuário em uma janela dedicada
"""

from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
)
from qgis.PyQt.QtGui import QFont

import os
import webbrowser

# Tentar importar QTextBrowser ou QWebEngineView
try:
    from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
    WEB_ENGINE_DISPONIVEL = True
except ImportError:
    WEB_ENGINE_DISPONIVEL = False

from qgis.PyQt.QtWidgets import QTextBrowser


class HelpDialog(QDialog):
    """Dialog para exibir a ajuda do plugin"""
    
    def __init__(self, parent=None):
        super(HelpDialog, self).__init__(parent)
        self.setup_ui()
        self.carregar_ajuda()
        
    def setup_ui(self):
        """Configura a interface"""
        self.setWindowTitle("Ajuda - Método Racional Pro")
        self.setMinimumSize(900, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        
        layout = QVBoxLayout(self)
        
        # Título
        titulo = QLabel("📚 Manual do Usuário - Método Racional Pro")
        titulo.setFont(QFont("Arial", 14, QFont.Bold))
        titulo.setStyleSheet("color: #1565C0; padding: 10px;")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(titulo)
        
        # Área de conteúdo
        if WEB_ENGINE_DISPONIVEL:
            self.browser = QWebEngineView()
        else:
            self.browser = QTextBrowser()
            self.browser.setOpenExternalLinks(True)
            self.browser.setStyleSheet("""
                QTextBrowser {
                    background-color: white;
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 10px;
                }
            """)
        
        layout.addWidget(self.browser)
        
        # Botões
        btn_layout = QHBoxLayout()
        
        self.btnAbrirNavegador = QPushButton("🌐 Abrir no Navegador")
        self.btnAbrirNavegador.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btnAbrirNavegador.clicked.connect(self.abrir_no_navegador)
        btn_layout.addWidget(self.btnAbrirNavegador)
        
        btn_layout.addStretch()
        
        self.btnFechar = QPushButton("Fechar")
        self.btnFechar.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        self.btnFechar.clicked.connect(self.close)
        btn_layout.addWidget(self.btnFechar)
        
        layout.addLayout(btn_layout)
        
    def carregar_ajuda(self):
        """Carrega o conteúdo da ajuda"""
        # Caminho do arquivo de ajuda
        help_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'docs',
            'manual_usuario.html'
        )
        
        self.help_path = os.path.abspath(help_file)
        
        if os.path.exists(self.help_path):
            if WEB_ENGINE_DISPONIVEL:
                self.browser.setUrl(QUrl.fromLocalFile(self.help_path))
            else:
                with open(self.help_path, 'r', encoding='utf-8') as f:
                    html = f.read()
                self.browser.setHtml(html)
        else:
            # Conteúdo de fallback
            self.browser.setHtml(self._get_ajuda_basica())
            
    def abrir_no_navegador(self):
        """Abre a ajuda no navegador padrão"""
        if os.path.exists(self.help_path):
            webbrowser.open('file:///' + self.help_path.replace('\\', '/'))
        else:
            # Criar arquivo temporário com ajuda básica
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(self._get_ajuda_basica())
                temp_path = f.name
            webbrowser.open('file:///' + temp_path.replace('\\', '/'))
            
    def _get_ajuda_basica(self):
        """Retorna HTML de ajuda básica como fallback"""
        return '''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <title>Ajuda - Método Racional Pro</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }
        h1 { color: #1565C0; border-bottom: 2px solid #1565C0; padding-bottom: 10px; }
        h2 { color: #1976D2; margin-top: 30px; }
        .info { background: #E3F2FD; padding: 15px; border-radius: 5px; margin: 15px 0; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background: #1565C0; color: white; }
        code { background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }
    </style>
</head>
<body>
    <h1>📐 Método Racional Pro</h1>
    <p>Plugin QGIS para Cálculo de Drenagem Urbana</p>
    
    <h2>Início Rápido</h2>
    <ol>
        <li>Carregue as camadas no QGIS (MDT, área de estudo, uso do solo)</li>
        <li>Abra o plugin: <code>Complementos → Método Racional Pro</code></li>
        <li>Selecione as camadas nos combos</li>
        <li>Clique em <strong>"EXTRAIR PARÂMETROS"</strong></li>
        <li>Clique em <strong>"Calcular IDF"</strong> para obter a intensidade</li>
        <li>Clique em <strong>"CALCULAR"</strong></li>
    </ol>
    
    <h2>Campos de Entrada</h2>
    <table>
        <tr><th>Campo</th><th>Descrição</th><th>Unidade</th></tr>
        <tr><td>Distância</td><td>Comprimento do talvegue</td><td>m</td></tr>
        <tr><td>Desnível</td><td>Diferença de altitude</td><td>m</td></tr>
        <tr><td>Tempo</td><td>Tempo de concentração</td><td>min</td></tr>
        <tr><td>Impermeabilidade</td><td>Coeficiente de escoamento (C)</td><td>0-1</td></tr>
        <tr><td>Área</td><td>Área da bacia</td><td>km²</td></tr>
        <tr><td>Rugosidade</td><td>Coeficiente de Manning</td><td>-</td></tr>
        <tr><td>Declividade</td><td>Inclinação do conduto</td><td>%</td></tr>
    </table>
    
    <h2>Coeficientes de Manning</h2>
    <table>
        <tr><th>Material</th><th>n (típico)</th></tr>
        <tr><td>PEAD/PVC</td><td>0.010</td></tr>
        <tr><td>Concreto liso</td><td>0.013</td></tr>
        <tr><td>Concreto rugoso</td><td>0.015</td></tr>
        <tr><td>Galeria celular</td><td>0.015</td></tr>
    </table>
    
    <h2>Coeficientes de Escoamento (C)</h2>
    <table>
        <tr><th>Superfície</th><th>C</th></tr>
        <tr><td>Asfalto/Concreto</td><td>0.90-0.95</td></tr>
        <tr><td>Área comercial</td><td>0.80-0.90</td></tr>
        <tr><td>Residencial</td><td>0.40-0.75</td></tr>
        <tr><td>Parques</td><td>0.15-0.25</td></tr>
        <tr><td>Floresta</td><td>0.10-0.20</td></tr>
    </table>
    
    <h2>Fórmulas</h2>
    <div class="info">
        <p><strong>Método Racional:</strong> Q = (C × I × A) / 3,6</p>
        <p><strong>Kirpich:</strong> Tc = 57 × (L³/H)^0,385</p>
        <p><strong>Manning:</strong> Q = (1/n) × A × R^(2/3) × S^(1/2)</p>
    </div>
    
    <h2>Verificações</h2>
    <ul>
        <li><strong>Velocidade:</strong> 0,6 a 5,0 m/s</li>
        <li><strong>Froude:</strong> < 1,0 (subcrítico)</li>
        <li><strong>Lâmina:</strong> 50% a 85% do diâmetro</li>
    </ul>
</body>
</html>'''
