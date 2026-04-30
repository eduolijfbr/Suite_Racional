import os
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import QgsProject, QgsMapLayerType, QgsSettings, QgsVectorLayer, QgsField, QgsMessageLog, Qgis, QgsGeometry, QgsPointXY, QgsCoordinateTransform, QgsRaster, QgsFeatureRequest
from qgis.gui import QgsMapToolEmitPoint
import heapq
import traceback
import itertools
import math
from .medir_3d_dockwidget import Medir3DDockWidget
from .maptool_3d import MapTool3D

class Medir3DPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.dockwidget = None
        self.action = None
        self.map_tool = None
        self.active_projeto_id = None
        self.ponto_inicio = None
        self.ponto_fim = None
        self.point_tool = None

    def initGui(self):
        from qgis.PyQt.QtWidgets import QToolBar
        
        # 1. Configurar Ícone e Ação
        icon_path = os.path.join(self.plugin_dir, 'icon.svg')
        self.action = QAction(QIcon(icon_path), "Medir 3D", self.iface.mainWindow())
        # Usa um nome ÚNICO para evitar conflitos se outros plugins usarem o mesmo boilerplate
        self.action_unique_name = "Action_SuiteRacional_Medir3D_v1"
        self.action.setObjectName(self.action_unique_name)
        self.action.setWhatsThis("Medir distâncias e perfis 3D")
        self.action.setStatusTip("Abrir painel Medir 3D")
        self.action.triggered.connect(self.run)
        
        # 2. Configurar Menu
        self.iface.addPluginToMenu("&Suite Racional Pro", self.action)

        # 3. Configurar Barra de Ferramentas Compartilhada
        self.toolbar_name = 'SuiteRacionalPro'
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, self.toolbar_name)
        if not self.toolbar:
            self.toolbar = self.iface.addToolBar('Suite Racional Pro')
            self.toolbar.setObjectName(self.toolbar_name)
            
        # 4. Prevenir Duplicação na Toolbar
        action_exists = False
        for act in self.toolbar.actions():
            # Checa o nome único E o texto para garantir que não estamos duplicando
            if act.objectName() == self.action_unique_name or act.text() == "Medir 3D":
                action_exists = True
                # Opcional: Se já existe uma ação antiga com o mesmo texto, podemos removê-la aqui
                # self.toolbar.removeAction(act)
                # action_exists = False
                break
                
        if not action_exists:
            self.toolbar.addAction(self.action)

    def unload(self):
        try:
            self.limpar_dados(permanente=True)
        except:
            pass # Garante que a limpeza visual não impeça a remoção do ícone
        
        if self.dockwidget:
            self.iface.removeDockWidget(self.dockwidget)
            self.dockwidget = None

        if self.action:
            self.iface.removePluginMenu("&Suite Racional Pro", self.action)
            
            if hasattr(self, 'toolbar') and self.toolbar:
                self.toolbar.removeAction(self.action)
                
            self.action = None



    def add_layer_to_group(self, layer, group_name="Medir 3D", at_bottom=False):
        root = QgsProject.instance().layerTreeRoot()
        group = root.findGroup(group_name)
        if not group:
            group = root.insertGroup(0, group_name)
        
        QgsProject.instance().addMapLayer(layer, False)
        if at_bottom:
            group.insertLayer(-1, layer)
        else:
            group.insertLayer(0, layer)

    def run(self):
        if not self.dockwidget:
            self.dockwidget = Medir3DDockWidget()
            self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockwidget)
            
            # Conectar sinais
            self.dockwidget.btn_medir_distancia.clicked.connect(self.ativar_medicao)
            self.dockwidget.btn_limpar.clicked.connect(self.limpar_dados)
            self.dockwidget.btn_salvar.clicked.connect(self.salvar_no_banco)
            self.dockwidget.btn_atualizar_pvs.clicked.connect(self.atualizar_pvs)
            self.dockwidget.btn_perfil.clicked.connect(self.ver_perfil)
            self.dockwidget.visibilityChanged.connect(self.dock_visibility_changed)
            self.dockwidget.combo_layer.currentIndexChanged.connect(self.guardar_selecao_camada)
            self.dockwidget.combo_bacias.currentIndexChanged.connect(self.guardar_selecao_camada)
            self.dockwidget.combo_vias.currentIndexChanged.connect(self.atualizar_campos_vias)
            self.dockwidget.btn_carregar_historico.clicked.connect(self.carregar_historico)
            self.dockwidget.btn_excluir_historico.clicked.connect(self.excluir_historico)
            self.dockwidget.btn_calc_sarjeta.clicked.connect(self.calcular_bocas_de_lobo)
            self.dockwidget.btn_calc_otimo.clicked.connect(self.calcular_tracado_economico)
            QgsProject.instance().layersAdded.connect(self.atualizar_camadas)
            QgsProject.instance().layersRemoved.connect(self.atualizar_camadas)
            
        self.dockwidget.show()
        self.atualizar_camadas()
        self.atualizar_combo_historico()

    def dock_visibility_changed(self, visible):
        if not visible:
            self.limpar_dados()

    def salvar_no_banco(self):
        # Encontra as camadas "Rede (Temp)" e "PVs (Temp)"
        rede_layer = None
        pv_layer = None
        
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "Rede (Temp)":
                rede_layer = layer
            elif layer.name() == "PVs (Temp)":
                pv_layer = layer
                
        if not rede_layer and not pv_layer:
            self.dockwidget.add_result("Erro: Nenhuma medição temporária encontrada para salvar.")
            return

        # Caminho para o banco local do próprio plugin
        db_path = os.path.join(self.plugin_dir, "medir_3d_db.gpkg")

        try:
            from qgis.core import QgsVectorFileWriter
            import time
            import uuid
            
            # Gerar um ID único se for um novo projeto, senão usar o ativo
            if not self.active_projeto_id:
                projeto_id = str(uuid.uuid4())[:8]
            else:
                projeto_id = self.active_projeto_id
            
            QgsMessageLog.logMessage(f"Salvando projeto: {projeto_id} (Ativo: {self.active_projeto_id})", "Medir 3D", Qgis.Info)
                
            nome_projeto = self.dockwidget.input_nome_projeto.text().strip()
            if not nome_projeto:
                if self.active_projeto_id:
                    # Se estiver atualizando, mantém o nome se o campo estiver vazio
                    nome_projeto = self.dockwidget.combo_historico.currentText().split(' (')[0]
                else:
                    nome_projeto = f"Projeto_{time.strftime('%H%M%S')}"
        
            timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")

            # Helper function to append or create GeoPackage table
            def save_layer_to_gpkg(layer, table_name, p_id):
                # Se estivermos atualizando, removemos o registro anterior do banco primeiro
                if os.path.exists(db_path):
                    from qgis.core import QgsVectorLayer, QgsFeatureRequest
                    temp_l = QgsVectorLayer(f"{db_path}|layername={table_name}", "del_check", "ogr")
                    if temp_l.isValid():
                        # Encontrar e remover features com o mesmo projeto_id
                        request = QgsFeatureRequest().setFilterExpression(f"\"projeto_id\" = '{p_id}'")
                        feats_to_del = [f.id() for f in temp_l.getFeatures(request)]
                        if feats_to_del:
                            QgsMessageLog.logMessage(f"Removendo {len(feats_to_del)} registros antigos de {table_name} com ID {p_id}", "Medir 3D", Qgis.Info)
                            temp_l.startEditing()
                            for fid in feats_to_del:
                                temp_l.deleteFeature(fid)
                            if not temp_l.commitChanges():
                                QgsMessageLog.logMessage(f"FALHA ao remover registros antigos de {table_name}: {temp_l.lastError().text()}", "Medir 3D", Qgis.Warning)
                        temp_l = None # Força fechamento do provider

                options = QgsVectorFileWriter.SaveVectorOptions()
                options.driverName = "GPKG"
                options.layerName = table_name
                
                if not os.path.exists(db_path):
                    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
                else:
                    # Se o arquivo existe e já tem a camada, faremos append
                    temp_l = QgsVectorLayer(f"{db_path}|layername={table_name}", "check", "ogr")
                    if temp_l.isValid():
                        options.actionOnExistingFile = QgsVectorFileWriter.AppendToLayerNoNewFields
                    else:
                        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
                    
                res = QgsVectorFileWriter.writeAsVectorFormatV3(layer, db_path, self.iface.mapCanvas().mapSettings().transformContext(), options)
                if res[0] != QgsVectorFileWriter.NoError:
                    QgsMessageLog.logMessage(f"Erro QgsVectorFileWriter ({table_name}): {res[1]}", "Medir 3D", Qgis.Critical)
                    return f"Erro ao salvar {table_name}: {res[1]}"
                return None

            if rede_layer:
                pr_rede = rede_layer.dataProvider()
                campos_atuais = [f.name() for f in rede_layer.fields()]
                novos_campos = []
                if "projeto_id" not in campos_atuais:
                    novos_campos.append(QgsField("projeto_id", QVariant.String))
                if "nome_projeto" not in campos_atuais:
                    novos_campos.append(QgsField("nome_projeto", QVariant.String))
                if "log_completo" not in campos_atuais:
                    novos_campos.append(QgsField("log_completo", QVariant.String))
                if "perfil_path" not in campos_atuais:
                    novos_campos.append(QgsField("perfil_path", QVariant.String))
                if "data_hora" not in campos_atuais:
                    novos_campos.append(QgsField("data_hora", QVariant.String))
                
                if novos_campos:
                    pr_rede.addAttributes(novos_campos)
                    rede_layer.updateFields()
                
                log_text = self.dockwidget.txt_resultados.toPlainText()
                timestamp_file = time.strftime("%Y%m%d_%H%M%S")
                dir_db = os.path.dirname(db_path)
                pasta_perfis = os.path.join(dir_db, "Perfis_Salvos")
                if not os.path.exists(pasta_perfis):
                    os.makedirs(pasta_perfis)
                caminho_img = os.path.join(pasta_perfis, f"perfil_{timestamp_file}.png")
                
                if self.map_tool and self.map_tool.last_pvs:
                    self.map_tool.gerar_perfil(show=False, save_path=caminho_img)
                else:
                    caminho_img = ""

                rede_layer.startEditing()
                for feat in rede_layer.getFeatures():
                    feat.setAttribute("projeto_id", projeto_id)
                    feat.setAttribute("nome_projeto", nome_projeto)
                    feat.setAttribute("log_completo", log_text)
                    feat.setAttribute("perfil_path", caminho_img)
                    feat.setAttribute("data_hora", timestamp_str)
                    rede_layer.updateFeature(feat)
                rede_layer.commitChanges()

                err = save_layer_to_gpkg(rede_layer, "rede_historico", projeto_id)
                if err: self.dockwidget.add_result(err)
            
            if pv_layer:
                pr_pv = pv_layer.dataProvider()
                campos_pv = [f.name() for f in pv_layer.fields()]
                novos_pv = []
                if "projeto_id" not in campos_pv:
                    novos_pv.append(QgsField("projeto_id", QVariant.String))
                if "nome_projeto" not in campos_pv:
                    novos_pv.append(QgsField("nome_projeto", QVariant.String))
                
                if novos_pv:
                    pr_pv.addAttributes(novos_pv)
                    pv_layer.updateFields()
                
                pv_layer.startEditing()
                for feat in pv_layer.getFeatures():
                    feat.setAttribute("projeto_id", projeto_id)
                    feat.setAttribute("nome_projeto", nome_projeto)
                    pv_layer.updateFeature(feat)
                pv_layer.commitChanges()

                err = save_layer_to_gpkg(pv_layer, "pv_historico", projeto_id)
                if err: self.dockwidget.add_result(err)
                
            self.active_projeto_id = projeto_id
            self.dockwidget.add_result(f"SUCESSO! Projeto '{nome_projeto}' salvo em:\n{db_path}")
            self.atualizar_combo_historico()
            self.dockwidget.input_nome_projeto.clear()

        except Exception as e:
            self.dockwidget.add_result(f"Erro Crítico ao Salvar: {str(e)}")

    def limpar_dados(self, permanente=False):
        self.active_projeto_id = None
        # Desativa a ferramenta do mapa se estiver ativa
        if self.map_tool and self.iface.mapCanvas().mapTool() == self.map_tool:
            self.iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool.reset_measurement()
        
        # Limpa o texto da UI
        if self.dockwidget:
            self.dockwidget.txt_resultados.clear()
            
        # Tenta deletar as camadas temporárias e de histórico
        layers_to_remove = []
        for layer in QgsProject.instance().mapLayers().values():
            name = layer.name()
            # Remove camadas temporárias de medição atual
            if name in ["Rede (Temp)", "PVs (Temp)"]:
                layers_to_remove.append(layer.id())
            # Remove camadas carregadas do histórico (REDE_... ou PVs_...)
            elif name.startswith("REDE_") or name.startswith("PVs_"):
                layers_to_remove.append(layer.id())
                
        if layers_to_remove:
            QgsProject.instance().removeMapLayers(layers_to_remove)

    def atualizar_combo_historico(self):
        self.dockwidget.combo_historico.clear()
        db_path = os.path.join(self.plugin_dir, "medir_3d_db.gpkg")
        if not os.path.exists(db_path):
            return

        # Criar uma camada temporária apenas para ler a tabela de histórico
        uri = f"{db_path}|layername=rede_historico"
        layer = QgsVectorLayer(uri, "temp_hist", "ogr")
        if layer.isValid():
            features = list(layer.getFeatures())
            for feat in reversed(features):
                # Usar o nome do projeto se disponível, senão usa a data
                campos = [f.name() for f in feat.fields()]
                nome = feat['nome_projeto'] if 'nome_projeto' in campos and feat['nome_projeto'] else "Sem Nome"
                data = feat['data_hora'] if 'data_hora' in campos else "S/D"
                label = f"{nome} ({data})"
                
                # Guardamos o projeto_id para carregar todas as camadas vinculadas
                p_id = feat['projeto_id'] if 'projeto_id' in campos else str(feat.id())
                self.dockwidget.combo_historico.addItem(label, p_id)

    def excluir_historico(self):
        projeto_id = self.dockwidget.combo_historico.currentData()
        if not projeto_id:
            return

        QgsMessageLog.logMessage(f"Iniciando exclusão do projeto_id: {projeto_id}", "Medir 3D", Qgis.Info)

        projeto_nome = self.dockwidget.combo_historico.currentText()
        
        reply = QMessageBox.question(None, 'Confirmar Exclusão', 
                                    f"Tem certeza que deseja excluir permanentemente o registro:\n'{projeto_nome}'?\n\nIsso removerá os dados do banco, o perfil e as camadas do mapa.",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.No:
            return

        db_path = os.path.join(self.plugin_dir, "medir_3d_db.gpkg")
        if not os.path.exists(db_path):
            return

        try:
            from qgis.core import QgsVectorLayer, QgsFeatureRequest
            
            # 1. Obter caminho do perfil para deletar o arquivo
            uri_rede = f"{db_path}|layername=rede_historico|subset=\"projeto_id\" = '{projeto_id}'"
            layer_rede = QgsVectorLayer(uri_rede, "check_del", "ogr")
            if layer_rede.isValid() and layer_rede.featureCount() > 0:
                features = list(layer_rede.getFeatures())
                if features:
                    feat = features[0]
                    campos = [f.name() for f in feat.fields()]
                    perfil_path = feat["perfil_path"] if "perfil_path" in campos else None
                    if perfil_path and os.path.exists(perfil_path):
                        try:
                            os.remove(perfil_path)
                            QgsMessageLog.logMessage(f"Perfil removido: {perfil_path}", "Medir 3D", Qgis.Info)
                        except Exception as e:
                            QgsMessageLog.logMessage(f"Falha ao remover arquivo de perfil: {str(e)}", "Medir 3D", Qgis.Warning)

            # 2. Deletar das tabelas do GPKG
            for table in ["rede_historico", "pv_historico"]:
                l = QgsVectorLayer(f"{db_path}|layername={table}", "deleter", "ogr")
                if l.isValid():
                    request = QgsFeatureRequest().setFilterExpression(f"\"projeto_id\" = '{projeto_id}'")
                    fids = [f.id() for f in l.getFeatures(request)]
                    if fids:
                        QgsMessageLog.logMessage(f"Deletando {len(fids)} features da tabela {table} (ID: {projeto_id})", "Medir 3D", Qgis.Info)
                        l.startEditing()
                        for fid in fids:
                            l.deleteFeature(fid)
                        if not l.commitChanges():
                            QgsMessageLog.logMessage(f"Erro ao comitar exclusão em {table}: {l.lastError().text()}", "Medir 3D", Qgis.Warning)
                    l = None

            # 3. Se era o projeto ativo ou se as camadas estão no mapa, resetar UI/Mapa
            self.limpar_dados()
            
            self.iface.mapCanvas().refresh()
            self.dockwidget.add_result(f"Registro {projeto_id} excluído com sucesso e tela atualizada.")
            self.atualizar_combo_historico()

        except Exception as e:
            self.dockwidget.add_result(f"Erro ao excluir: {str(e)}")


    def carregar_historico(self):
        projeto_id = self.dockwidget.combo_historico.currentData()
        if not projeto_id:
            return

        # Limpar antes de carregar
        self.limpar_dados()
        self.active_projeto_id = projeto_id

        db_path = os.path.join(self.plugin_dir, "medir_3d_db.gpkg")
        
        # 1. Carregar Rede
        uri_rede = f"{db_path}|layername=rede_historico|subset=\"projeto_id\" = '{projeto_id}'"
        layer_rede_db = QgsVectorLayer(uri_rede, "load_rede", "ogr")
        
        if not layer_rede_db.isValid() or layer_rede_db.featureCount() == 0:
            self.dockwidget.add_result("Erro ao localizar rede no histórico.")
            return

        features = list(layer_rede_db.getFeatures())
        if not features:
            self.dockwidget.add_result("Erro: Dados geométricos não encontrados no histórico.")
            return
        feat_rede = features[0]
        
        # Restaurar UI
        self.dockwidget.txt_resultados.clear()
        log_text = feat_rede["log_completo"]
        if log_text:
            self.dockwidget.add_result(f"=== PROJETO CARREGADO: {feat_rede['nome_projeto']} ===")
            self.dockwidget.add_result(log_text)
        
        perfil_path = feat_rede["perfil_path"]
        if perfil_path and os.path.exists(perfil_path):
            self.dockwidget.add_result(f"\nAbrindo perfil: {perfil_path}")
            os.startfile(perfil_path)
            
        # 2. Restaurar Estado para o MapTool (Permite Recalcular PVs)
        from qgis.core import QgsPointXY
        if not self.map_tool:
            self.map_tool = MapTool3D(self.iface.mapCanvas(), self.get_camada_selecionada, self.get_inclinacao_rede, self.get_dist_pv, self.get_diameter)
            self.map_tool.measurement_done.connect(self.dockwidget.add_result)
        
        # Extrair pontos da geometria carregada
        geom = feat_rede.geometry()
        # No QGIS 3, asPolyline() funciona para LineString
        self.map_tool.last_points = [QgsPointXY(pt) for pt in geom.asPolyline()]
        self.map_tool.last_pvs = []  # Resetar PVs calculados anteriormente
        self.map_tool.total_dist_2d = feat_rede["dist_2d_m"]
        self.map_tool.total_dist_3d = feat_rede["dist_3d_m"]
            
        # 3. Carregar PVs
        uri_pv = f"{db_path}|layername=pv_historico|subset=\"projeto_id\" = '{projeto_id}'"
        layer_pv_db = QgsVectorLayer(uri_pv, "load_pv", "ogr")
        
        # 4. Adicionar como camadas de memória ATIVAS (Temp) para o usuário
        crs = self.iface.mapCanvas().mapSettings().destinationCrs().authid()
        
        # Rede no mapa (Como Temp para permitir salvar/recalcular)
        view_rede = QgsVectorLayer(f"LineString?crs={crs}", "Rede (Temp)", "memory")
        view_rede.dataProvider().addAttributes(layer_rede_db.fields())
        view_rede.updateFields()
        view_rede.dataProvider().addFeatures([feat_rede])
        self.add_layer_to_group(view_rede)
        
        # PVs no mapa (Como Temp)
        if layer_pv_db.isValid() and layer_pv_db.featureCount() > 0:
            view_pv = QgsVectorLayer(f"Point?crs={crs}", "PVs (Temp)", "memory")
            view_pv.dataProvider().addAttributes(layer_pv_db.fields())
            view_pv.updateFields()
            view_pv.dataProvider().addFeatures(list(layer_pv_db.getFeatures()))
            self.add_layer_to_group(view_pv)
            self.dockwidget.add_result(f"\nRecuperados {layer_pv_db.featureCount()} PVs.")
            
        self.dockwidget.add_result("\nPronto para novo cálculo ou edição.")

    def atualizar_camadas(self, layers=None):
        settings = QgsSettings()
        # Salva o nome da camada atualmente selecionada (se houver) antes de limpar
        camada_atual = self.dockwidget.combo_layer.currentText()
        if not camada_atual: camada_atual = settings.value("Medir3D/lastLayer", "")
        
        bacia_atual = self.dockwidget.combo_bacias.currentText()
        if not bacia_atual: bacia_atual = settings.value("Medir3D/lastBacia", "")
        
        vias_atual = self.dockwidget.combo_vias.currentText()
        if not vias_atual: vias_atual = settings.value("Medir3D/lastVias", "")

        self.dockwidget.combo_layer.blockSignals(True)
        self.dockwidget.combo_bacias.blockSignals(True)
        self.dockwidget.combo_vias.blockSignals(True)
        
        self.dockwidget.combo_layer.clear()
        self.dockwidget.combo_bacias.clear()
        self.dockwidget.combo_vias.clear()
        
        todas_camadas = QgsProject.instance().mapLayers().values()
        for layer in todas_camadas:
            if layer.type() == QgsMapLayerType.RasterLayer:
                self.dockwidget.combo_layer.addItem(layer.name(), layer.id())
            elif layer.type() == QgsMapLayerType.VectorLayer:
                geom_type = layer.geometryType()
                from qgis.core import QgsWkbTypes
                if geom_type == QgsWkbTypes.PolygonGeometry:
                    self.dockwidget.combo_bacias.addItem(layer.name(), layer.id())
                elif geom_type == QgsWkbTypes.LineGeometry:
                    self.dockwidget.combo_vias.addItem(layer.name(), layer.id())
        
        # Tenta restaurar a seleção anterior pelo nome
        index_raster = self.dockwidget.combo_layer.findText(camada_atual)
        if index_raster >= 0: self.dockwidget.combo_layer.setCurrentIndex(index_raster)
            
        index_bacia = self.dockwidget.combo_bacias.findText(bacia_atual)
        if index_bacia >= 0: self.dockwidget.combo_bacias.setCurrentIndex(index_bacia)
            
        index_vias = self.dockwidget.combo_vias.findText(vias_atual)
        if index_vias >= 0: self.dockwidget.combo_vias.setCurrentIndex(index_vias)
            
        self.dockwidget.combo_layer.blockSignals(False)
        self.dockwidget.combo_bacias.blockSignals(False)
        self.dockwidget.combo_vias.blockSignals(False)
        
        self.atualizar_campos_vias()

    def guardar_selecao_camada(self):
        if self.dockwidget:
            layer_name = self.dockwidget.combo_layer.currentText()
            if layer_name:
                settings = QgsSettings()
                settings.setValue("Medir3D/lastLayer", layer_name)
            
            bacia_name = self.dockwidget.combo_bacias.currentText()
            if bacia_name:
                settings = QgsSettings()
                settings.setValue("Medir3D/lastBacia", bacia_name)

    def atualizar_campos_vias(self):
        if not self.dockwidget: return
        
        vias_name = self.dockwidget.combo_vias.currentText()
        if vias_name:
            settings = QgsSettings()
            settings.setValue("Medir3D/lastVias", vias_name)
            
        layer_id = self.dockwidget.combo_vias.currentData()
        self.dockwidget.combo_campo_n.clear()
        self.dockwidget.combo_campo_lamina.clear()
        self.dockwidget.combo_campo_caimento.clear()
        
        if layer_id:
            layer = QgsProject.instance().mapLayer(layer_id)
            if layer:
                fields = [f.name() for f in layer.fields()]
                self.dockwidget.combo_campo_n.addItems(fields)
                self.dockwidget.combo_campo_lamina.addItems(fields)
                self.dockwidget.combo_campo_caimento.addItems(fields)

    def get_camada_selecionada(self):
        layer_id = self.dockwidget.combo_layer.currentData()
        if layer_id:
            return QgsProject.instance().mapLayer(layer_id)
        return None
        
    def get_inclinacao_rede(self):
        try:
            val = float(self.dockwidget.input_inclinacao.text().replace(',', '.'))
            if val > 4.5:
                self.dockwidget.add_result(f"ALERTA: Declividade {val:.1f}% excede limite. Ajustado para 4,5%.")
                self.dockwidget.input_inclinacao.setText("4.5")
                return 4.5
            return val
        except:
            return 1.0 # Default 1%
            
    def get_dist_pv(self):
        try:
            return float(self.dockwidget.input_dist_pv.text().replace(',', '.'))
        except:
            return 40.0

    def atualizar_pvs(self):
        raster_layer = self.get_camada_selecionada()
        if not raster_layer:
            self.dockwidget.add_result("Erro: Nenhuma camada raster selecionada.")
            return
        if not self.map_tool:
            # Recriar map_tool se foi destruído
            self.map_tool = MapTool3D(self.iface.mapCanvas(), self.get_camada_selecionada, self.get_inclinacao_rede, self.get_dist_pv, self.get_diameter)
            self.map_tool.measurement_done.connect(self.dockwidget.add_result)
            self.dockwidget.add_result("Erro: Nenhuma medição anterior. Trace um caminho primeiro.")
            return
        if not self.map_tool.last_points:
            self.dockwidget.add_result("Erro: Nenhuma medição anterior. Trace um caminho primeiro.")
            return
        slope = self.get_inclinacao_rede()
        self.dockwidget.add_result(f"Recalculando PVs com declive {slope:.1f}%...")
        self.map_tool.refazer_pvs(raster_layer)

    def ver_perfil(self):
        if self.map_tool:
            self.map_tool.gerar_perfil()
        else:
            self.dockwidget.add_result("Erro: Nenhum perfil disponível. Faça uma medição primeiro.")

    def get_diameter(self):
        try:
            val = float(self.dockwidget.input_diametro.text().replace(',', '.'))
            return val
        except:
            return 200.0

    def ativar_medicao(self):
        self.active_projeto_id = None
        if not self.map_tool:
            self.map_tool = MapTool3D(self.iface.mapCanvas(), self.get_camada_selecionada, self.get_inclinacao_rede, self.get_dist_pv, self.get_diameter)
            self.map_tool.measurement_done.connect(self.dockwidget.add_result)
        
        self.iface.mapCanvas().setMapTool(self.map_tool)
        self.dockwidget.add_result("Ferramenta 3D ativada.\n- ESQUERDO: Adicionar pontos do traçado\n- DIREITO: Finalizar e Gerar PVs")

    def calcular_capacidade_sarjeta(self, n, y_max, sx, i_long):
        if i_long <= 0 or sx <= 0:
            return 0.0
        z = 1.0 / sx
        area = (z * (y_max ** 2)) / 2.0
        perimetro_molhado = y_max + (y_max * ((1 + z**2) ** 0.5))
        raio_hidraulico = area / perimetro_molhado
        q_cap = (1.0 / n) * area * (raio_hidraulico ** (2/3)) * (i_long ** 0.5)
        return q_cap

    def calcular_bocas_de_lobo(self):
        self.dockwidget.add_result("Iniciando cálculo de sarjetas...")
        raster_layer = self.get_camada_selecionada()
        if not raster_layer:
            self.dockwidget.add_result("Erro: Selecione uma camada raster (MDT/MDS).")
            return
            
        vias_id = self.dockwidget.combo_vias.currentData()
        bacias_id = self.dockwidget.combo_bacias.currentData()
        
        if not vias_id or not bacias_id:
            self.dockwidget.add_result("Erro: Selecione as camadas de Vias e Bacias.")
            return
            
        layer_vias = QgsProject.instance().mapLayer(vias_id)
        layer_bacias = QgsProject.instance().mapLayer(bacias_id)
        
        if not layer_vias or not layer_bacias:
            self.dockwidget.add_result("Erro: Camadas não encontradas.")
            return

        is_dynamic = self.dockwidget.chk_dinamico.isChecked()
        
        try:
            n_fixo = float(self.dockwidget.input_manning.text().replace(',', '.'))
            lam_fixo = float(self.dockwidget.input_lamina.text().replace(',', '.'))
            cai_fixo = float(self.dockwidget.input_caimento.text().replace(',', '.')) / 100.0
            q_engol_fixo = float(self.dockwidget.input_engolimento.text().replace(',', '.'))
            margem_segur = float(self.dockwidget.input_margem.text().replace(',', '.')) / 100.0
            dist_max = float(self.dockwidget.input_dist_max.text().replace(',', '.'))
            dist_min = float(self.dockwidget.input_dist_min.text().replace(',', '.'))
            largura_via = float(self.dockwidget.input_largura_via.text().replace(',', '.'))
        except ValueError:
            self.dockwidget.add_result("Erro: Parâmetros numéricos inválidos.")
            return

        campo_n = self.dockwidget.combo_campo_n.currentText()
        campo_lam = self.dockwidget.combo_campo_lamina.currentText()
        campo_cai = self.dockwidget.combo_campo_caimento.currentText()

        crs = self.iface.mapCanvas().mapSettings().destinationCrs().authid()
        from qgis.core import QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsRaster, QgsSpatialIndex, QgsCoordinateTransform, QgsWkbTypes
        from qgis.PyQt.QtCore import QVariant
        import math
        
        # Camada de Poços de Visita (Eixo da via)
        layer_pv = QgsVectorLayer(f"Point?crs={crs}", "PVs da Sarjeta (Temp)", "memory")
        pr_pv = layer_pv.dataProvider()
        
        # Camada de Bocas de Lobo (Pares nos bordos)
        layer_bl = QgsVectorLayer(f"Point?crs={crs}", "Bocas de Lobo (Temp)", "memory")
        pr_bl = layer_bl.dataProvider()
        
        campos = [
            QgsField("q_cap", QVariant.Double),
            QgsField("q_acc", QVariant.Double),
            QgsField("i_long", QVariant.Double),
            QgsField("qtd_grelhas", QVariant.Int)
        ]
        
        pr_pv.addAttributes(campos)
        layer_pv.updateFields()
        
        pr_bl.addAttributes(campos)
        layer_bl.updateFields()
        
        features_pv = []
        features_bl = []
        
        def get_z(pt):
            canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            raster_crs = raster_layer.crs()
            if canvas_crs != raster_crs:
                transform = QgsCoordinateTransform(canvas_crs, raster_crs, QgsProject.instance())
                pt_trans = transform.transform(pt)
            else:
                pt_trans = pt
            ident = raster_layer.dataProvider().identify(pt_trans, QgsRaster.IdentifyFormatValue)
            if ident.isValid() and ident.results():
                for val in ident.results().values():
                    if val is not None:
                        return float(val)
            return 0.0

        index_vias = QgsSpatialIndex(layer_vias.getFeatures())
        vias_selecionadas_ids = [f.id() for f in layer_vias.selectedFeatures()]
        
        selected_bacias = list(layer_bacias.selectedFeatures())
        if not selected_bacias:
            self.dockwidget.add_result("Erro: Selecione a(s) bacia(s) no mapa.")
            return

        self.dockwidget.add_result(f"\n--- CÁLCULO DINÂMICO (PVs e BLs) ---")
        
        for bacia in selected_bacias:
            bacia_geom = bacia.geometry()
            area_ha = bacia_geom.area() / 10000.0
            q_total_bacia = (0.5 * 150 * area_ha) / 360.0
            
            self.dockwidget.add_result(f"\nBacia {bacia.id()}: Área={area_ha:.2f}ha, Q_total={q_total_bacia:.4f}m3/s")
            
            # Passo 1: Identificar e preparar vias na bacia
            vias_na_bacia = []
            l_total_vias = 0.0
            candidate_ids = index_vias.intersects(bacia_geom.boundingBox())
            for v_id in candidate_ids:
                if vias_selecionadas_ids and v_id not in vias_selecionadas_ids: continue
                fv = layer_vias.getFeature(v_id)
                if fv.geometry().intersects(bacia_geom):
                    inter = fv.geometry().intersection(bacia_geom)
                    for part in inter.asGeometryCollection() if inter.isMultipart() else [inter]:
                        lin = part.asPolyline()
                        if len(lin) < 2: continue
                        z_i, z_f = get_z(QgsPointXY(lin[0])), get_z(QgsPointXY(lin[-1]))
                        # Garante orientação montante -> jusante na geometria para interpolação correta
                        if z_f > z_i: 
                            lin.reverse()
                            part = QgsGeometry.fromPolylineXY(lin)
                            z_i, z_f = z_f, z_i
                        dist = part.length()
                        if dist < 1.0: continue
                        vias_na_bacia.append({'geom': part, 'pts': lin, 'zi': z_i, 'zf': z_f, 'L': dist, 'feat': fv})
                        l_total_vias += dist

            if l_total_vias == 0: continue
            q_linear = q_total_bacia / l_total_vias # m3/s por metro linear
            
            # Passo 2: Ordenação Topológica Simplificada (por Z máximo)
            vias_na_bacia.sort(key=lambda x: x['zi'], reverse=True)
            
            # Dicionário para rastrear vazão que chega ao final de cada via
            flow_at_point = {} # (x,y) -> q_acumulado

            for vdata in vias_na_bacia:
                p_ini = (round(vdata['pts'][0].x(), 2), round(vdata['pts'][0].y(), 2))
                q_acc = flow_at_point.get(p_ini, 0.0)
                
                # Parâmetros hidráulicos
                n, lam, cai = n_fixo, lam_fixo, cai_fixo
                if is_dynamic:
                    fv = vdata['feat']
                    if fv[campo_n] is not None: n = float(fv[campo_n])
                    if fv[campo_lam] is not None: lam = float(fv[campo_lam])
                    if fv[campo_cai] is not None: cai = float(fv[campo_cai]) / 100.0
                
                i_long = max(0.001, abs(vdata['zi'] - vdata['zf']) / vdata['L'])
                q_cap = self.calcular_capacidade_sarjeta(n, lam, cai, i_long)
                
                # 4. Correção de Eficiência por Declividade (Splash-over)
                if i_long > 0.08:
                    fator_e = 0.50
                elif i_long > 0.04:
                    fator_e = 0.75
                else:
                    fator_e = 1.0
                
                q_engol_real = q_engol_fixo * fator_e
                
                # Percorre a via em passos de 10m
                passo = 10.0
                dist_percorrida = 0.0
                dist_desde_ultima_bl = 0.0
                pts = vdata['pts']
                
                last_indices_in_this_via = []
                
                while dist_percorrida < vdata['L']:
                    segmento_l = min(passo, vdata['L'] - dist_percorrida)
                    q_acc += q_linear * segmento_l
                    dist_percorrida += segmento_l
                    dist_desde_ultima_bl += segmento_l
                    
                    is_final_segment = dist_percorrida >= vdata['L'] - 3.0
                    
                    gatilho_hidraulico = q_acc > (q_cap * margem_segur)
                    gatilho_geometrico = dist_desde_ultima_bl >= dist_max
                    # 3. Gatilho Topológico: esquina/ponto baixo com água considerável
                    gatilho_topologico = is_final_segment and q_acc > (q_engol_real * 0.5)
                    
                    if gatilho_hidraulico or gatilho_geometrico or gatilho_topologico:
                        # 2. Agrupamento em Baterias
                        vazao_a_abater = q_acc - (q_cap * margem_segur) if gatilho_hidraulico else q_acc
                        
                        if vazao_a_abater <= 0 and (gatilho_geometrico or gatilho_topologico):
                             qtd_novas = 1 # Para manter o espaçamento/secar esquina
                        else:
                             qtd_novas = math.ceil(vazao_a_abater / q_engol_real)
                        
                        # 1. Trava de Distância Mínima
                        if dist_desde_ultima_bl < dist_min and last_indices_in_this_via:
                            # Acumula na última bateria dessa mesma via (PV e suas 2 BLs)
                            for list_obj, idx in last_indices_in_this_via:
                                feat = list_obj[idx]
                                attr = feat.attributes()
                                attr[3] += qtd_novas
                                feat.setAttributes(attr)
                            
                            q_acc = max(0.0, q_acc - (qtd_novas * q_engol_real))
                        else:
                            # Lança novo Poço de Visita no Eixo e Bocas de Lobo nos Bordos
                            # Ponto base da captação (BLs)
                            pos_bl_geom = vdata['geom'].interpolate(dist_percorrida)
                            pt_bl_base = pos_bl_geom.asPoint()
                            
                            # Cálculo dinâmico do deslocamento (H) para garantir PV mais baixo que BL
                            # considerando a coroa da rua (cross-slope) e visando inclinação entre 0.5% e 1.5%
                            s_alvo = 0.01 # Alvo de 1.0% de inclinação na conexão
                            w2 = largura_via / 2.0
                            c_transv = cai # Inclinação transversal decimal
                            
                            # Se i_long (longitudinal) for maior que o alvo, calculamos H para compensar a coroa
                            # H * i_long - (w2 * c_transv) = s_alvo * H  =>  H = (w2 * c_transv) / (i_long - s_alvo)
                            if i_long > s_alvo + 0.002:
                                shift_pv = (w2 * c_transv) / (i_long - s_alvo)
                            else:
                                # Em vias planas, usamos um deslocamento maior para buscar o ponto mais baixo possível
                                # ou para indicar claramente a jusante, respeitando os limites do sistema
                                shift_pv = 12.0 
                            
                            # Limitar o deslocamento para valores práticos e visíveis (entre 3m e 6m)
                            shift_pv = max(3.0, min(shift_pv, 6.0))
                            
                            pos_pv_geom = vdata['geom'].interpolate(min(dist_percorrida + shift_pv, vdata['L']))
                            pt_pv = pos_pv_geom.asPoint()
                            
                            # Feature PV (Deslocado para jusante conforme cálculo de inclinação)
                            fpv = QgsFeature()
                            fpv.setGeometry(QgsGeometry.fromPointXY(pt_pv))
                            fpv.setAttributes([round(q_cap, 4), round(q_acc, 4), round(i_long, 4), qtd_novas])
                            features_pv.append(fpv)
                            idx_pv = len(features_pv) - 1
                            
                            # Cálculo de Offset Transversal para BLs (nos bordos)
                            dist_next = min(dist_percorrida + 0.1, vdata['L'])
                            dist_prev = max(dist_percorrida - 0.1, 0.0)
                            
                            if dist_percorrida + 0.1 <= vdata['L']:
                                pt_next = vdata['geom'].interpolate(dist_next).asPoint()
                                dx, dy = pt_next.x() - pt_bl_base.x(), pt_next.y() - pt_bl_base.y()
                            else:
                                pt_prev = vdata['geom'].interpolate(dist_prev).asPoint()
                                dx, dy = pt_bl_base.x() - pt_prev.x(), pt_bl_base.y() - pt_prev.y()
                            
                            length = math.sqrt(dx*dx + dy*dy)
                            current_last_indices = [(features_pv, idx_pv)]
                            
                            if length > 0:
                                # Vetor unitário perpendicular
                                nx, ny = -dy/length, dx/length
                                offset = largura_via / 2.0
                                
                                for side in [-1, 1]:
                                    bl_pos = QgsPointXY(pt_bl_base.x() + nx * offset * side, 
                                                        pt_bl_base.y() + ny * offset * side)
                                    fbl = QgsFeature()
                                    fbl.setGeometry(QgsGeometry.fromPointXY(bl_pos))
                                    fbl.setAttributes([round(q_cap, 4), round(q_acc, 4), round(i_long, 4), qtd_novas])
                                    features_bl.append(fbl)
                                    current_last_indices.append((features_bl, len(features_bl) - 1))
                            
                            last_indices_in_this_via = current_last_indices
                            
                            q_acc = max(0.0, q_acc - (qtd_novas * q_engol_real))
                            dist_desde_ultima_bl = 0.0 # Reseta a distância
                
                # Transmite vazão residual para o ponto final
                p_fim = (round(vdata['pts'][-1].x(), 2), round(vdata['pts'][-1].y(), 2))
                flow_at_point[p_fim] = flow_at_point.get(p_fim, 0.0) + q_acc

        if features_pv:
            pr_pv.addFeatures(features_pv)
            self.add_layer_to_group(layer_pv)
            
            if features_bl:
                pr_bl.addFeatures(features_bl)
                self.add_layer_to_group(layer_bl)
            
            self.dockwidget.add_result(f"Sucesso: {len(features_pv)} PVs e {len(features_bl)} BLs lançados com fluxo dinâmico.")
        else:
            self.dockwidget.add_result("Nenhuma BL necessária.")

    # --- Funções de Otimização de Traçado (Global Automático) ---

    def get_z_local(self, pt, raster_layer):
        # Garantir que pt é QgsPointXY (identify() não aceita QgsPoint 3D)
        if not isinstance(pt, QgsPointXY):
            pt = QgsPointXY(pt.x(), pt.y())
            
        canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        raster_crs = raster_layer.crs()
        if canvas_crs != raster_crs:
            transform = QgsCoordinateTransform(canvas_crs, raster_crs, QgsProject.instance())
            pt_trans = transform.transform(pt)
        else:
            pt_trans = pt
            
        # Reforçar conversão após transformação (pode retornar QgsPoint)
        if not isinstance(pt_trans, QgsPointXY):
            pt_trans = QgsPointXY(pt_trans.x(), pt_trans.y())

        ident = raster_layer.dataProvider().identify(pt_trans, QgsRaster.IdentifyFormatValue)
        if ident.isValid() and ident.results():
            for val in ident.results().values():
                if val is not None and str(val).lower() != 'nan':
                    return float(val)
        return 0.0

    def calcular_tracado_economico(self):
        from qgis.core import QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer, QgsProject, QgsFeatureRequest, QgsMessageLog, Qgis, QgsField, QgsWkbTypes, QgsCoordinateTransform, QgsSpatialIndex, QgsRaster
        from qgis.PyQt.QtCore import QVariant
        import math
        import time

        try:
            # 1. Obter Camadas e Parâmetros da UI
            raster_layer = self.get_camada_selecionada()
            vias_id = self.dockwidget.combo_vias.currentData()
            bacias_id = self.dockwidget.combo_bacias.currentData()

            if not raster_layer or not vias_id or not bacias_id:
                self.dockwidget.add_result("Erro: Selecione MDT, Vias e Bacias para a otimização.")
                return

            layer_vias = QgsProject.instance().mapLayer(vias_id)
            layer_bacias = QgsProject.instance().mapLayer(bacias_id)

            # Parâmetros Hidráulicos
            try:
                n_fixo = float(self.dockwidget.input_manning.text().replace(',', '.'))
                lam_fixo = float(self.dockwidget.input_lamina.text().replace(',', '.'))
                cai_fixo = float(self.dockwidget.input_caimento.text().replace(',', '.')) / 100.0
                q_engol_fixo = float(self.dockwidget.input_engolimento.text().replace(',', '.'))
                margem_segur = float(self.dockwidget.input_margem.text().replace(',', '.')) / 100.0
                dist_max = float(self.dockwidget.input_dist_max.text().replace(',', '.'))
                dist_min = float(self.dockwidget.input_dist_min.text().replace(',', '.'))
                largura_via = float(self.dockwidget.input_largura_via.text().replace(',', '.'))
            except ValueError:
                self.dockwidget.add_result("Erro: Parâmetros numéricos inválidos na aba de cálculos.")
                return

            self.dockwidget.add_result("\n=== INICIANDO OTIMIZAÇÃO AUTOMATIZADA ===")
        
            # 2. Preparar Camadas de Saída
            crs = layer_vias.crs().authid()
            
            # Camada de PVs
            layer_pv = QgsVectorLayer(f"Point?crs={crs}", "PVs Otimizados", "memory")
            pr_pv = layer_pv.dataProvider()
            
            # Camada de BLs
            layer_bl = QgsVectorLayer(f"Point?crs={crs}", "Bocas de Lobo Otimizadas", "memory")
            pr_bl = layer_bl.dataProvider()
            
            # Camada de Rede (Traçado Sugerido)
            layer_rede = QgsVectorLayer(f"LineString?crs={crs}", "Rede Sugerida (Otimizada)", "memory")
            pr_rede = layer_rede.dataProvider()

            # Atributos solicitados
            campos = [
                QgsField("id", QVariant.Int),
                QgsField("codlograd", QVariant.String),
                QgsField("shape_len", QVariant.Double),
                QgsField("diametro_rede", QVariant.Double),
                QgsField("cobertura_rede", QVariant.Double)
            ]
            
            for pr in [pr_pv, pr_bl, pr_rede]:
                pr.addAttributes(campos)
            
            layer_pv.updateFields()
            layer_bl.updateFields()
            layer_rede.updateFields()

            features_pv = []
            features_bl = []
            features_rede = []

            # 3. Helpers de Topografia
            def get_z(pt):
                if not isinstance(pt, QgsPointXY): pt = QgsPointXY(pt.x(), pt.y())
                canvas_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
                raster_crs = raster_layer.crs()
                if canvas_crs != raster_crs:
                    transform = QgsCoordinateTransform(canvas_crs, raster_crs, QgsProject.instance())
                    pt = transform.transform(pt)
                ident = raster_layer.dataProvider().identify(pt, QgsRaster.IdentifyFormatValue)
                if ident.isValid() and ident.results():
                    for val in ident.results().values():
                        if val is not None and str(val).lower() != 'nan': return float(val)
                return 0.0

            # 4. Obter Área de Estudo (Bacias Selecionadas)
            selected_bacias = list(layer_bacias.selectedFeatures())
            if not selected_bacias:
                self.dockwidget.add_result("Erro: Selecione a(s) bacia(s) de estudo no mapa.")
                return
            
            bacia_geom = QgsGeometry.unaryUnion([f.geometry() for f in selected_bacias])
            index_vias = QgsSpatialIndex(layer_vias.getFeatures())
            vias_selecionadas_ids = [f.id() for f in layer_vias.selectedFeatures()]

            # 5. Loop de Processamento por Bacia
            for bacia in selected_bacias:
                b_geom = bacia.geometry()
                area_ha = b_geom.area() / 10000.0
                q_total_bacia = (0.5 * 150 * area_ha) / 360.0 # Exemplo simplificado de vazão
                
                # Identificar vias na bacia e aplicar clipping + high point split
                vias_na_bacia = []
                l_total_vias = 0.0
                candidate_ids = index_vias.intersects(b_geom.boundingBox())
                
                for v_id in candidate_ids:
                    if vias_selecionadas_ids and v_id not in vias_selecionadas_ids: continue
                    fv = layer_vias.getFeature(v_id)
                    if fv.geometry().intersects(b_geom):
                        # Clipping
                        inter = fv.geometry().intersection(b_geom)
                        for part in inter.asGeometryCollection() if inter.isMultipart() else [inter]:
                            if QgsWkbTypes.isCurvedType(part.wkbType()): part = part.segmentize()
                            lin = part.asPolyline()
                            if len(lin) < 2: continue
                            
                            # Identificar Topo (Ponto Alto)
                            pts_z = [(pt, get_z(pt)) for pt in lin]
                            idx_max = max(range(len(pts_z)), key=lambda i: pts_z[i][1])
                            
                            def create_via_data(p_list):
                                if len(p_list) < 2: return
                                g = QgsGeometry.fromPolylineXY([p[0] for p in p_list])
                                if g.length() < 1.0: return
                                vias_na_bacia.append({
                                    'geom': g, 'pts': [p[0] for p in p_list], 'pts_z': p_list,
                                    'zi': p_list[0][1], 'zf': p_list[-1][1], 'L': g.length(), 'feat': fv
                                })
                                nonlocal l_total_vias
                                l_total_vias += g.length()

                            if 0 < idx_max < len(pts_z) - 1:
                                create_via_data(pts_z[:idx_max+1][::-1])
                                create_via_data(pts_z[idx_max:])
                            else:
                                if pts_z[0][1] >= pts_z[-1][1]: create_via_data(pts_z)
                                else: create_via_data(pts_z[::-1])

                if l_total_vias == 0: continue
                q_linear = q_total_bacia / l_total_vias

                # 6. Simulação Hidráulica e Geração de Elementos
                # Função auxiliar: extrair sub-polilinha da geometria por distância ao longo da linha
                def extrair_sublinha(geom, pts_originais, d_ini, d_fim):
                    """Extrai um segmento da polilinha entre duas distâncias, usando os vértices originais."""
                    if d_fim <= d_ini + 0.5: return None
                    
                    sub_pts = []
                    d_acc = 0.0
                    
                    # Adicionar ponto interpolado no início
                    pt_ini = geom.interpolate(d_ini).asPoint()
                    sub_pts.append(pt_ini)
                    
                    # Percorrer vértices originais, incluindo os que ficam entre d_ini e d_fim
                    for i in range(len(pts_originais) - 1):
                        seg_len = pts_originais[i].distance(pts_originais[i + 1])
                        d_next = d_acc + seg_len
                        
                        # O vértice i+1 está entre d_ini e d_fim?
                        if d_next > d_ini + 0.5 and d_next < d_fim - 0.5:
                            sub_pts.append(pts_originais[i + 1])
                        
                        d_acc = d_next
                    
                    # Adicionar ponto interpolado no final
                    pt_fim = geom.interpolate(d_fim).asPoint()
                    sub_pts.append(pt_fim)
                    
                    # Remover pontos duplicados consecutivos
                    clean_pts = [sub_pts[0]]
                    for p in sub_pts[1:]:
                        if clean_pts[-1].distance(p) > 0.01:
                            clean_pts.append(p)
                    
                    if len(clean_pts) < 2: return None
                    return QgsGeometry.fromPolylineXY(clean_pts)

                for vdata in vias_na_bacia:
                    # Atributos base da feição original
                    orig_fields = vdata['feat'].fields()
                    id_idx = orig_fields.indexOf("id")
                    if id_idx < 0: id_idx = orig_fields.indexOf("ID")
                    id_val = vdata['feat'].attribute(id_idx) if id_idx >= 0 else vdata['feat'].id()
                    cod_val = vdata['feat'].attribute(orig_fields.indexOf("codlograd")) if orig_fields.indexOf("codlograd") >= 0 else ""

                    i_long = max(0.001, abs(vdata['zi'] - vdata['zf']) / vdata['L'])
                    q_cap = self.calcular_capacidade_sarjeta(n_fixo, lam_fixo, cai_fixo, i_long)
                    fator_e = 0.5 if i_long > 0.08 else (0.75 if i_long > 0.04 else 1.0)
                    q_engol_real = q_engol_fixo * fator_e

                    # --- Fase A: Simulação hidráulica para identificar posições de PVs ---
                    pv_dists = []  # Lista de distâncias ao longo do segmento onde PVs serão colocados
                    q_acc = 0.0
                    dist_percorrida = 0.0
                    dist_desde_ultimo_pv = 0.0
                    
                    passo = 5.0
                    while dist_percorrida < vdata['L']:
                        seg_l = min(passo, vdata['L'] - dist_percorrida)
                        q_acc += q_linear * seg_l
                        dist_percorrida += seg_l
                        dist_desde_ultimo_pv += seg_l
                        
                        is_final = dist_percorrida >= vdata['L'] - 2.0
                        gatilho = (q_acc > (q_cap * margem_segur) or 
                                   dist_desde_ultimo_pv >= dist_max or 
                                   (is_final and q_acc > 0.01))
                        
                        if gatilho and dist_desde_ultimo_pv >= dist_min:
                            # Cálculo de shift para o PV (a jusante da captação)
                            shift = max(3.0, min(6.0, (largura_via/2.0 * cai_fixo)/(i_long - 0.01) if i_long > 0.012 else 6.0))
                            curr_pv_dist = min(dist_percorrida + shift, vdata['L'])
                            pv_dists.append(curr_pv_dist)
                            q_acc = 0.0
                            dist_desde_ultimo_pv = 0.0

                    # Garantir PV no ponto final (baixo/confluência) para conectividade
                    if not pv_dists or (vdata['L'] - pv_dists[-1]) > dist_min:
                        pv_dists.append(vdata['L'])
                    elif pv_dists and abs(pv_dists[-1] - vdata['L']) < dist_min:
                        # Se o último PV está muito perto do final, move ele para o final exato
                        pv_dists[-1] = vdata['L']

                    # --- Fase B: Validação Pré-Lançamento ---
                    # B1: Remover PVs redundantes (muito próximos entre si)
                    pv_dists_valid = []
                    for d in pv_dists:
                        if not pv_dists_valid or (d - pv_dists_valid[-1]) >= dist_min:
                            pv_dists_valid.append(d)
                        else:
                            # Substitui o anterior se o atual é o ponto final
                            if abs(d - vdata['L']) < 1.0:
                                pv_dists_valid[-1] = d
                    pv_dists = pv_dists_valid

                    # B2: Verificar que todos os PVs estão dentro do segmento
                    pv_dists = [d for d in pv_dists if 0 < d <= vdata['L'] + 0.1]
                    
                    if not pv_dists:
                        # Segmento muito curto: um único trecho sem PV intermediário
                        # Apenas adicionar PV no final e a rede inteira
                        pv_dists = [vdata['L']]

                    # B3: O primeiro trecho da rede começa no primeiro PV
                    # (NÃO no topo - elimina segmentos curtos e PVs desnecessários no ponto alto)
                    primeiro_pv = pv_dists[0]
                    
                    # Verificação: se o primeiro PV está muito perto do topo (< dist_min),
                    # não precisa de rede antes dele. A rede começa nele.
                    # Se está longe, cria a rede do topo até o primeiro PV para cobertura.
                    rede_inicio = 0.0
                    if primeiro_pv < dist_min * 1.5:
                        # Primeiro PV perto do topo: rede começa no primeiro PV
                        rede_inicio = primeiro_pv
                    else:
                        # Primeiro PV longe do topo: rede começa no topo (dist=0)
                        rede_inicio = 0.0
                    
                    # --- Fase C: Lançamento de Elementos ---
                    # C1: Lançar PVs
                    for pv_d in pv_dists:
                        pt = vdata['geom'].interpolate(pv_d).asPoint()
                        f = QgsFeature(layer_pv.fields())
                        f.setGeometry(QgsGeometry.fromPointXY(pt))
                        f.setAttributes([id_val, cod_val, 0.0, 400.0, 1.0])
                        features_pv.append(f)

                    # C2: Lançar Rede segmentada de PV a PV
                    pontos_rede = [rede_inicio] + pv_dists
                    for k in range(len(pontos_rede) - 1):
                        d1 = pontos_rede[k]
                        d2 = pontos_rede[k + 1]
                        seg_g = extrair_sublinha(vdata['geom'], vdata['pts'], d1, d2)
                        if seg_g is None or seg_g.isEmpty(): continue
                        
                        # Cálculo de cobertura refinado
                        seg_len = seg_g.length()
                        z_ini = get_z(seg_g.asPolyline()[0])
                        z_fim = get_z(seg_g.asPolyline()[-1])
                        slope_local = abs(z_ini - z_fim) / max(0.1, seg_len)
                        s_pipe = max(0.005, slope_local)
                        max_c = 1.0 + max(0, (slope_local - s_pipe) * seg_len)
                        
                        f = QgsFeature(layer_rede.fields())
                        f.setGeometry(seg_g)
                        f.setAttributes([id_val, cod_val, round(seg_len, 2), 400.0, round(max_c, 2)])
                        features_rede.append(f)
                    
                    # C3: Lançar BLs em cada posição de PV (exceto final do segmento)
                    for pv_d in pv_dists[:-1]:  # Não coloca BL no último PV (confluência)
                        pt_bl = vdata['geom'].interpolate(pv_d).asPoint()
                        # Calcular direção perpendicular
                        d_probe = min(pv_d + 0.5, vdata['L'])
                        d_back = max(pv_d - 0.5, 0.0)
                        if d_probe > pv_d:
                            pt_n = vdata['geom'].interpolate(d_probe).asPoint()
                            dx, dy = pt_n.x() - pt_bl.x(), pt_n.y() - pt_bl.y()
                        else:
                            pt_b = vdata['geom'].interpolate(d_back).asPoint()
                            dx, dy = pt_bl.x() - pt_b.x(), pt_bl.y() - pt_b.y()
                        
                        leng = math.sqrt(dx*dx + dy*dy)
                        if leng > 0:
                            nx, ny = -dy/leng, dx/leng
                            offset = largura_via / 2.0
                            for side in [-1, 1]:
                                fbl = QgsFeature(layer_bl.fields())
                                fbl.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(
                                    pt_bl.x() + nx * offset * side, 
                                    pt_bl.y() + ny * offset * side)))
                                fbl.setAttributes([id_val, cod_val, 0.0, 0.0, 0.0])
                                features_bl.append(fbl)

            # --- 7. Validação Final e Relatório ---
            self.dockwidget.add_result(f"\n--- VALIDAÇÃO PRÉ-LANÇAMENTO ---")
            
            # V1: Verificar segmentos de rede muito curtos
            segs_curtos = 0
            features_rede_valid = []
            for f in features_rede:
                if f.geometry().length() < 1.0:
                    segs_curtos += 1
                else:
                    features_rede_valid.append(f)
            features_rede = features_rede_valid
            if segs_curtos > 0:
                self.dockwidget.add_result(f"  Removidos {segs_curtos} segmento(s) de rede < 1m (stubs)")
            
            # V2: Verificar PVs duplicados (muito próximos)
            pvs_removidos = 0
            features_pv_valid = []
            for f in features_pv:
                pt = f.geometry().asPoint()
                duplicado = False
                for fv in features_pv_valid:
                    pt_v = fv.geometry().asPoint()
                    if pt.distance(pt_v) < 1.0:
                        duplicado = True
                        pvs_removidos += 1
                        break
                if not duplicado:
                    features_pv_valid.append(f)
            features_pv = features_pv_valid
            if pvs_removidos > 0:
                self.dockwidget.add_result(f"  Removidos {pvs_removidos} PV(s) duplicado(s) (< 1m de distância)")
            
            self.dockwidget.add_result(f"  Elementos válidos: {len(features_pv)} PVs, {len(features_bl)} BLs, {len(features_rede)} Redes")

            # 8. Adicionar camadas ao projeto
            if features_pv or features_rede:
                pr_pv.addFeatures(features_pv)
                pr_bl.addFeatures(features_bl)
                pr_rede.addFeatures(features_rede)
                
                # Estilização
                from qgis.core import QgsLineSymbol, QgsMarkerSymbol, QgsSingleSymbolRenderer
                
                sym_rede = QgsLineSymbol.createSimple({'line_color': '0,255,0,255', 'line_width': '1.2'})
                layer_rede.setRenderer(QgsSingleSymbolRenderer(sym_rede))
                
                sym_pv = QgsMarkerSymbol.createSimple({'name': 'circle', 'color': '100,100,100,255', 'size': '3'})
                layer_pv.setRenderer(QgsSingleSymbolRenderer(sym_pv))
                
                sym_bl = QgsMarkerSymbol.createSimple({'name': 'square', 'color': '200,50,50,255', 'size': '2'})
                layer_bl.setRenderer(QgsSingleSymbolRenderer(sym_bl))

                self.add_layer_to_group(layer_rede, at_bottom=True)
                self.add_layer_to_group(layer_bl)
                self.add_layer_to_group(layer_pv)
                
                self.dockwidget.add_result(f"\nSUCESSO: Otimização concluída!\n- {len(features_pv)} PVs\n- {len(features_bl)} BLs\n- {len(features_rede)} Tramas de Rede")
            else:
                self.dockwidget.add_result("Aviso: Nenhum elemento gerado. Verifique as bacias e seleções.")

        except Exception as e:
            self.dockwidget.add_result(f"Erro Crítico na Otimização: {str(e)}")
            import traceback
            QgsMessageLog.logMessage(traceback.format_exc(), "Medir 3D", Qgis.Critical)
