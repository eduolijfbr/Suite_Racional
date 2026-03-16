1. Fundamentação Matemática do MVPPara que os cálculos reflitam o terreno real, precisamos aplicar trigonometria sobre os valores extraídos dos pixels do raster.Distância 3D (Perfil Longitudinal):O usuário clica no mapa, formando uma linha 2D. O script deve amostrar os valores de $Z$ do raster ao longo dessa linha em intervalos regulares (ex: a cada 1 metro ou a cada tamanho de pixel). A distância real é a soma das hipotenusas entre os pontos amostrados.$$D_{3D} = \sum_{i=1}^{n-1} \sqrt{(X_{i+1} - X_i)^2 + (Y_{i+1} - Y_i)^2 + (Z_{i+1} - Z_i)^2}$$Área de Superfície 3D:A área plana 2D de um polígono não reflete a área real de um terreno acidentado. Para calcular a área 3D, iteramos sobre os pixels do raster que caem dentro do polígono desenhado pelo usuário e dividimos a área de cada pixel pelo cosseno da declividade daquele pixel.$$Area_{3D} = \sum \frac{Area_{pixel}}{\cos(Declividade)}$$Volume (Corte/Aterro ou Capacidade de Retenção):O usuário desenha um polígono e define uma "Cota Base" ($Z_{base}$). O volume é a diferença entre a cota do terreno ($Z_{pixel}$) e a cota base, multiplicada pela área plana do pixel.$$Volume = \sum Area_{pixel} \times (Z_{pixel} - Z_{base})$$2. Arquitetura da FerramentaO MVP será composto por duas partes principais:Interface Gráfica (UI): Um painel acoplável (DockWidget) com um QComboBox para selecionar a camada de elevação, botões de ação (Medir Distância, Medir Área, Calcular Volume) e um campo para input da cota de referência (para volumes).Motor Geométrico (PyQGIS): Uma classe QgsMapToolEmitPoint personalizada para capturar os cliques no canevas do mapa e interagir com as APIs de raster do QGIS (QgsRasterDataProvider).3. Código PyQGIS: O Motor de Cálculo (MVP)Este script contém o núcleo lógico do plugin. Você pode testá-lo diretamente no Console Python do QGIS para validar a extração de dados antes de encapsular no PyQt5. Ele assume que você tem um MDT carregado e ativo no mapa.Pythonimport math
from qgis.core import (
    QgsProject, 
    QgsGeometry, 
    QgsPointXY, 
    QgsRasterGeometryUtils,
    QgsMessageLog,
    Qgis
)
from qgis.gui import QgsMapToolEmitPoint
from PyQt5.QtCore import Qt

class FerramentaMedicao3D(QgsMapToolEmitPoint):
    def __init__(self, canvas, raster_layer):
        super().__init__(canvas)
        self.canvas = canvas
        self.raster_layer = raster_layer
        self.points = []
        self.setCursor(Qt.CrossCursor)

    def canvasReleaseEvent(self, event):
        # Captura o clique no mapa e converte para coordenadas do projeto
        point = self.toMapCoordinates(event.pos())
        self.points.append(point)
        
        # Extrai o valor Z do Raster no ponto clicado
        ident = self.raster_layer.dataProvider().identify(point, QgsRaster.IdentifyFormatValue)
        if ident.isValid():
            z_value = list(ident.results().values())[0]
            QgsMessageLog.logMessage(f"Ponto adicionado: X={point.x():.2f}, Y={point.y():.2f}, Z={z_value:.2f}", "Medicao 3D", Qgis.Info)
        
        # Se houver 2 pontos, calcula a distância 3D
        if len(self.points) == 2:
            self.calcular_distancia_3d()
            self.points = [] # Reseta para a próxima medição

    def calcular_distancia_3d(self):
        pt1, pt2 = self.points[0], self.points[1]
        
        # Amostragem da linha para maior precisão (10 segmentos de interpolação)
        segmentos = 10
        dist_2d_total = math.sqrt((pt2.x() - pt1.x())**2 + (pt2.y() - pt1.y())**2)
        passo_x = (pt2.x() - pt1.x()) / segmentos
        passo_y = (pt2.y() - pt1.y()) / segmentos
        
        distancia_3d = 0.0
        ponto_anterior = None
        z_anterior = None

        provider = self.raster_layer.dataProvider()

        for i in range(segmentos + 1):
            x = pt1.x() + (passo_x * i)
            y = pt1.y() + (passo_y * i)
            ponto_atual = QgsPointXY(x, y)
            
            ident = provider.identify(ponto_atual, QgsRaster.IdentifyFormatValue)
            if ident.isValid():
                z_atual = list(ident.results().values())[0]
            else:
                z_atual = 0.0 # Fallback caso o pixel seja nulo

            if ponto_anterior is not None:
                # Aplica Pitágoras no espaço 3D
                dx = ponto_atual.x() - ponto_anterior.x()
                dy = ponto_atual.y() - ponto_anterior.y()
                dz = z_atual - z_anterior
                
                segmento_3d = math.sqrt(dx**2 + dy**2 + dz**2)
                distancia_3d += segmento_3d

            ponto_anterior = ponto_atual
            z_anterior = z_atual

        QgsMessageLog.logMessage(f"Distância 2D: {dist_2d_total:.2f}m", "Medicao 3D", Qgis.Success)
        QgsMessageLog.logMessage(f"Distância 3D: {distancia_3d:.2f}m", "Medicao 3D", Qgis.Success)

# --- Como inicializar no Console do QGIS ---
# layer = iface.activeLayer() # Certifique-se de selecionar uma camada Raster (MDT/MDS)
# tool = FerramentaMedicao3D(iface.mapCanvas(), layer)
# iface.mapCanvas().setMapTool(tool)
4. Lógica para Integração de Volumes (Próxima Fase)Para a rotina de área e volume (especialmente útil para bacias de detenção em drenagem), a abordagem nativa mais eficiente em PyQGIS é utilizar a biblioteca QgsZonalStatistics.Você pode criar uma geometria de polígono em memória a partir dos cliques do usuário e rodar uma estatística zonal sobre a camada de elevação para obter a Soma (Sum), a Contagem de Pixels (Count) e o tamanho do pixel.Área Plana da Bacia = Count $\times$ (Tamanho do Pixel X $\times$ Tamanho do Pixel Y).Volume de Acúmulo = Integrar a diferença entre um Z máximo (cota de extravasamento) e os pixels subjacentes extraídos pela estatística zonal.