"""
MDT Generator Plugin for QGIS
Generates MDT/MDS from contour line layers using GDAL Grid (Delaunay TIN).
100% QGIS-native — no external dependencies.
"""
import os
import time
import traceback

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction, QFileDialog, QDockWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QDoubleSpinBox, QPushButton, QProgressBar,
    QMessageBox, QWidget, QScrollArea
)

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer,
    QgsApplication, QgsMessageLog, Qgis,
    QgsFeatureRequest, QgsCoordinateTransform
)

from .mdt_algorithm import MDTAlgorithm


def log(msg, level=Qgis.Info):
    QgsMessageLog.logMessage(str(msg), "MDT Plugin", level=level)


class MDTPluginDialog(QDockWidget):
    """DockWidget for MDT generation parameters."""

    def __init__(self, iface, parent=None):
        super().__init__("MDT Generator", parent)
        self.iface = iface
        self.setObjectName("MDTGeneratorDock")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        
        # Widget principal
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        
        self.output_path = ""
        self._setup_ui()
        self.populate_layers()
        
        # Usar Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.main_widget)
        self.setWidget(scroll_area)

    def _setup_ui(self):
        # Layer Selection
        self.main_layout.addWidget(QLabel("Camada de Curvas de Nível:"))
        self.cboLayer = QComboBox()
        self.main_layout.addWidget(self.cboLayer)

        # Z Field Selection
        self.main_layout.addWidget(QLabel("Campo Z/Elevação:"))
        self.cboZField = QComboBox()
        self.main_layout.addWidget(self.cboZField)
        self.cboLayer.currentIndexChanged.connect(self._on_layer_changed)

        # Resolution
        self.main_layout.addWidget(QLabel("Resolução do Grid (m):"))
        self.spnResolution = QDoubleSpinBox()
        self.spnResolution.setValue(1.0)
        self.spnResolution.setMinimum(0.1)
        self.spnResolution.setMaximum(100.0)
        self.spnResolution.setDecimals(1)
        self.spnResolution.setSingleStep(0.5)
        self.main_layout.addWidget(self.spnResolution)

        # Output File
        self.main_layout.addWidget(QLabel("Arquivo de Saída (GeoTIFF):"))
        h_layout = QHBoxLayout()
        self.lblOutput = QLabel("Nenhum arquivo selecionado")
        h_layout.addWidget(self.lblOutput)
        self.btnSelectOutput = QPushButton("...")
        self.btnSelectOutput.setMaximumWidth(40)
        self.btnSelectOutput.clicked.connect(self.select_output)
        h_layout.addWidget(self.btnSelectOutput)
        self.main_layout.addLayout(h_layout)

        # Run Button
        self.btnRun = QPushButton("Gerar MDT")
        self.btnRun.clicked.connect(self.run_process)
        self.main_layout.addWidget(self.btnRun)

        # Progress Bar
        self.progressBar = QProgressBar()
        self.progressBar.setValue(0)
        self.main_layout.addWidget(self.progressBar)

        # Status Label
        self.lblStatus = QLabel("")
        self.lblStatus.setWordWrap(True)
        self.main_layout.addWidget(self.lblStatus)


    def populate_layers(self):
        self.cboLayer.clear()
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                geom_type = layer.geometryType()
                if geom_type == 1:  # LineGeometry
                    self.cboLayer.addItem(layer.name(), layer.id())

        if self.cboLayer.count() == 0:
            self.lblStatus.setText("⚠ Nenhuma camada de linhas encontrada.")
        else:
            self._on_layer_changed()

    def _on_layer_changed(self):
        self.cboZField.clear()
        layer = self._get_selected_layer()
        if not layer:
            return

        candidates = ['cota', 'elevation', 'elev', 'z', 'alt', 'nivel', 'height']
        selected_idx = 0
        for i, field in enumerate(layer.fields()):
            self.cboZField.addItem(field.name(), i)
            if field.name().lower() in candidates and selected_idx == 0:
                selected_idx = self.cboZField.count() - 1

        if selected_idx > 0:
            self.cboZField.setCurrentIndex(selected_idx)

    def _get_selected_layer(self):
        layer_id = self.cboLayer.currentData()
        if layer_id:
            return QgsProject.instance().mapLayer(layer_id)
        return None

    def select_output(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Salvar MDT", "", "GeoTIFF (*.tif)")
        if filename:
            if not filename.endswith('.tif'):
                filename += '.tif'
            self.output_path = filename
            self.lblOutput.setText(filename)

    def _update_progress(self, pct, msg):
        """Update UI during synchronous processing."""
        self.progressBar.setValue(int(pct))
        self.lblStatus.setText(msg)
        QgsApplication.processEvents()

    def run_process(self):
        layer = self._get_selected_layer()
        resolution = self.spnResolution.value()
        z_field_name = self.cboZField.currentText()

        if not layer:
            QMessageBox.warning(self, "Erro", "Nenhuma camada selecionada.")
            return
        if not self.output_path:
            QMessageBox.warning(self, "Erro", "Nenhum arquivo de saída selecionado.")
            return
        if not z_field_name:
            QMessageBox.warning(self, "Erro", "Nenhum campo Z selecionado.")
            return

        self.btnRun.setEnabled(False)
        self.progressBar.setValue(0)

        try:
            # ---- Step 1: Get canvas extent ----
            self._update_progress(1, "Obtendo extensão da tela...")

            canvas = self.iface.mapCanvas()
            canvas_extent = canvas.extent()
            canvas_crs = canvas.mapSettings().destinationCrs()
            layer_crs = layer.crs()

            if canvas_crs != layer_crs:
                transform = QgsCoordinateTransform(
                    canvas_crs, layer_crs, QgsProject.instance()
                )
                filter_rect = transform.transformBoundingBox(canvas_extent)
            else:
                filter_rect = canvas_extent

            log(f"Canvas extent: [{filter_rect.xMinimum():.2f}, "
                f"{filter_rect.yMinimum():.2f}, "
                f"{filter_rect.xMaximum():.2f}, "
                f"{filter_rect.yMaximum():.2f}]")

            # ---- Step 2: Extract points from visible features ----
            self._update_progress(2, "Extraindo pontos das curvas visíveis...")
            t_extract_start = time.time()

            z_field_idx = layer.fields().indexFromName(z_field_name)
            if z_field_idx == -1:
                raise Exception(f"Campo '{z_field_name}' não encontrado.")

            request = QgsFeatureRequest()
            request.setFilterRect(filter_rect)

            # Adaptive densification: proportional to resolution (min 0.5m)
            densify_dist = max(resolution * 0.5, 0.5)

            total = layer.featureCount()
            points_xyz = []
            feat_count = 0
            skipped = 0

            # Inline bounding box tracking during extraction
            data_xmin, data_ymin = float('inf'), float('inf')
            data_xmax, data_ymax = float('-inf'), float('-inf')

            for i, feat in enumerate(layer.getFeatures(request)):
                if i % 100 == 0:
                    if progress_fn:
                        pct = int(2 + (i / max(total, 1)) * 28)
                        progress_fn(pct, f"Extraindo feição {i}... ({len(points_xyz)} pts)")

                geom = feat.geometry()
                if not geom or geom.isEmpty():
                    skipped += 1
                    continue

                attr = feat.attributes()
                if len(attr) <= z_field_idx:
                    skipped += 1
                    continue
                    
                z_val = attr[z_field_idx]
                try:
                    z_val = float(z_val)
                except (ValueError, TypeError):
                    skipped += 1
                    continue

                # Optimize: only densify if really needed or if it's a long segment
                # But for simplicity and TIN quality, densification is good.
                densified = geom.densifyByDistance(densify_dist)
                
                # Faster vertex extraction
                for v in densified.vertices():
                    x, y = v.x(), v.y()
                    points_xyz.append((x, y, z_val))
                    if x < data_xmin: data_xmin = x
                    if y < data_ymin: data_ymin = y
                    if x > data_xmax: data_xmax = x
                    if y > data_ymax: data_ymax = y

                feat_count += 1

            t_extract = time.time() - t_extract_start
            log(f"Extração: {t_extract:.2f}s — {feat_count} feições, "
                f"{len(points_xyz)} pontos, {skipped} ignorados "
                f"(densificação: {densify_dist:.1f}m)")

            if not points_xyz:
                raise Exception(
                    f"Nenhum ponto extraído da tela visível.\n\n"
                    f"Verifique se:\n"
                    f"- Existem curvas visíveis na tela\n"
                    f"- O campo '{z_field_name}' contém valores numéricos\n"
                    f"- A camada não está vazia na extensão atual"
                )

            # ---- Step 3: Compute data-driven extent ----
            self._update_progress(30, "Calculando extensão otimizada...")

            # Buffer: 2x resolution to avoid edge artifacts in TIN
            buf = resolution * 2.0
            data_xmin -= buf
            data_ymin -= buf
            data_xmax += buf
            data_ymax += buf

            # Intersect with canvas to never exceed visible area
            final_xmin = max(data_xmin, filter_rect.xMinimum())
            final_ymin = max(data_ymin, filter_rect.yMinimum())
            final_xmax = min(data_xmax, filter_rect.xMaximum())
            final_ymax = min(data_ymax, filter_rect.yMaximum())

            # Performance metric: area reduction
            canvas_area = ((filter_rect.xMaximum() - filter_rect.xMinimum()) *
                           (filter_rect.yMaximum() - filter_rect.yMinimum()))
            data_area = (final_xmax - final_xmin) * (final_ymax - final_ymin)
            if canvas_area > 0:
                reduction = (1.0 - data_area / canvas_area) * 100.0
                log(f"Área reduzida: {canvas_area:.0f}m² → {data_area:.0f}m² "
                    f"({reduction:.1f}% economia)")

            extent_data = (
                final_xmin, final_ymin,
                final_xmax, final_ymax
            )
            crs_wkt = layer_crs.toWkt()

            # ---- Step 4: Run algorithm (GDAL Grid) ----
            self._update_progress(35, "Iniciando interpolação GDAL...")
            t_grid_start = time.time()

            algo = MDTAlgorithm()
            result = algo.process(
                points_xyz,
                extent_data,
                resolution,
                self.output_path,
                crs_wkt,
                progress_fn=self._update_progress
            )

            t_grid = time.time() - t_grid_start
            log(f"Interpolação GDAL: {t_grid:.2f}s")

            # Dump algorithm logs
            for msg in algo.log_messages:
                log(msg)

            if not result:
                raise Exception("Algoritmo retornou falso sem exceção.")

            # ---- Step 5: Load result ----
            self._update_progress(100, "✅ MDT gerado com sucesso!")

            if os.path.exists(self.output_path):
                basename = os.path.splitext(os.path.basename(self.output_path))[0]
                rlayer = QgsRasterLayer(self.output_path, basename)
                if rlayer.isValid():
                    QgsProject.instance().addMapLayer(rlayer)
                    log(f"Raster carregado: {self.output_path}")
                else:
                    log(f"Raster inválido: {self.output_path}", level=Qgis.Warning)

            QMessageBox.information(self, "Sucesso", "MDT gerado com sucesso!")

        except Exception as e:
            error_detail = str(e)
            if not error_detail:
                error_detail = repr(e)

            tb = traceback.format_exc()
            log(f"ERRO: {error_detail}\n{tb}", level=Qgis.Critical)

            self.lblStatus.setText(f"❌ Erro: {error_detail[:120]}")
            QMessageBox.critical(self, "Erro na Geração do MDT",
                f"A geração do MDT falhou.\n\n"
                f"Detalhes: {error_detail}\n\n"
                f"Log completo em: View > Log Messages > MDT Plugin")

        finally:
            self.btnRun.setEnabled(True)


class MDTPlugin:
    """Main plugin class."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.menu = "&Suite Racional Pro"
        self.toolbar_name = "SuiteRacionalPro"
        self.toolbar = None

    def initGui(self):
        from qgis.PyQt.QtWidgets import QToolBar
        icon_path = os.path.join(self.plugin_dir, 'icon.svg')
        self.action = QAction(
            QIcon(icon_path), "Gerar MDT/MDS", self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, self.toolbar_name)
        if not self.toolbar:
            self.toolbar = self.iface.addToolBar('Suite Racional Pro')
            self.toolbar.setObjectName(self.toolbar_name)
            
        self.toolbar.addAction(self.action)
        self.iface.addPluginToMenu(self.menu, self.action)

    def unload(self):
        self.iface.removePluginMenu(self.menu, self.action)
        if self.toolbar:
            self.toolbar.removeAction(self.action)
        if hasattr(self, 'dlg') and self.dlg:
            self.iface.removeDockWidget(self.dlg)
            self.dlg.close()
            self.dlg = None

    def run(self):
        if not hasattr(self, 'dlg') or self.dlg is None:
            self.dlg = MDTPluginDialog(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dlg)
        
        if self.dlg.isVisible():
            self.dlg.hide()
        else:
            self.dlg.show()
