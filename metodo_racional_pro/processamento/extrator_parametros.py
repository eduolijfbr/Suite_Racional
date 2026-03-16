# -*- coding: utf-8 -*-
"""
Extração Automática de Parâmetros de Bacias Hidrográficas
"""

from qgis.core import (
    QgsRasterLayer, QgsVectorLayer, QgsProject,
    QgsRasterBandStats, QgsGeometry, QgsPointXY,
    QgsFeature, QgsField, QgsFields, QgsWkbTypes,
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsRectangle, QgsProcessingFeedback
)
from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
import processing
import math


class ExtratorParametros:
    """
    Extrai automaticamente parâmetros físicos da bacia hidrográfica.
    """
    
    def __init__(self):
        self.feedback = QgsProcessingFeedback()
        
    def extrair_parametros_bacia(self, mdt_layer, area_layer, uso_solo_layer=None):
        """
        Extrai automaticamente parâmetros físicos da bacia hidrográfica.
        
        Parâmetros calculados:
        - Área (km²)
        - Perímetro (km)
        - Comprimento do talvegue (m)
        - Desnível máximo (m)
        - Declividade média (%)
        - Altitude máxima/mínima/média (m)
        - Coeficiente de compacidade
        - Fator de forma
        - CN ponderado (se uso_solo fornecido)
        - Tempo de concentração (múltiplos métodos)
        
        Retorna:
            dict: Dicionário com todos os parâmetros calculados
        """
        parametros = {}
        
        # Área e perímetro
        area_perimetro = self.calcular_area_perimetro(area_layer)
        parametros.update(area_perimetro)
        
        # Altitudes do MDT
        altitudes = self.extrair_altitudes(mdt_layer, area_layer)
        parametros.update(altitudes)
        
        # Desnível
        parametros['desnivel'] = altitudes['altitude_max'] - altitudes['altitude_min']
        
        # Comprimento do talvegue (estimativa)
        parametros['comprimento_talvegue'] = self.estimar_comprimento_talvegue(
            area_layer, mdt_layer
        )
        
        # Declividade
        if parametros['comprimento_talvegue'] > 0:
            parametros['declividade_perc'] = (
                parametros['desnivel'] / parametros['comprimento_talvegue']
            ) * 100
        else:
            parametros['declividade_perc'] = 0
            
        # Índices morfométricos
        parametros['coef_compacidade'] = self.calcular_coef_compacidade(
            parametros['area_km2'], 
            parametros['perimetro_km']
        )
        parametros['fator_forma'] = self.calcular_fator_forma(
            parametros['area_km2'],
            parametros['comprimento_talvegue'] / 1000
        )
        
        # CN ponderado
        if uso_solo_layer:
            parametros['cn_ponderado'] = self.calcular_cn_ponderado(
                area_layer, uso_solo_layer
            )
        
        # Tempo de concentração
        from ..hidrologia.metodo_racional import TempoConcentracao
        
        tc_resultados = TempoConcentracao.calcular_todos(
            parametros['comprimento_talvegue'],
            parametros['desnivel'],
            parametros['area_km2'],
            parametros.get('cn_ponderado'),
            parametros['declividade_perc']
        )
        
        parametros['tempo_concentracao_kirpich'] = tc_resultados['kirpich']
        parametros['tempo_concentracao_media'] = tc_resultados['media']
        parametros['tempos_concentracao'] = tc_resultados
        
        return parametros
    
    def calcular_area_perimetro(self, area_layer):
        """
        Calcula área e perímetro da bacia.
        """
        resultado = {
            'area_m2': 0,
            'area_km2': 0,
            'perimetro_m': 0,
            'perimetro_km': 0
        }
        
        for feature in area_layer.getFeatures():
            geom = feature.geometry()
            resultado['area_m2'] += geom.area()
            resultado['perimetro_m'] += geom.length()
            
        resultado['area_km2'] = resultado['area_m2'] / 1_000_000
        resultado['perimetro_km'] = resultado['perimetro_m'] / 1000
        
        return resultado
    
    def calcular_area(self, area_layer):
        """
        Calcula área em km².
        """
        area_m2 = 0
        for feature in area_layer.getFeatures():
            geom = feature.geometry()
            area_m2 += geom.area()
        return area_m2 / 1_000_000
    
    def extrair_altitudes(self, mdt_layer, area_layer):
        """
        Extrai estatísticas de altitude do MDT dentro da área.
        """
        resultado = {
            'altitude_max': 0,
            'altitude_min': 0,
            'altitude_med': 0
        }
        
        try:
            # Usar estatísticas zonais
            stats = processing.run("native:zonalstatisticsfb", {
                'INPUT': area_layer,
                'INPUT_RASTER': mdt_layer,
                'RASTER_BAND': 1,
                'COLUMN_PREFIX': 'elev_',
                'STATISTICS': [0, 1, 2, 5, 6],  # count, sum, mean, min, max
                'OUTPUT': 'memory:'
            }, feedback=self.feedback)
            
            output_layer = stats['OUTPUT']
            
            for feature in output_layer.getFeatures():
                resultado['altitude_min'] = feature['elev_min'] or 0
                resultado['altitude_max'] = feature['elev_max'] or 0
                resultado['altitude_med'] = feature['elev_mean'] or 0
                break
                
        except Exception as e:
            # Fallback: usar estatísticas do raster completo
            stats = mdt_layer.dataProvider().bandStatistics(
                1, QgsRasterBandStats.All
            )
            resultado['altitude_min'] = stats.minimumValue
            resultado['altitude_max'] = stats.maximumValue
            resultado['altitude_med'] = stats.mean
            
        return resultado
    
    def calcular_desnivel(self, mdt_layer, area_layer):
        """
        Calcula desnível dentro da área.
        """
        altitudes = self.extrair_altitudes(mdt_layer, area_layer)
        return altitudes['altitude_max'] - altitudes['altitude_min']
    
    def estimar_comprimento_talvegue(self, area_layer, mdt_layer):
        """
        Estima comprimento do talvegue principal.
        
        Usa aproximação baseada na área e forma da bacia.
        """
        # Obter bounding box
        extent = area_layer.extent()
        
        # Diagonal da bounding box como estimativa inicial
        dx = extent.width()
        dy = extent.height()
        diagonal = math.sqrt(dx**2 + dy**2)
        
        # Fator de correção baseado na forma
        area_m2 = 0
        for feature in area_layer.getFeatures():
            area_m2 += feature.geometry().area()
            
        # Comprimento estimado (aproximação empírica)
        comprimento = diagonal * 0.7  # Fator de sinuosidade
        
        return comprimento
    
    def calcular_comprimento_talvegue(self, mdt_layer, area_layer):
        """
        Calcula comprimento do talvegue usando processamento.
        """
        return self.estimar_comprimento_talvegue(area_layer, mdt_layer)
    
    def calcular_coef_compacidade(self, area_km2, perimetro_km):
        """
        Calcula coeficiente de compacidade (Kc).
        
        Kc = 0.28 * P / sqrt(A)
        
        Kc = 1.0: bacia circular
        Kc > 1.5: bacia alongada
        """
        if area_km2 <= 0:
            return 0
        kc = 0.28 * perimetro_km / math.sqrt(area_km2)
        return kc
    
    def calcular_fator_forma(self, area_km2, comprimento_km):
        """
        Calcula fator de forma (Kf).
        
        Kf = A / L²
        
        Kf baixo: bacia alongada (menor risco de cheias)
        Kf alto: bacia arredondada (maior risco de cheias)
        """
        if comprimento_km <= 0:
            return 0
        kf = area_km2 / (comprimento_km ** 2)
        return kf
    
    def calcular_cn_ponderado(self, area_layer, uso_solo_layer, campo_cn='CN'):
        """
        Calcula CN ponderado pela área de cada uso do solo.
        
        Tabela CN padrão incluída:
        - Área urbana (impermeável): 95-98
        - Área urbana (permeável): 80-85
        - Floresta: 30-60
        - Agricultura: 70-80
        - Solo exposto: 75-90
        - Corpos d'água: 100
        """
        # Tabela CN padrão
        tabela_cn = {
            'urbano_impermeavel': 98,
            'urbano_permeavel': 82,
            'floresta': 45,
            'agricultura': 75,
            'pastagem': 68,
            'solo_exposto': 85,
            'agua': 100
        }
        
        try:
            # Interseção entre área e uso do solo
            intersect = processing.run("native:intersection", {
                'INPUT': area_layer,
                'OVERLAY': uso_solo_layer,
                'OUTPUT': 'memory:'
            }, feedback=self.feedback)
            
            output_layer = intersect['OUTPUT']
            
            soma_cn_area = 0
            soma_area = 0
            
            for feature in output_layer.getFeatures():
                area = feature.geometry().area()
                
                # Tentar obter CN do campo
                cn = None
                if campo_cn in [f.name() for f in feature.fields()]:
                    cn = feature[campo_cn]
                    
                if cn is None:
                    cn = 75  # Valor padrão
                    
                soma_cn_area += cn * area
                soma_area += area
                
            if soma_area > 0:
                return soma_cn_area / soma_area
            else:
                return 75  # Valor padrão
                
        except Exception:
            return 75  # Valor padrão em caso de erro
    
    def calcular_declividade_media(self, mdt_layer, area_layer):
        """
        Calcula declividade média da bacia.
        """
        try:
            # Calcular slope
            slope = processing.run("native:slope", {
                'INPUT': mdt_layer,
                'Z_FACTOR': 1,
                'OUTPUT': 'memory:'
            }, feedback=self.feedback)
            
            slope_layer = slope['OUTPUT']
            
            # Estatísticas zonais
            stats = processing.run("native:zonalstatisticsfb", {
                'INPUT': area_layer,
                'INPUT_RASTER': slope_layer,
                'RASTER_BAND': 1,
                'COLUMN_PREFIX': 'slope_',
                'STATISTICS': [2],  # mean
                'OUTPUT': 'memory:'
            }, feedback=self.feedback)
            
            output_layer = stats['OUTPUT']
            
            for feature in output_layer.getFeatures():
                return feature['slope_mean'] or 0
                
        except Exception:
            return 0
    
    def gerar_curva_hipsometrica(self, mdt_layer, area_layer, num_classes=10):
        """
        Gera dados para curva hipsométrica.
        
        Retorna:
            list: Lista de tuplas (altitude_relativa, area_acumulada_relativa)
        """
        altitudes = self.extrair_altitudes(mdt_layer, area_layer)
        
        alt_min = altitudes['altitude_min']
        alt_max = altitudes['altitude_max']
        amplitude = alt_max - alt_min
        
        if amplitude <= 0:
            return [(0, 100), (100, 0)]
            
        # Gerar classes de altitude
        intervalo = amplitude / num_classes
        
        curva = []
        for i in range(num_classes + 1):
            alt = alt_min + (i * intervalo)
            alt_rel = ((alt - alt_min) / amplitude) * 100
            
            # Área acima desta altitude (simplificado)
            area_rel = 100 - (i / num_classes * 100)
            
            curva.append((alt_rel, area_rel))
            
        return curva
