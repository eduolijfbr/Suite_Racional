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
    QgsWkbTypes
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
        ident = raster_layer.dataProvider().identify(point, QgsRaster.IdentifyFormatValue)
        if ident.isValid() and ident.results():
            val = list(ident.results().values())[0]
            if val is not None:
                return float(val)
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
        Algoritmo de lançamento de PVs para rede de saneamento baseado em 
        regras de engenharia (Maximização de Distância com Limite de Profundidade):
        
        REGRAS:
        1. PV1 no início: profundidade mínima de 2m.
        2. Tenta lançar o próximo PV na Maior Distância Permitida (dist_max_seguranca).
        3. Verifica se a Profundidade do PV e a cobertura do tubo ao longo
           deste trecho não excedem limites.
        4. O Tubo DEVE ter pelo menos 2m de cobertura em todos os pontos do trecho.
        5. A prof. inicial do trecho deve ser a mínima necessária para garantir (4).
        6. Se a prof. num trecho ficar muito alta (> PROF_MAX), 
           a distância do trecho é reduzida até um mínimo aceitável (10m).
        7. Distâncias são puramente ditadas pela topografia, inclinação e PROF_MAX.
        """
        # Fórmula Técnica: Cobertura(1.5*D) + Diâmetro(D) + Berço(0.20) = 2.5*D + 0.20
        depth_total_req = (2.5 * (diam_mm / 1000.0)) + 0.20
        COB_MIN = depth_total_req     # No código, COB_MIN representa a profundidade total da vala
        PROF_MAX = 5.0        # Profundidade máxima desejável para um PV
        DIST_MAX = max(10.0, dist_max_seguranca) # Distância MÁXIMA entre PVs
        DIST_MIN = 10.0       # Distância MÍNIMA entre PVs (evitar PVs colados)
        if DIST_MAX < DIST_MIN: DIST_MAX = DIST_MIN
        PASSO = 1.0           # Resolução de amostragem no terreno

        linha = QgsGeometry.fromPolylineXY(original_points)
        compr_total = linha.length()
        
        if compr_total < 1.0:
            return []

        # Amostramos o perfil do terreno ao longo do traçado
        perfil = self.amostrar_perfil_terreno(original_points, raster_layer, PASSO)
        self.last_perfil_terrain = perfil
        
        def get_z_terr(d):
            pt_geom = linha.interpolate(d)
            if not pt_geom: return 0.0
            pt = pt_geom.asPoint()
            return self.get_z_at_point(QgsPointXY(pt.x(), pt.y()), raster_layer)

        pvs = []
        d_atual = 0.0
        cf_in_max = float('inf')  # Restrição da cota de chegada do tubo anterior
        
        while d_atual < compr_total:
            restante = compr_total - d_atual
            
            # Tentar de DIST_MAX até DIST_MIN no trecho restante
            L_max_teste = min(DIST_MAX, restante)
            L_min_teste = min(DIST_MIN, restante)
            
            melhor_L = L_min_teste
            melhor_cf_out = None
            
            L_teste = L_max_teste
            
            while L_teste >= L_min_teste:
                # Cota necessária no começo deste L_teste para que o tubo 
                # NUNCA fique com cobertura < COB_MIN
                cf_req = float('inf')
                d_check = 0.0
                
                while d_check <= L_teste + 0.001:
                    d_global = d_atual + d_check
                    z_terr = get_z_terr(d_global)
                    
                    limit = z_terr - COB_MIN + (d_check * slope_pct)
                    if limit < cf_req:
                        cf_req = limit
                        
                    d_check += PASSO
                
                # cf_req é a cota de saída estritamente necessária por conta da topografia à frente.
                # A gravidade impede que o tubo DO NOVO TRECHO inicie
                # acima da cota do tubo DO TRECHO ANTERIOR chegando no PV.
                cf_out = min(cf_req, cf_in_max)
                
                # Se o terreno permite subir o tubo (topografia favorável),
                # garantimos que ele não fique mais fundo do que o necessário no início.
                cf_out_ideal = get_z_terr(d_atual) - COB_MIN
                # O tubo pode subir até cf_out_ideal, desde que não suba acima da cota de chegada (cf_in_max)
                # E não suba acima do que a topografia à frente exige (cf_req)
                if cf_out < cf_out_ideal and cf_out_ideal <= cf_in_max and cf_out_ideal <= cf_req:
                     cf_out = cf_out_ideal
                
                # Qual será a profundidade real deste PV se usarmos cf_out?
                z_atual = get_z_terr(d_atual)
                prof_start = z_atual - cf_out
                
                # Se a profundidade for tolerável, ótimo, achei a maior distância!
                if prof_start <= PROF_MAX:
                    melhor_L = L_teste
                    melhor_cf_out = cf_out
                    break
                
                melhor_L = L_teste
                melhor_cf_out = cf_out
                L_teste -= 1.0
                
            # Adicionar o PV a montante
            z_atual = get_z_terr(d_atual)
            
            pt_geom = linha.interpolate(d_atual)
            pt = QgsPointXY(pt_geom.asPoint().x(), pt_geom.asPoint().y())
            
            # Cota de saída deste PV
            cf_out = melhor_cf_out
            # Cota de entrada vindo do trecho anterior
            # No primeiro PV, entrada = saída
            cf_in = cf_in_max if cf_in_max != float('inf') else cf_out
            
            # Cobertura = Profundidade - Diâmetro - Berço(0.20)
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
                "incl_aplicada": slope_pct * 100
            })
            
            # Atualiza qual a cota que este tubo vai CHEGAR no próximo PV
            cf_in_max = melhor_cf_out - (melhor_L * slope_pct)
            d_atual += melhor_L
            
            # Se chegou perto o suficiente do final, força o fechamento do PV final
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
                
                # Intercalador dinâmico avançado (3 níveis)
                nivel = i % 3
                offset_y = 15 + (nivel * 35)
                
                # Cor do card condicional (Atenção se prof > 4.5m)
                cor_card = '#FFE4B5' if pv["profund"] < 4.5 else '#FFA07A'
                
                ax.annotate(f'PV{i+1}\nProf: {pv["profund"]:.2f}m\nCob Ent: {pv["cob_entrada"]:.2f}m | Sai: {pv["cob_saida"]:.2f}m', 
                           xy=(pv["dist_acum"], pv["z_terr"]), 
                           xytext=(0, offset_y), textcoords='offset points',
                           ha='center', va='bottom', fontsize=8,
                           bbox=dict(boxstyle='round,pad=0.3', facecolor=cor_card, edgecolor='#666666', alpha=0.9),
                           arrowprops=dict(arrowstyle="-", color='#666666', alpha=0.5))
            
            # Distâncias entre PVs (setas com texto)
            for i in range(1, len(self.last_pvs)):
                d1 = self.last_pvs[i-1]["dist_acum"]
                d2 = self.last_pvs[i]["dist_acum"]
                d_meio = (d1 + d2) / 2
                # Ponto médio da cota para posicionar o texto da distância
                z_m1 = self.last_pvs[i-1]["cf_saida"]
                z_m2 = self.last_pvs[i]["cf_entrada"]
                z_meio_v = (z_m1 + z_m2) / 2
                
                dist_entre = d2 - d1
                ax.annotate('', xy=(d2, z_meio_v - 0.5), xytext=(d1, z_meio_v - 0.5),
                           arrowprops=dict(arrowstyle='<->', color='#2E8B57', lw=1.2, alpha=0.7))
                ax.text(d_meio, z_meio_v - 1.2, f'{dist_entre:.1f}m',
                       ha='center', va='top', fontsize=8, color='#006400',
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='none', alpha=0.8))
            
            ax.set_xlabel('Estaqueamento (m)', fontsize=12, fontweight='bold', color='#333333')
            ax.set_ylabel('Cota (m)', fontsize=12, fontweight='bold', color='#333333')
            ax.set_title(f'Perfil Longitudinal da Rede de Coleta\nDeclividade Base: {self.get_slope_callback():.1f}% | Diâmetro: {self.get_diameter_callback()}mm', 
                         fontsize=14, fontweight='bold', color='#1a1a1a', pad=20)
            
            # Estilização das legendas e grid
            ax.legend(loc='upper right', frameon=True, fancybox=True, framealpha=0.9, shadow=True, borderpad=1)
            ax.grid(True, linestyle=':', alpha=0.6, color='#999999')
            ax.set_xlim(0 - (dist_terr[-1]*0.02), dist_terr[-1] * 1.02) # Leve margem nas bordas
            
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
