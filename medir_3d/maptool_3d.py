import math
import os
from qgis.core import (
    QgsPointXY, 
    QgsRaster,
    QgsMessageLog,
    Qgis,
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    QgsGeometry,
    QgsField,
    QgsWkbTypes,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform
)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.PyQt.QtCore import Qt, pyqtSignal, QVariant
from qgis.PyQt.QtGui import QColor

class MapTool3D(QgsMapToolEmitPoint):
    
    measurement_done = pyqtSignal(str)
    
    def __init__(self, canvas, get_raster_layer_callback, get_slope_callback, get_dist_pv_callback, get_diameter_callback):
        super().__init__(canvas)
        self.canvas = canvas
        self.get_raster_layer_callback = get_raster_layer_callback
        self.get_slope_callback = get_slope_callback
        self.get_dist_pv_callback = get_dist_pv_callback
        self.get_diameter_callback = get_diameter_callback
        self.points = []
        self.z_values = []
        self.last_points = []
        self.last_pvs = []  # Armazena resultado dos PVs para perfil
        self.last_perfil_terrain = []  # Armazena perfil do terreno
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.total_dist_2d = 0.0
        self.total_dist_3d = 0.0
        
        self.rb_line = QgsRubberBand(self.canvas, QgsWkbTypes.LineGeometry)
        self.rb_line.setColor(QColor(255, 0, 0))
        self.rb_line.setWidth(2)
        
        self.rb_points = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.rb_points.setColor(QColor(0, 0, 255))
        self.rb_points.setIconSize(7)

    def deactivate(self):
        self.reset_measurement()
        super().deactivate()

    def get_z_at_point(self, point, raster_layer):
        try:
            # Transforma ponto para o CRS da camada raster
            canvas_crs = self.canvas.mapSettings().destinationCrs()
            raster_crs = raster_layer.crs()
            
            if canvas_crs != raster_crs:
                transform = QgsCoordinateTransform(canvas_crs, raster_crs, QgsProject.instance())
                pt_trans = transform.transform(point)
            else:
                pt_trans = point

            ident = raster_layer.dataProvider().identify(pt_trans, QgsRaster.IdentifyFormatValue)
            if ident.isValid() and ident.results():
                # Tenta pegar o primeiro valor não-nulo
                for val in ident.results().values():
                    if val is not None:
                        return float(val)
        except Exception as e:
            QgsMessageLog.logMessage(f"Erro ao obter Z: {str(e)}", "Medir 3D", Qgis.Warning)
        return 0.0

    def canvasReleaseEvent(self, event):
        raster_layer = self.get_raster_layer_callback()
        if not raster_layer:
            self.measurement_done.emit("Erro: Nenhuma camada raster selecionada.")
            self.reset_measurement()
            return

        if event.button() == Qt.MouseButton.RightButton:
            self.finalizar_medicao(raster_layer)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            point = self.toMapCoordinates(event.pos())
            z_value = self.get_z_at_point(point, raster_layer)
            
            self.points.append(point)
            self.z_values.append(z_value)
            
            self.rb_points.addPoint(point, False)
            self.rb_points.updatePosition()
            self.rb_points.update()
            
            if len(self.points) == 1:
                self.rb_line.reset(QgsWkbTypes.LineGeometry)
                self.rb_line.addPoint(point, False)
                self.measurement_done.emit(f"Ponto Inicial (Z: {z_value:.2f}) adicionado.")
                
            if len(self.points) > 1:
                self.rb_line.addPoint(point, True)
                self.rb_line.updatePosition()
                self.rb_line.update()
                self.calcular_distancia_segmento(raster_layer)

    def calcular_distancia_segmento(self, raster_layer):
        pt1, pt2 = self.points[-2], self.points[-1]
        segmentos = 10
        dist_2d_seg = math.sqrt((pt2.x() - pt1.x())**2 + (pt2.y() - pt1.y())**2)
        
        if dist_2d_seg == 0:
            return

        passo_x = (pt2.x() - pt1.x()) / segmentos
        passo_y = (pt2.y() - pt1.y()) / segmentos
        
        dist_3d_seg = 0.0
        ponto_anterior = None
        z_anterior = None

        for i in range(segmentos + 1):
            x = pt1.x() + (passo_x * i)
            y = pt1.y() + (passo_y * i)
            ponto_atual = QgsPointXY(x, y)
            z_atual = self.get_z_at_point(ponto_atual, raster_layer)

            if ponto_anterior is not None and z_anterior is not None:
                dx = ponto_atual.x() - ponto_anterior.x()
                dy = ponto_atual.y() - ponto_anterior.y()
                dz = z_atual - z_anterior
                dist_3d_seg += math.sqrt(dx**2 + dy**2 + dz**2)

            ponto_anterior = ponto_atual
            z_anterior = z_atual

        self.total_dist_2d += dist_2d_seg
        self.total_dist_3d += dist_3d_seg
        
        self.measurement_done.emit(f"--- Somatório Atual ---")
        self.measurement_done.emit(f"Distância 2D Acumulada: {self.total_dist_2d:.2f} m")
        self.measurement_done.emit(f"Distância 3D Acumulada: {self.total_dist_3d:.2f} m\n")

    def finalizar_medicao(self, raster_layer):
        if len(self.points) > 1:
            # Validar tendência de declividade (Independência da ordem de clique)
            # Se o ponto final for mais alto que o inicial, invertemos a lista
            # para que o cálculo hidráulico (que assume descida) funcione corretamente.
            if self.z_values[-1] > self.z_values[0]:
                self.points.reverse()
                self.z_values.reverse()
                self.measurement_done.emit("Nota: Traçado detectado como 'subida'. Invertendo para cálculo de drenagem (alto -> baixo).")

            self.last_points = list(self.points)
            self.criar_camada_rede()
            self.criar_camada_pv(raster_layer, self.last_points)
            self.measurement_done.emit(f"=== MEDIÇÃO FINALIZADA ===")
            self.measurement_done.emit(f"TOTAL 2D: {self.total_dist_2d:.2f} m")
            self.measurement_done.emit(f"TOTAL 3D: {self.total_dist_3d:.2f} m")
            self.measurement_done.emit(f"Camadas 'Rede (Temp)' e 'PVs (Temp)' geradas.")
        elif len(self.points) == 1:
            self.measurement_done.emit(f"Medição cancelada (apenas 1 ponto).")
        self.reset_measurement()

    def reset_measurement(self):
        self.points = []
        self.z_values = []
        self.total_dist_2d = 0.0
        self.total_dist_3d = 0.0
        self.rb_line.reset(QgsWkbTypes.LineGeometry)
        self.rb_points.reset(QgsWkbTypes.PointGeometry)

    def criar_camada_rede(self):
        crs = self.canvas.mapSettings().destinationCrs().authid()
        layer = QgsVectorLayer(f"LineString?crs={crs}", "Rede (Temp)", "memory")
        pr = layer.dataProvider()
        pr.addAttributes([
            QgsField("dist_2d_m", QVariant.Double),
            QgsField("dist_3d_m", QVariant.Double)
        ])
        layer.updateFields()
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPolylineXY(self.points))
        feat.setAttributes([self.total_dist_2d, self.total_dist_3d])
        pr.addFeature(feat)
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)

    def amostrar_perfil_terreno(self, original_points, raster_layer, passo=1.0):
        """Amostra o perfil do terreno ao longo da polyline."""
        linha = QgsGeometry.fromPolylineXY(original_points)
        comprimento = linha.length()
        perfil = []
        d = 0.0
        while d <= comprimento:
            pt_geom = linha.interpolate(d)
            pt = pt_geom.asPoint()
            z = self.get_z_at_point(QgsPointXY(pt.x(), pt.y()), raster_layer)
            perfil.append((d, z))
            d += passo
        # Ponto final
        if perfil[-1][0] < comprimento:
            pt_geom = linha.interpolate(comprimento)
            pt = pt_geom.asPoint()
            z = self.get_z_at_point(QgsPointXY(pt.x(), pt.y()), raster_layer)
            perfil.append((comprimento, z))
        return perfil

    def calcular_pvs_dinamicos(self, original_points, raster_layer, slope_pct, dist_max_seguranca, diam_mm):
        """
        Algoritmo de lançamento de PVs para rede de saneamento.
        Garante que a declividade da rede não ultrapasse a declividade solicitada,
        criando degraus (tubos de queda) nos PVs quando o terreno cair abruptamente.
        A distância máxima entre PVs é respeitada, e se for necessária uma profundidade
        maior que o limite, a distância entre PVs é encurtada.
        """
        depth_total_req = (2.5 * (diam_mm / 1000.0)) + 0.20
        COB_MIN = depth_total_req
        PROF_MAX = 5.0
        DIST_MAX = max(10.0, dist_max_seguranca)
        DIST_MIN = 10.0
        if DIST_MAX < DIST_MIN: DIST_MAX = DIST_MIN
        PASSO = 1.0

        linha = QgsGeometry.fromPolylineXY(original_points)
        compr_total = linha.length()
        
        if compr_total < 1.0:
            return []

        perfil = self.amostrar_perfil_terreno(original_points, raster_layer, PASSO)
        self.last_perfil_terrain = perfil
        
        def get_z_terr(d):
            pt_geom = linha.interpolate(d)
            if not pt_geom: return 0.0
            pt = pt_geom.asPoint()
            return self.get_z_at_point(QgsPointXY(pt.x(), pt.y()), raster_layer)

        pvs = []
        d_atual = 0.0
        cf_in_max = float('inf')
        
        while d_atual < compr_total:
            restante = compr_total - d_atual
            L_max_teste = min(DIST_MAX, restante)
            L_min_teste = min(DIST_MIN, restante)
            
            melhor_L = L_min_teste
            melhor_cf_out = None
            melhor_slope = slope_pct
            
            L_teste = L_max_teste
            
            while L_teste >= L_min_teste:
                if d_atual == 0:
                    cf_start_base = get_z_terr(0) - COB_MIN
                else:
                    cf_start_base = cf_in_max
                
                req_slope = slope_pct
                
                # Verifica afloramento (falta de cobertura) em todos os pontos do trecho
                max_deficit = 0.0
                d_check = 0.0
                while d_check <= L_teste:
                    z_t = get_z_terr(d_atual + d_check)
                    cf_t = cf_start_base - (d_check * req_slope)
                    prof_t = z_t - cf_t
                    
                    if prof_t < COB_MIN:
                        deficit = COB_MIN - prof_t
                        if deficit > max_deficit:
                            max_deficit = deficit
                    
                    d_check += PASSO
                
                # Ajusta a cota de saída do PV para garantir a cobertura (introduzindo tubo de queda se necessário)
                cf_start_adj = cf_start_base - max_deficit
                
                # Checa a profundidade no início e fim do trecho
                z_atual_pv = get_z_terr(d_atual)
                prof_start = z_atual_pv - cf_start_adj
                
                z_fim_pv = get_z_terr(d_atual + L_teste)
                cf_fim_adj = cf_start_adj - (L_teste * req_slope)
                prof_fim = z_fim_pv - cf_fim_adj
                
                # Se profundidades OK ou se não podemos reduzir mais, aceitamos este comprimento
                if (prof_start <= PROF_MAX and prof_fim <= PROF_MAX) or L_teste == L_min_teste:
                    melhor_L = L_teste
                    melhor_cf_out = cf_start_adj
                    melhor_slope = req_slope
                    break
                
                # Se muito profundo, reduz a distância entre os PVs e tenta novamente
                L_teste -= 5.0
                if L_teste < L_min_teste:
                    L_teste = L_min_teste

            z_atual = get_z_terr(d_atual)
            pt_geom = linha.interpolate(d_atual)
            pt = QgsPointXY(pt_geom.asPoint().x(), pt_geom.asPoint().y())
            
            cf_out = melhor_cf_out
            cf_in = cf_in_max if cf_in_max != float('inf') else cf_out
            
            cob_in = (z_atual - cf_in) - (diam_mm / 1000.0) - 0.20
            cob_out = (z_atual - cf_out) - (diam_mm / 1000.0) - 0.20

            pvs.append({
                "pt": pt,
                "z_terr": z_atual,
                "cf_entrada": cf_in,
                "cf_saida": cf_out,
                "profund": z_atual - min(cf_in, cf_out),
                "cob_entrada": cob_in,
                "cob_saida": cob_out,
                "dist_acum": d_atual,
                "dist_parcial": melhor_L if d_atual > 0 else 0.0,
                "incl_aplicada": melhor_slope * 100
            })
            
            # Cota de chegada do tubo no próximo PV
            cf_in_max = melhor_cf_out - (melhor_L * melhor_slope)
            d_atual += melhor_L
            
            if d_atual >= compr_total - 0.001:
                z_fim = get_z_terr(compr_total)
                cf_end = cf_in_max
                pt_fim_geom = linha.interpolate(compr_total)
                pt_fim = QgsPointXY(pt_fim_geom.asPoint().x(), pt_fim_geom.asPoint().y())
                
                cob_in_end = (z_fim - cf_end) - (diam_mm / 1000.0) - 0.20
                pvs.append({
                    "pt": pt_fim,
                    "z_terr": z_fim,
                    "cf_entrada": cf_end,
                    "cf_saida": cf_end,
                    "profund": z_fim - cf_end,
                    "cob_entrada": cob_in_end,
                    "cob_saida": cob_in_end,
                    "dist_acum": compr_total,
                    "dist_parcial": melhor_L,
                    "incl_aplicada": slope_pct * 100
                })
                break
                
        self.last_pvs = pvs
        
        # Amostrar o terreno para plotagem com 1m para garantir que a array seja coerente
        self.last_perfil_terrain = self.amostrar_perfil_terreno(original_points, raster_layer, 1.0)
        
        return pvs

    def criar_camada_pv(self, raster_layer, pts=None, zs=None):
        if pts is None:
            pts = self.points
            
        slope_pct = self.get_slope_callback() / 100.0
        dist_max_seguranca = self.get_dist_pv_callback()
        diam_mm = self.get_diameter_callback()
        pvs_calc = self.calcular_pvs_dinamicos(pts, raster_layer, slope_pct, dist_max_seguranca, diam_mm)
            
        crs = self.canvas.mapSettings().destinationCrs().authid()
        layer = QgsVectorLayer(f"Point?crs={crs}", "PVs (Temp)", "memory")
        pr = layer.dataProvider()
        
        pr.addAttributes([
            QgsField("id_pv", QVariant.Int),
            QgsField("cota_terr", QVariant.Double),
            QgsField("cf_entrada", QVariant.Double),
            QgsField("cf_saida", QVariant.Double),
            QgsField("profund", QVariant.Double),
            QgsField("cob_ent", QVariant.Double),
            QgsField("cob_sai", QVariant.Double),
            QgsField("dist_parc", QVariant.Double),
            QgsField("inclinacao", QVariant.Double)
        ])
        layer.updateFields()
        
        features = []
        pv_count = 1
        
        for pv in pvs_calc:
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPointXY(pv["pt"]))
            feat.setAttributes([
                pv_count, 
                round(pv["z_terr"], 3), 
                round(pv["cf_entrada"], 3), 
                round(pv["cf_saida"], 3), 
                round(pv["profund"], 3),
                round(pv["cob_entrada"], 3),
                round(pv["cob_saida"], 3),
                round(pv["dist_parcial"], 3),
                round(pv["incl_aplicada"], 2)
            ])
            features.append(feat)
            pv_count += 1
            
        pr.addFeatures(features)
        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)
        
        self.measurement_done.emit(f"--- {len(pvs_calc)} PVs gerados (Declive: {slope_pct*100:.1f}%) ---")
        
    def refazer_pvs(self, raster_layer):
        if not self.last_points:
            self.measurement_done.emit("Nenhuma medição anterior para refazer PVs.")
            return
            
        layers_to_remove = []
        for layer in QgsProject.instance().mapLayers().values():
            if layer.name() == "PVs (Temp)":
                layers_to_remove.append(layer.id())
                
        if layers_to_remove:
            QgsProject.instance().removeMapLayers(layers_to_remove)
            
        self.criar_camada_pv(raster_layer, self.last_points)
        self.measurement_done.emit("--- PVs Recalculados com sucesso ---")
    
    def gerar_perfil(self, show=True, save_path=None):
        """Gera o perfil longitudinal com matplotlib."""
        if not self.last_pvs or not self.last_perfil_terrain:
            self.measurement_done.emit("Nenhum dado de perfil disponível.")
            return
        
        try:
            import matplotlib.pyplot as plt
            import os
            
            # Dados do terreno
            dist_terr = [p[0] for p in self.last_perfil_terrain]
            z_terr = [p[1] for p in self.last_perfil_terrain]
            
            # Dados dos PVs (cota fundo = linha do tubo)
            dist_pvs = [pv["dist_acum"] for pv in self.last_pvs]
            z_saida = [pv["cf_saida"] for pv in self.last_pvs]
            z_entrada = [pv["cf_entrada"] for pv in self.last_pvs]
            
            # Styling profissional
            plt.style.use('seaborn-v0_8-whitegrid')
            fig, ax = plt.subplots(figsize=(15, 7))
            
            # Perfil do terreno (MDT)
            ax.fill_between(dist_terr, z_terr, min(z_terr) - 5, alpha=0.2, color='#8B4513', label='MDT')
            ax.plot(dist_terr, z_terr, color='#6B4226', linewidth=2.5, label='Superfície do Terreno')
            
            # Linha do fundo da rede (tubo dentado)
            primeiro_segmento = True
            for i in range(len(self.last_pvs) - 1):
                p_curr = self.last_pvs[i]
                p_next = self.last_pvs[i+1]
                
                label_rede = 'Geratriz Inferior (Fundo)' if primeiro_segmento else ""
                ax.plot([p_curr["dist_acum"], p_next["dist_acum"]], 
                        [p_curr["cf_saida"], p_next["cf_entrada"]], 
                        color='#0052cc', linewidth=2.5, linestyle='-', label=label_rede)
                primeiro_segmento = False
                
                # Queda (vertical) no PV destino se houver degrau
                if abs(p_next["cf_entrada"] - p_next["cf_saida"]) > 0.001:
                    ax.plot([p_next["dist_acum"], p_next["dist_acum"]], 
                            [p_next["cf_entrada"], p_next["cf_saida"]], 
                            color='#0052cc', linewidth=2.5, linestyle='-')
            
            # Estruturas dos PVs e Anotações Dinâmicas para evitar sobreposição
            for i, pv in enumerate(self.last_pvs):
                # Linha vertical representando o PV do terreno até a menor cota
                min_cf = min(pv["cf_entrada"], pv["cf_saida"])
                ax.plot([pv["dist_acum"], pv["dist_acum"]], 
                       [pv["z_terr"], min_cf], 
                       color='#333333', linewidth=1.5, linestyle='--', alpha=0.7)
                
                # Intercalador dinâmico avançado (4 níveis com maior distanciamento)
                nivel = i % 4
                offset_y = 20 + (nivel * 45)
                
                # Cor do card condicional (Atenção se prof > 4.5m)
                cor_card = '#FFE4B5' if pv["profund"] < 4.5 else '#FF7F50'
                
                queda = pv["cf_entrada"] - pv["cf_saida"]
                texto_queda = f'\nQueda: {queda:.2f}m' if queda >= 0.01 else ''
                
                ax.annotate(f'PV{i+1}\nProf: {pv["profund"]:.2f}m\nCob Ent: {pv["cob_entrada"]:.2f}m{texto_queda}', 
                           xy=(pv["dist_acum"], pv["z_terr"]), 
                           xytext=(0, offset_y), textcoords='offset points',
                           ha='center', va='bottom', fontsize=9, fontweight='medium',
                           bbox=dict(boxstyle='round,pad=0.4', facecolor=cor_card, edgecolor='#444444', alpha=0.95),
                           arrowprops=dict(arrowstyle="->", color='#444444', alpha=0.6, lw=1.2))
            
            # Distâncias entre PVs (setas com texto) com correção de overlap
            for i in range(1, len(self.last_pvs)):
                p1, p2 = self.last_pvs[i-1], self.last_pvs[i]
                d1, d2 = p1["dist_acum"], p2["dist_acum"]
                d_meio = (d1 + d2) / 2
                
                # Ponto médio da cota
                z_meio_v = (p1["cf_saida"] + p2["cf_entrada"]) / 2
                
                dist_entre = d2 - d1
                incl_texto = p1["incl_aplicada"]
                
                # Linha de cota e texto
                ax.annotate('', xy=(d2, z_meio_v - 0.3), xytext=(d1, z_meio_v - 0.3),
                           arrowprops=dict(arrowstyle='<->', color='#2E8B57', lw=1.5, alpha=0.8))
                
                ax.text(d_meio, z_meio_v - 0.6, f'{dist_entre:.1f}m ({incl_texto:.1f}%)',
                       ha='center', va='top', fontsize=8, color='#004d00', fontweight='bold',
                       bbox=dict(boxstyle='square,pad=0.1', facecolor='white', edgecolor='none', alpha=0.7))
            
            ax.set_xlabel('Estaqueamento (m)', fontsize=12, fontweight='bold', color='#333333')
            ax.set_ylabel('Cota (m)', fontsize=12, fontweight='bold', color='#333333')
            ax.set_title(f'Perfil Longitudinal da Rede de Coleta\nDeclividade Base: {self.get_slope_callback():.1f}% | Diâmetro: {self.get_diameter_callback()}mm', 
                         fontsize=14, fontweight='bold', color='#1a1a1a', pad=20)
            
            # Estilização das legendas e grid
            ax.legend(loc='upper left', frameon=True, fancybox=True, framealpha=0.9, shadow=True, borderpad=1)
            ax.grid(True, linestyle=':', alpha=0.6, color='#999999')
            ax.set_xlim(0 - (dist_terr[-1]*0.05), dist_terr[-1] * 1.05) # Margem maior
            
            # Garante espaço para os labels superiores (offset_y alto)
            ylim = ax.get_ylim()
            ax.set_ylim(ylim[0], ylim[1] + (ylim[1]-ylim[0])*0.3)
            
            plt.tight_layout()
            
            if save_path:
                caminho_perfil = save_path
            else:
                plugin_dir = os.path.dirname(__file__)
                caminho_perfil = os.path.join(plugin_dir, "perfil_rede.png")
                
            fig.savefig(caminho_perfil, dpi=150, bbox_inches='tight')
            plt.close(fig)
            
            if show:
                self.measurement_done.emit(f"Perfil gerado e salvo em: {caminho_perfil}")
                os.startfile(caminho_perfil)
            else:
                self.measurement_done.emit(f"Perfil documentado em: {caminho_perfil}")
            
        except ImportError:
            self.measurement_done.emit("Erro: matplotlib não encontrado.")
        except Exception as e:
            self.measurement_done.emit(f"Erro ao gerar perfil: {str(e)}")
