from qgis.PyQt.QtCore import Qt
from qgis.core import QgsProject, QgsMapLayerType

class QgisSmartDockSkill:
    def __init__(self, iface, plugin_name, ui_instance, layer_type_required=None):
        """
        Skill adaptada para receber a instância do DockWidget do Racional Pro.
        :param layer_type_required: Tipo de camada necessária (ex: QgsMapLayerType.RasterLayer)
        """
        self.iface = iface
        self.plugin_name = plugin_name
        self.ui = ui_instance
        self.layer_type_req = layer_type_required
        self.dock_widget = self.ui

    def setup_dock(self, area=Qt.RightDockWidgetArea):
        self.iface.addDockWidget(area, self.dock_widget)
        
        # Conecta o monitoramento do projeto
        QgsProject.instance().layersAdded.connect(self.validate_environment)
        QgsProject.instance().layersRemoved.connect(self.validate_environment)
        
        # Executa a primeira validação
        self.validate_environment()
        
        return self.dock_widget

    def validate_environment(self, *args):
        """
        Verifica se os pré-requisitos para o plugin funcionar estão no mapa.
        No Método Racional, precisamos de MDT (Raster) e Área (Polígono).
        """
        if not self.ui:
            return

        layers = QgsProject.instance().mapLayers().values()
        
        has_raster = any(l.type() == QgsMapLayerType.RasterLayer for l in layers)
        has_vector = any(l.type() == QgsMapLayerType.VectorLayer for l in layers)
        
        can_calculate = has_raster and has_vector
        
        # Habilitar/desabilitar botão de extração na UI do Racional Pro
        if hasattr(self.ui, 'btnExtrairParametros'):
            self.ui.btnExtrairParametros.setEnabled(can_calculate)
            
            # Feedback visual no título do DockWidget
            if can_calculate:
                status = "Pronto para Extração"
            elif has_vector and not has_raster:
                status = "Aguardando MDT (Raster)..."
            elif has_raster and not has_vector:
                status = "Aguardando Área (Vetor)..."
            else:
                status = "Aguardando MDT e Área..."
                
            self.dock_widget.setWindowTitle(f"{self.plugin_name} ({status})")

    def toggle_visibility(self):
        if self.dock_widget:
            if self.dock_widget.isVisible():
                self.dock_widget.hide()
            else:
                self.dock_widget.show()
                self.validate_environment() # Valida ao abrir
