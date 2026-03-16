# -*- coding: utf-8 -*-
"""
Método Racional Pro - Classe Principal do Plugin
"""

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QToolBar
from qgis.core import QgsProject, QgsMessageLog, Qgis

import os.path


class MetodoRacionalPro:
    """Plugin QGIS - Método Racional Pro"""
    
    def __init__(self, iface):
        """Constructor"""
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        
        # Inicializar variáveis
        self.actions = []
        self.menu = '&Suite Racional Pro'
        
        # Compartilhar toolbar
        self.toolbar_name = 'SuiteRacionalPro'
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, self.toolbar_name)
        if not self.toolbar:
            self.toolbar = self.iface.addToolBar('Suite Racional Pro')
            self.toolbar.setObjectName(self.toolbar_name)
        
        # Dialog
        self.dlg = None
        
    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        """Adiciona ação à interface do QGIS"""
        
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        
        if status_tip is not None:
            action.setStatusTip(status_tip)
            
        if whats_this is not None:
            action.setWhatsThis(whats_this)
            
        if add_to_toolbar:
            self.toolbar.addAction(action)
            # Removido: self.iface.addToolBarIcon(action) para evitar duplicação do ícone
            
        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action
            )
            
        self.actions.append(action)
        return action
        
    def initGui(self):
        """Cria entradas de menu e ícones dentro do QGIS"""
        
        # Diretório de ícones
        icons_dir = os.path.join(self.plugin_dir, 'recursos', 'icons')
        
        # Ícone principal (gota d'água)
        icon_main = os.path.join(icons_dir, 'icon.svg')
        if not os.path.exists(icon_main):
            icon_main = ':/images/themes/default/mActionAddRasterLayer.svg'
        
        # Ícone IDF (gráfico)
        icon_idf = os.path.join(icons_dir, 'idf.svg')
        if not os.path.exists(icon_idf):
            icon_idf = ':/images/themes/default/mActionShowAllLayers.svg'
        
        # Ícone Banco de Dados (cilindro)
        icon_db = os.path.join(icons_dir, 'database.svg')
        if not os.path.exists(icon_db):
            icon_db = ':/images/themes/default/mActionOpenTable.svg'
        
        # Ícone Ajuda (interrogação)
        icon_help = os.path.join(icons_dir, 'help.svg')
        if not os.path.exists(icon_help):
            icon_help = ':/images/themes/default/mActionHelpContents.svg'
        
        # Ação principal - Cálculo de Drenagem
        self.add_action(
            icon_main,
            text='Método Racional - Cálculo de Drenagem',
            callback=self.run,
            parent=self.iface.mainWindow(),
            status_tip='Calcular drenagem pelo Método Racional',
            whats_this='Abre a interface de cálculo de drenagem'
        )
        
        # Ação - Gerenciar Curvas IDF
        self.add_action(
            icon_idf,
            text='Gerenciar Curvas IDF',
            callback=self.abrir_gerenciador_idf,
            add_to_toolbar=False
        )
        
        # Ícone Impermeabilidade (usar ícone padrão de raster)
        icon_impermeabilidade = ':/images/themes/default/mActionAddRasterLayer.svg'
        
        # Ação - Análise de Impermeabilidade
        self.add_action(
            icon_impermeabilidade,
            text='Análise de Impermeabilidade',
            callback=self.abrir_analise_impermeabilidade,
            add_to_toolbar=False,
            status_tip='Calcular percentual de impermeabilidade do solo a partir de imagem raster',
            parent=self.iface.mainWindow()
        )
        
        # Ação - Banco de Dados
        self.add_action(
            icon_db,
            text='Banco de Dados',
            callback=self.abrir_banco_dados,
            add_to_toolbar=False
        )
        
        # Ação - Ajuda
        self.add_action(
            icon_help,
            text='Ajuda',
            callback=self.abrir_ajuda,
            add_to_toolbar=False
        )
        
    def unload(self):
        """Remove plugin do QGIS"""
        for action in self.actions:
            self.iface.removePluginMenu(
                '&Suite Racional Pro',
                action
            )
            self.iface.removeToolBarIcon(action)
        del self.toolbar
        
    def run(self):
        """Executa o plugin (agora como DockWidget)"""
        from .ui.main_dialog import MetodoRacionalDialog
        from .skills.qgis_smart_dock_skill import QgisSmartDockSkill
        
        if self.dlg is None:
            # Instanciar a UI (que é um DockWidget)
            self.dlg = MetodoRacionalDialog(self.iface, self.iface.mainWindow())
            
            # Instanciar e configurar a Skill
            self.dock_skill = QgisSmartDockSkill(
                self.iface, 
                "Método Racional Pro", 
                self.dlg
            )
            self.dlg = self.dock_skill.setup_dock(Qt.RightDockWidgetArea)
            
        # Carregar camadas disponíveis
        self.dlg.carregar_camadas_projeto()
        
        # Alternar visibilidade
        self.dock_skill.toggle_visibility()


        
    def abrir_gerenciador_idf(self):
        """Abre gerenciador de curvas IDF"""
        from .ui.idf_dialog import IDFDialog
        dlg = IDFDialog(self.iface.mainWindow())
        dlg.exec_()
        
    def abrir_banco_dados(self):
        """Abre gerenciador de banco de dados"""
        from .ui.config_dialog import ConfigDialog
        dlg = ConfigDialog(self.iface.mainWindow())
        dlg.exec_()
        
    def abrir_ajuda(self):
        """Abre janela de ajuda do plugin"""
        from .ui.help_dialog import HelpDialog
        dlg = HelpDialog(self.iface.mainWindow())
        dlg.exec_()
        
    def abrir_analise_impermeabilidade(self):
        """Abre ferramenta de análise de impermeabilidade"""
        from .ui.impermeabilidade_dialog import ImpermeabilidadeDialog
        dlg = ImpermeabilidadeDialog(self.iface, self.iface.mainWindow())
        dlg.exec_()
