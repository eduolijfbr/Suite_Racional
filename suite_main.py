# -*- coding: utf-8 -*-
import os

class SuiteRacionalPro:
    def __init__(self, iface):
        self.iface = iface
        self.plugins = []
        
        # O QGIS carrega este arquivo como parte de um pacote cuja raiz 
        # pode ter nomes variados (Suite_Racional, Suite_Racional-main, etc).
        # Usamos importação relativa para garantir que os módulos internos sejam encontrados
        # independentemente do nome da pasta raiz.
        try:
            from .metodo_racional_pro.plugin_main import MetodoRacionalPro
            self.plugins.append(MetodoRacionalPro(self.iface))
        except Exception as e:
            self._log_error(f"Erro ao carregar Metodo Racional Pro: {str(e)}")

        try:
            from .mdt_qgis_plugin.mdt_plugin import MDTPlugin
            self.plugins.append(MDTPlugin(self.iface))
        except Exception as e:
            self._log_error(f"Erro ao carregar Gerador de MDT: {str(e)}")

        try:
            from .medir_3d.medir_3d import Medir3DPlugin
            self.plugins.append(Medir3DPlugin(self.iface))
        except Exception as e:
            self._log_error(f"Erro ao carregar Medir 3D: {str(e)}")

    def _log_error(self, message):
        from qgis.core import QgsMessageLog, Qgis
        QgsMessageLog.logMessage(message, "Suite Racional Pro", level=Qgis.Critical)

    def initGui(self):
        for plugin in self.plugins:
            try:
                plugin.initGui()
            except Exception as e:
                self._log_error(f"Erro ao inicializar GUI: {str(e)}")

    def unload(self):
        for plugin in self.plugins:
            try:
                plugin.unload()
            except Exception as e:
                pass
