# -*- coding: utf-8 -*-
import os

class SuiteRacionalPro:
    def __init__(self, iface):
        self.iface = iface
        
        # Importar as classes dos plugins individuais
        # Usamos importação relativa para suportar renomeação da pasta raiz (ex: Suite_Racional-main)
        try:
            from .metodo_racional_pro.plugin_main import MetodoRacionalPro
            from .mdt_qgis_plugin.mdt_plugin import MDTPlugin
            from .medir_3d.medir_3d import Medir3DPlugin
            
            # Instanciar cada plugin
            self.plugins = [
                MetodoRacionalPro(self.iface),
                MDTPlugin(self.iface),
                Medir3DPlugin(self.iface)
            ]
        except ImportError as e:
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(f"Erro ao carregar Suite Racional: {str(e)}", "Suite Racional", level=Qgis.Critical)
            self.plugins = []

    def initGui(self):
        for plugin in self.plugins:
            try:
                plugin.initGui()
            except Exception as e:
                print(f"Erro ao inicializar GUI do plugin {plugin}: {e}")

    def unload(self):
        for plugin in self.plugins:
            try:
                plugin.unload()
            except Exception as e:
                print(f"Erro ao descarregar plugin {plugin}: {e}")
