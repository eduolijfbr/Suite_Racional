import os
from qgis.PyQt.QtCore import Qt, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import QgsProject, QgsMapLayerType, QgsSettings, QgsVectorLayer, QgsField, QgsMessageLog, Qgis
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

    def initGui(self):
        # Configurar menu e barra de ferramentas
        from qgis.PyQt.QtWidgets import QToolBar
        icon_path = os.path.join(self.plugin_dir, 'icon.svg')
        self.action = QAction(QIcon(icon_path), "Medir 3D", self.iface.mainWindow())
        self.action.setObjectName("Medir3DAction")
        self.action.setWhatsThis("Medir distâncias e perfis 3D")
        self.action.setStatusTip("Abrir painel Medir 3D")
        self.action.triggered.connect(self.run)

        self.toolbar_name = 'SuiteRacionalPro'
        self.toolbar = self.iface.mainWindow().findChild(QToolBar, self.toolbar_name)
        if not self.toolbar:
            self.toolbar = self.iface.addToolBar('Suite Racional Pro')
            self.toolbar.setObjectName(self.toolbar_name)
            
        self.toolbar.addAction(self.action)
        self.iface.addPluginToMenu("&Suite Racional Pro", self.action)

    def unload(self):
        self.limpar_dados(permanente=True)
        if self.dockwidget:
            self.iface.removeDockWidget(self.dockwidget)
        self.iface.removePluginMenu("&Suite Racional Pro", self.action)
        if hasattr(self, 'toolbar') and self.toolbar:
            self.toolbar.removeAction(self.action)

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
            self.dockwidget.btn_carregar_historico.clicked.connect(self.carregar_historico)
            self.dockwidget.btn_excluir_historico.clicked.connect(self.excluir_historico)
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
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
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
        QgsProject.instance().addMapLayer(view_rede)
        
        # PVs no mapa (Como Temp)
        if layer_pv_db.isValid() and layer_pv_db.featureCount() > 0:
            view_pv = QgsVectorLayer(f"Point?crs={crs}", "PVs (Temp)", "memory")
            view_pv.dataProvider().addAttributes(layer_pv_db.fields())
            view_pv.updateFields()
            view_pv.dataProvider().addFeatures(list(layer_pv_db.getFeatures()))
            QgsProject.instance().addMapLayer(view_pv)
            self.dockwidget.add_result(f"\nRecuperados {layer_pv_db.featureCount()} PVs.")
            
        self.dockwidget.add_result("\nPronto para novo cálculo ou edição.")

    def atualizar_camadas(self, layers=None):
        settings = QgsSettings()
        # Salva o nome da camada atualmente selecionada (se houver) antes de limpar
        camada_atual = self.dockwidget.combo_layer.currentText()
        if not camada_atual:
            camada_atual = settings.value("Medir3D/lastLayer", "")

        self.dockwidget.combo_layer.blockSignals(True)
        self.dockwidget.combo_layer.clear()
        
        todas_camadas = QgsProject.instance().mapLayers().values()
        for layer in todas_camadas:
            if layer.type() == QgsMapLayerType.RasterLayer:
                self.dockwidget.combo_layer.addItem(layer.name(), layer.id())
        
        # Tenta restaurar a seleção anterior pelo nome
        index = self.dockwidget.combo_layer.findText(camada_atual)
        if index >= 0:
            self.dockwidget.combo_layer.setCurrentIndex(index)
            
        self.dockwidget.combo_layer.blockSignals(False)

    def guardar_selecao_camada(self):
        if self.dockwidget:
            layer_name = self.dockwidget.combo_layer.currentText()
            if layer_name:
                settings = QgsSettings()
                settings.setValue("Medir3D/lastLayer", layer_name)

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

