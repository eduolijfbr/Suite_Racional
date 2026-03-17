# -*- coding: utf-8 -*-
"""
Dialog para Análise de Impermeabilidade do Solo
Ferramenta independente acessível pelo menu de plugins
Usa implementação 100% nativa do QGIS
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QGroupBox,
    QMessageBox, QFileDialog, QFrame, QScrollArea, QApplication
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QFont, QImage, QPixmap, QPainter, QColor

from qgis.core import (
    QgsProject, QgsRasterLayer, QgsVectorLayer,
    QgsMessageLog, Qgis, QgsWkbTypes, QgsGeometry
)

import numpy as np
import os
import traceback

from .persistence_manager import PersistenceManager


class ImpermeabilidadeDialog(QDialog):
    """Dialog para análise de impermeabilidade do solo baseada em imagem raster"""
    
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.iface = iface
        self.resultados = None
        self.setup_ui()
        self.carregar_camadas()
        
        # Conectar sinais de mudança nas camadas para auto-carregamento por feição
        self.cmbPoligono.currentIndexChanged.connect(self.on_poligono_changed)
        
        self.carregar_estado_salvo()
        
    def setup_ui(self):
        """Configura interface do usuário"""
        self.setWindowTitle("Análise de Impermeabilidade do Solo")
        self.setMinimumSize(800, 700)
        self.resize(900, 750)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # === Cabeçalho ===
        header = QFrame()
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1976D2, stop:1 #42A5F5);
                border-radius: 8px;
                padding: 15px;
            }
        """)
        header_layout = QVBoxLayout(header)
        
        titulo = QLabel("🏗️ Análise de Impermeabilidade do Solo")
        titulo.setFont(QFont("Arial", 16, QFont.Bold))
        titulo.setStyleSheet("color: white;")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(titulo)
        
        subtitulo = QLabel("Classificação ternária de pixels: Impermeável | Vegetação | Sombra/Água")
        subtitulo.setStyleSheet("color: #E3F2FD; font-size: 11px;")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitulo)
        
        layout.addWidget(header)
        
        # === Seleção de Camadas ===
        grp_camadas = QGroupBox("1. Selecione as Camadas")
        grp_camadas.setStyleSheet("QGroupBox { font-weight: bold; }")
        grid_camadas = QGridLayout(grp_camadas)
        
        grid_camadas.addWidget(QLabel("Imagem Raster (RGB):"), 0, 0)
        self.cmbRaster = QComboBox()
        self.cmbRaster.setMinimumWidth(400)
        self.cmbRaster.setToolTip("Selecione a imagem de satélite ou ortofoto (deve ter 3+ bandas RGB)")
        grid_camadas.addWidget(self.cmbRaster, 0, 1)
        
        self.btnAtualizarRaster = QPushButton("🔄")
        self.btnAtualizarRaster.setFixedWidth(30)
        self.btnAtualizarRaster.setToolTip("Atualizar lista de camadas")
        self.btnAtualizarRaster.clicked.connect(self.carregar_camadas)
        grid_camadas.addWidget(self.btnAtualizarRaster, 0, 2)
        
        grid_camadas.addWidget(QLabel("Área de Estudo (Polígono):"), 1, 0)
        self.cmbPoligono = QComboBox()
        self.cmbPoligono.setMinimumWidth(400)
        self.cmbPoligono.setToolTip("Selecione a camada vetorial com a área de estudo")
        grid_camadas.addWidget(self.cmbPoligono, 1, 1)
        
        layout.addWidget(grp_camadas)
        
        # === Botão de Cálculo ===
        self.btnCalcular = QPushButton("⚡ CALCULAR IMPERMEABILIDADE")
        self.btnCalcular.setMinimumHeight(50)
        self.btnCalcular.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 8px;
                padding: 15px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.btnCalcular.clicked.connect(self.executar_calculo)
        layout.addWidget(self.btnCalcular)
        
        # === Resultados ===
        grp_resultados = QGroupBox("2. Resultados")
        grp_resultados.setStyleSheet("QGroupBox { font-weight: bold; }")
        grid_resultados = QGridLayout(grp_resultados)
        
        # Coeficiente
        grid_resultados.addWidget(QLabel("Coeficiente (C):"), 0, 0)
        self.txtCoeficiente = QLineEdit()
        self.txtCoeficiente.setReadOnly(True)
        self.txtCoeficiente.setPlaceholderText("0.0000")
        self.txtCoeficiente.setStyleSheet("""
            font-weight: bold; 
            font-size: 18px; 
            background-color: #E8F5E9;
            padding: 8px;
            border: 2px solid #4CAF50;
            border-radius: 5px;
        """)
        self.txtCoeficiente.setMaximumWidth(150)
        grid_resultados.addWidget(self.txtCoeficiente, 0, 1)
        
        # Percentual
        self.lblPercentual = QLabel("---%")
        self.lblPercentual.setFont(QFont("Arial", 24, QFont.Bold))
        self.lblPercentual.setStyleSheet("color: #1976D2;")
        grid_resultados.addWidget(self.lblPercentual, 0, 2)
        
        # Status
        self.lblStatus = QLabel("Aguardando cálculo...")
        self.lblStatus.setStyleSheet("color: #757575; font-style: italic;")
        self.lblStatus.setWordWrap(True)
        grid_resultados.addWidget(self.lblStatus, 1, 0, 1, 3)
        
        layout.addWidget(grp_resultados)
        
        # === Detalhes (Expandível) ===
        self.grpDetalhes = QGroupBox("3. Detalhes da Análise (clique para expandir)")
        self.grpDetalhes.setCheckable(True)
        self.grpDetalhes.setChecked(False)
        self.grpDetalhes.toggled.connect(self.toggle_detalhes)
        self.grpDetalhes.setStyleSheet("QGroupBox { font-weight: bold; }")
        
        detalhes_layout = QVBoxLayout(self.grpDetalhes)
        
        # Área de imagem
        self.scrollImagem = QScrollArea()
        self.scrollImagem.setWidgetResizable(True)
        self.scrollImagem.setMinimumHeight(250)
        self.scrollImagem.setStyleSheet("background-color: #FAFAFA; border: 1px solid #E0E0E0;")
        
        self.lblImagem = QLabel("A imagem de classificação aparecerá aqui após o cálculo.")
        self.lblImagem.setAlignment(Qt.AlignCenter)
        self.lblImagem.setStyleSheet("color: #9E9E9E;")
        self.scrollImagem.setWidget(self.lblImagem)
        
        detalhes_layout.addWidget(self.scrollImagem)
        
        # Estatísticas
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: #F5F5F5; border-radius: 5px; padding: 10px;")
        stats_layout = QGridLayout(stats_frame)
        
        self.stats_labels = {}
        stats_items = [
            ("Total de Pixels:", "total", 0, 0),
            ("Impermeável:", "impermeavel", 1, 0),
            ("Vegetação:", "vegetacao", 2, 0),
            ("Sombra/Água:", "sombra", 3, 0),
        ]
        
        for label_text, key, row, col in stats_items:
            lbl = QLabel(label_text)
            lbl.setFont(QFont("Arial", 10))
            stats_layout.addWidget(lbl, row, col)
            
            val_lbl = QLabel("---")
            val_lbl.setFont(QFont("Arial", 10, QFont.Bold))
            stats_layout.addWidget(val_lbl, row, col + 1)
            self.stats_labels[key] = val_lbl
            
        # Legenda de cores
        legenda_layout = QHBoxLayout()
        legenda_layout.addWidget(QLabel("Legenda:"))
        
        cores = [
            ("#505050", "Impermeável"),
            ("#228B22", "Vegetação"),
            ("#1E90FF", "Sombra/Água"),
        ]
        for cor, texto in cores:
            lbl = QLabel(f"  {texto}  ")
            lbl.setStyleSheet(f"background-color: {cor}; color: white; border-radius: 3px; padding: 2px 5px;")
            legenda_layout.addWidget(lbl)
        legenda_layout.addStretch()
        
        stats_layout.addLayout(legenda_layout, 4, 0, 1, 2)
        
        detalhes_layout.addWidget(stats_frame)
        
        # Inicialmente oculto
        self.scrollImagem.hide()
        stats_frame.hide()
        self.stats_frame = stats_frame
        
        layout.addWidget(self.grpDetalhes)
        
        # === Botões de Exportação ===
        export_layout = QHBoxLayout()
        
        self.btnSalvarImagem = QPushButton("💾 Salvar Imagem")
        self.btnSalvarImagem.setEnabled(False)
        self.btnSalvarImagem.clicked.connect(self.salvar_imagem)
        export_layout.addWidget(self.btnSalvarImagem)
        
        self.btnSalvarRelatorio = QPushButton("📄 Salvar Relatório")
        self.btnSalvarRelatorio.setEnabled(False)
        self.btnSalvarRelatorio.clicked.connect(self.salvar_relatorio)
        export_layout.addWidget(self.btnSalvarRelatorio)
        
        export_layout.addStretch()
        
        self.btnFechar = QPushButton("Fechar")
        self.btnFechar.setMinimumWidth(100)
        self.btnFechar.clicked.connect(self.close)
        export_layout.addWidget(self.btnFechar)
        
        layout.addLayout(export_layout)
            
    def toggle_detalhes(self, checked):
        """Mostra/oculta seção de detalhes"""
        self.scrollImagem.setVisible(checked)
        self.stats_frame.setVisible(checked)
        
        if checked:
            self.grpDetalhes.setTitle("3. Detalhes da Análise")
        else:
            self.grpDetalhes.setTitle("3. Detalhes da Análise (clique para expandir)")

    def _obter_output_dir(self):
        """Obtém diretório de saída para resultados (subpasta do projeto)"""
        try:
            projeto = QgsProject.instance()
            projeto_path = projeto.fileName()
            
            if projeto_path:
                output_dir = os.path.dirname(projeto_path)
                return os.path.join(output_dir, "impermeabilidade_resultados")
            else:
                import tempfile
                return os.path.join(tempfile.gettempdir(), "metodo_racional_pro", "impermeabilidade_resultados")
        except:
            import tempfile
            return os.path.join(tempfile.gettempdir(), "metodo_racional_pro", "impermeabilidade_resultados")

    def salvar_imagens_em_disco(self):
        """Salva as imagens do cálculo atual em disco automaticamente"""
        if not self.resultados or 'rgb_image' not in self.resultados:
            return
            
        try:
            output_dir = self._obter_output_dir()
            os.makedirs(output_dir, exist_ok=True)
            
            from ..processamento.impermeabilidade_qgis import (
                salvar_imagem_original,
                salvar_imagem_classificacao_simples
            )
            
            # Salvar Imagem Original
            path_orig = salvar_imagem_original(
                self.resultados['rgb_image'],
                self.resultados['valid_mask'],
                output_dir
            )
            
            # Salvar Imagem Classificada
            path_class = salvar_imagem_classificacao_simples(
                self.resultados['rgb_image'],
                self.resultados['classification_map'],
                self.resultados['valid_mask'],
                output_dir
            )
            
            if path_orig: self.resultados['impermeabilidade_imagem_original'] = path_orig
            if path_class: self.resultados['impermeabilidade_imagem'] = path_class
            
        except Exception as e:
            QgsMessageLog.logMessage(f"Erro ao auto-salvar imagens: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)

    def on_poligono_changed(self, index):
        """Chamado quando a camada de polígonos muda"""
        # Desconectar sinal da camada anterior para evitar múltiplas chamadas
        if hasattr(self, '_current_layer_selection_conn') and self._current_layer_selection_conn:
            try:
                self._current_layer_selection_conn.selectionChanged.disconnect(self.carregar_estado_salvo)
            except: pass
            
        layer = self.cmbPoligono.currentData()
        if layer:
            layer.selectionChanged.connect(self.carregar_estado_salvo)
            self._current_layer_selection_conn = layer
        else:
            self._current_layer_selection_conn = None
            
        self.carregar_estado_salvo()
            
    def salvar_estado_atual(self):
        """Salva estado atual do diálogo no projeto QGIS"""
        try:
            # Garantir que imagens estão em disco
            self.salvar_imagens_em_disco()
            
            # Coletar caminhos de imagens se houver
            img_path = self.resultados.get('impermeabilidade_imagem') if self.resultados else None
            img_orig_path = self.resultados.get('impermeabilidade_imagem_original') if self.resultados else None
            rel_path = self.resultados.get('impermeabilidade_relatorio') if self.resultados else None
            
            state = {
                'raster_layer': self.cmbRaster.currentText() if self.cmbRaster.currentIndex() > 0 else '',
                'polygon_layer': self.cmbPoligono.currentText() if self.cmbPoligono.currentIndex() > 0 else '',
                'resultados_scallar': {
                    'coeficiente': self.resultados.get('coeficiente') if self.resultados else None,
                    'percentual': self.resultados.get('percentual') if self.resultados else None,
                    'total_pixels': self.resultados.get('total_pixels') if self.resultados else None,
                    'impermeable_pixels': self.resultados.get('impermeable_pixels') if self.resultados else None,
                    'vegetation_pixels': self.resultados.get('vegetation_pixels') if self.resultados else None,
                    'shadow_pixels': self.resultados.get('shadow_pixels') if self.resultados else None,
                    'percent_vegetation': self.resultados.get('percent_vegetation') if self.resultados else None,
                    'percent_shadow': self.resultados.get('percent_shadow') if self.resultados else None,
                } if self.resultados else None,
                'img_path': img_path,
                'img_orig_path': img_orig_path,
                'rel_path': rel_path
            }
            
            # Salvar globalmente
            PersistenceManager.save_impermeability_state(state)
            
            # Salvar por feição se houver seleção
            layer = self.cmbPoligono.currentData()
            if layer:
                feature_id = PersistenceManager.get_current_feature_id(layer)
                if feature_id:
                    PersistenceManager.save_feature_data(feature_id, f"imper_{layer.name()}", state)
                    
        except Exception as e:
            QgsMessageLog.logMessage(f"Erro ao salvar estado de impermeabilidade: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)

    def carregar_estado_salvo(self):
        """Carrega estado salvo do projeto QGIS (Global ou por Feição)"""
        try:
            layer = self.cmbPoligono.currentData()
            state = None
            
            if layer:
                feature_id = PersistenceManager.get_current_feature_id(layer)
                if feature_id:
                    state = PersistenceManager.load_feature_data(feature_id, f"imper_{layer.name()}")
            
            if not state:
                state = PersistenceManager.load_impermeability_state()
                
            if not state:
                # Resetar campos se não houver estado
                self.txtCoeficiente.clear()
                self.lblPercentual.setText("---%")
                self.lblStatus.setText("Aguardando cálculo...")
                self.resultados = None
                self.lblImagem.clear()
                self.lblImagem.setText("A imagem de classificação aparecerá aqui após o cálculo.")
                return
            
            # Restaurar combos (apenas se for carga global ou se a camada bater)
            self.cmbRaster.blockSignals(True)
            idx_raster = self.cmbRaster.findText(state.get('raster_layer', ''))
            if idx_raster >= 0: self.cmbRaster.setCurrentIndex(idx_raster)
            self.cmbRaster.blockSignals(False)
            
            # Restaurar resultados
            res_scallar = state.get('resultados_scallar')
            if res_scallar:
                self.resultados = res_scallar
                
                coef = res_scallar.get('coeficiente')
                perc = res_scallar.get('percentual')
                
                if coef is not None:
                    self.txtCoeficiente.setText(f"{coef:.4f}")
                    self.lblPercentual.setText(f"{perc:.2f}%")
                    self.lblStatus.setText(f"✅ Resultados recuperados.")
                    self.lblStatus.setStyleSheet("color: #4CAF50;")
                    
                    self.atualizar_estatisticas()
                    
                    img_path = state.get('img_path')
                    img_orig_path = state.get('img_orig_path')
                    
                    # Atualizar dicionário de resultados com os caminhos carregados
                    self.resultados['impermeabilidade_imagem'] = img_path
                    self.resultados['impermeabilidade_imagem_original'] = img_orig_path
                    
                    if img_path and os.path.exists(img_path):
                        pixmap = QPixmap(img_path)
                        if not pixmap.isNull():
                            self.lblImagem.setPixmap(pixmap)
                            self.btnSalvarImagem.setEnabled(True)
                            self.btnSalvarRelatorio.setEnabled(True)
                            self.grpDetalhes.setChecked(True)
                        else:
                            self.lblImagem.setText("Imagem salva não encontrada.")
                    else:
                        self.lblImagem.setText("Imagem não disponível para feição selecionada.")
        except Exception as e:
            QgsMessageLog.logMessage(f"Erro ao carregar estado de impermeabilidade: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)
            
    def carregar_camadas(self):
        """Carrega camadas disponíveis no projeto"""
        self.cmbRaster.clear()
        self.cmbPoligono.clear()
        
        self.cmbRaster.addItem("-- Selecione uma imagem raster --", None)
        self.cmbPoligono.addItem("-- Selecione uma camada de polígonos --", None)
        
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsRasterLayer):
                self.cmbRaster.addItem(f"🗺️ {layer.name()}", layer)
            elif isinstance(layer, QgsVectorLayer):
                if layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                    self.cmbPoligono.addItem(f"📐 {layer.name()}", layer)
                    
    def executar_calculo(self):
        """Executa o cálculo de impermeabilidade"""
        # Validar seleções
        layer_raster = self.cmbRaster.currentData()
        layer_poligono = self.cmbPoligono.currentData()
        
        if layer_raster is None:
            QMessageBox.warning(self, "Atenção", "Selecione uma imagem raster.")
            return
            
        if layer_poligono is None:
            QMessageBox.warning(self, "Atenção", "Selecione uma camada de polígonos para a área de estudo.")
            return
            
        # Obter geometria
        geometria = self.obter_geometria_unificada(layer_poligono)
        if geometria is None:
            QMessageBox.warning(self, "Atenção", "A camada de polígonos não contém feições válidas.")
            return
            
        # Atualizar status
        self.lblStatus.setText("⏳ Calculando... Por favor, aguarde.")
        self.lblStatus.setStyleSheet("color: #FF9800;")
        self.btnCalcular.setEnabled(False)
        self.setCursor(Qt.CursorShape.WaitCursor)
        
        # Forçar atualização da UI
        QApplication.processEvents()
        
        try:
            # Importar módulo nativo QGIS
            from ..processamento.impermeabilidade_qgis import calcular_impermeabilidade_qgis
            
            source_crs = layer_poligono.crs()
            
            # Executar cálculo
            self.resultados = calcular_impermeabilidade_qgis(
                layer_raster,
                geometria,
                source_crs=source_crs
            )
            
            if self.resultados is None:
                self.lblStatus.setText("⚠️ A área de estudo não sobrepõe a imagem ou não contém pixels válidos.")
                self.lblStatus.setStyleSheet("color: #F44336;")
                self.txtCoeficiente.setText("")
                self.lblPercentual.setText("---%")
                return
                
            # Exibir resultados
            coef = self.resultados['coeficiente']
            perc = self.resultados['percentual']
            
            self.txtCoeficiente.setText(f"{coef:.4f}")
            self.lblPercentual.setText(f"{perc:.2f}%")
            
            self.lblStatus.setText(f"✅ Cálculo concluído! Impermeabilidade: {perc:.2f}%")
            self.lblStatus.setStyleSheet("color: #4CAF50;")
            
            # Atualizar estatísticas
            self.atualizar_estatisticas()
            
            # Gerar imagem de visualização
            self.gerar_imagem_visualizacao()
            
            # Habilitar botões de exportação
            self.btnSalvarImagem.setEnabled(True)
            self.btnSalvarRelatorio.setEnabled(True)
            
            # Expandir detalhes automaticamente
            self.grpDetalhes.setChecked(True)
            
            # Salvar estado automaticamente após cálculo
            self.salvar_estado_atual()
            
        except Exception as e:
            erro_msg = str(e)
            self.lblStatus.setText(f"❌ Erro: {erro_msg}")
            self.lblStatus.setStyleSheet("color: #F44336;")
            
            QgsMessageLog.logMessage(
                f"Erro no cálculo de impermeabilidade: {erro_msg}\n{traceback.format_exc()}",
                'MetodoRacionalPro',
                Qgis.Critical
            )
            
            QMessageBox.critical(
                self, "Erro",
                f"Ocorreu um erro durante o cálculo:\n\n{erro_msg}\n\n"
                "Verifique se a imagem e a área de estudo estão corretas."
            )
            
        finally:
            self.btnCalcular.setEnabled(True)
            self.setCursor(Qt.CursorShape.ArrowCursor)
            
    def obter_geometria_unificada(self, layer):
        """Obtém geometria unificada de todas as feições da camada"""
        geometrias = []
        
        # Usar feições selecionadas ou todas
        features = layer.selectedFeatures() if layer.selectedFeatureCount() > 0 else layer.getFeatures()
        
        for feature in features:
            geom = feature.geometry()
            if geom and not geom.isEmpty():
                geometrias.append(geom)
                
        if not geometrias:
            return None
            
        if len(geometrias) == 1:
            return geometrias[0]
            
        # Unir geometrias
        try:
            return QgsGeometry.unaryUnion(geometrias)
        except:
            # Fallback: combinar manualmente
            resultado = geometrias[0]
            for g in geometrias[1:]:
                resultado = resultado.combine(g)
            return resultado
            
    def atualizar_estatisticas(self):
        """Atualiza labels de estatísticas"""
        if not self.resultados:
            return
            
        total = self.resultados.get('total_pixels', 0)
        imp = self.resultados.get('impermeable_pixels', 0)
        veg = self.resultados.get('vegetation_pixels', 0)
        shadow = self.resultados.get('shadow_pixels', 0)
        
        perc_imp = self.resultados.get('percentual', 0)
        perc_veg = self.resultados.get('percent_vegetation', 0)
        perc_shadow = self.resultados.get('percent_shadow', 0)
        
        self.stats_labels['total'].setText(f"{total:,}")
        self.stats_labels['impermeavel'].setText(f"{imp:,} ({perc_imp:.2f}%)")
        self.stats_labels['vegetacao'].setText(f"{veg:,} ({perc_veg:.2f}%)")
        self.stats_labels['sombra'].setText(f"{shadow:,} ({perc_shadow:.2f}%)")
        
    def gerar_imagem_visualizacao(self):
        """Gera imagem composta para visualização"""
        if not self.resultados:
            return
            
        try:
            rgb = self.resultados.get('rgb_image')
            classification = self.resultados.get('classification_map')
            valid_mask = self.resultados.get('valid_mask')
            
            if rgb is None or classification is None:
                self.lblImagem.setText("Dados de imagem não disponíveis")
                return
            
            h, w = classification.shape
            
            # Criar imagem RGB usando QImage pixel por pixel (mais lento mas seguro)
            qimg_rgb = QImage(w, h, QImage.Format_RGB888)
            qimg_class = QImage(w, h, QImage.Format_RGB888)
            
            # Cores de classificação
            color_impermeavel = QColor(80, 80, 80)
            color_vegetacao = QColor(34, 139, 34)
            color_sombra = QColor(30, 144, 255)
            color_fundo = QColor(255, 255, 255)
            
            for row in range(h):
                for col in range(w):
                    # RGB original
                    r = int(rgb[0, row, col])
                    g = int(rgb[1, row, col])
                    b = int(rgb[2, row, col])
                    qimg_rgb.setPixelColor(col, row, QColor(r, g, b))
                    
                    # Classificação
                    if valid_mask[row, col]:
                        cls = classification[row, col]
                        if cls == 0:
                            qimg_class.setPixelColor(col, row, color_impermeavel)
                        elif cls == 1:
                            qimg_class.setPixelColor(col, row, color_vegetacao)
                        else:
                            qimg_class.setPixelColor(col, row, color_sombra)
                    else:
                        qimg_class.setPixelColor(col, row, color_fundo)
            
            # Combinar imagens
            gap = 20
            final_width = w * 2 + gap
            final_height = h + 50
            
            pixmap = QPixmap(final_width, final_height)
            pixmap.fill(Qt.GlobalColor.white)
            
            painter = QPainter(pixmap)
            
            # Títulos
            painter.setPen(Qt.GlobalColor.black)
            font = QFont("Arial", 11, QFont.Bold)
            painter.setFont(font)
            painter.drawText(10, 20, "Imagem Original (RGB)")
            painter.drawText(w + gap + 10, 20, "Classificação")
            
            # Desenhar imagens
            painter.drawImage(0, 35, qimg_rgb)
            painter.drawImage(w + gap, 35, qimg_class)
            
            painter.end()
            
            # Exibir no label
            self.lblImagem.setPixmap(pixmap)
            self.lblImagem.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
        except Exception as e:
            self.lblImagem.setText(f"Erro ao gerar visualização: {str(e)}")
            QgsMessageLog.logMessage(
                f"Erro ao gerar imagem: {str(e)}\n{traceback.format_exc()}",
                'MetodoRacionalPro',
                Qgis.Warning
            )
            
    def salvar_imagem(self):
        """Salva imagem de classificação"""
        if not self.resultados:
            QMessageBox.warning(self, "Atenção", "Execute o cálculo primeiro.")
            return
            
        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Imagem de Classificação",
            os.path.expanduser("~/impermeabilidade_classificacao.png"),
            "Imagens PNG (*.png)"
        )
        
        if caminho:
            try:
                from ..processamento.impermeabilidade_qgis import salvar_imagem_classificacao_simples
                
                img_path = salvar_imagem_classificacao_simples(
                    self.resultados['rgb_image'],
                    self.resultados['classification_map'],
                    self.resultados['valid_mask'],
                    os.path.dirname(caminho)
                )
                
                if img_path:
                    # Renomear para o caminho escolhido pelo usuário
                    if os.path.exists(img_path) and img_path != caminho:
                        import shutil
                        shutil.move(img_path, caminho)
                        
                    QMessageBox.information(
                        self, "Sucesso",
                        f"Imagem salva em:\n{caminho}"
                    )
                else:
                    QMessageBox.warning(self, "Aviso", "Não foi possível salvar a imagem.")
                    
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar imagem:\n{str(e)}")
                
    def salvar_relatorio(self):
        """Salva relatório de análise"""
        if not self.resultados:
            QMessageBox.warning(self, "Atenção", "Execute o cálculo primeiro.")
            return
            
        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Relatório de Impermeabilidade",
            os.path.expanduser("~/impermeabilidade_relatorio.txt"),
            "Arquivos de Texto (*.txt)"
        )
        
        if caminho:
            try:
                from ..processamento.impermeabilidade_qgis import salvar_relatorio_txt_simples
                
                txt_path = salvar_relatorio_txt_simples(
                    self.resultados,
                    os.path.dirname(caminho)
                )
                
                if txt_path:
                    # Renomear para o caminho escolhido pelo usuário
                    if os.path.exists(txt_path) and txt_path != caminho:
                        import shutil
                        shutil.move(txt_path, caminho)
                        
                    QMessageBox.information(
                        self, "Sucesso",
                        f"Relatório salvo em:\n{caminho}"
                    )
                else:
                    QMessageBox.warning(self, "Aviso", "Não foi possível salvar o relatório.")
                    
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Erro ao salvar relatório:\n{str(e)}")
