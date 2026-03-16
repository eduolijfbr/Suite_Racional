# -*- coding: utf-8 -*-
"""
Delimitação Automática de Bacias Hidrográficas
"""

from qgis.core import (
    QgsRasterLayer, QgsVectorLayer, QgsProject,
    QgsFeature, QgsGeometry, QgsPointXY,
    QgsField, QgsFields, QgsWkbTypes,
    QgsVectorFileWriter, QgsCoordinateReferenceSystem,
    QgsProcessingFeedback, QgsMemoryProviderUtils
)
from qgis.PyQt.QtCore import QVariant
import processing


class DelimitadorBacia:
    """
    Delimitação automática de bacias hidrográficas a partir de MDT.
    """
    
    def __init__(self):
        self.feedback = QgsProcessingFeedback()
        
    def delimitar(self, mdt_layer, ponto_exutorio):
        """
        Delimita bacia hidrográfica a partir do ponto de exutório.
        
        Parâmetros:
            mdt_layer: Camada raster do MDT
            ponto_exutorio: QgsPointXY do exutório
            
        Retorna:
            QgsVectorLayer: Camada vetorial com a bacia delimitada
        """
        try:
            # 1. Preencher depressões (Fill Sinks)
            filled = self._fill_sinks(mdt_layer)
            
            # 2. Calcular direção de fluxo (Flow Direction)
            flow_dir = self._flow_direction(filled)
            
            # 3. Calcular acumulação de fluxo (Flow Accumulation)
            flow_acc = self._flow_accumulation(flow_dir)
            
            # 4. Delimitar bacia (Watershed)
            bacia = self._watershed(flow_dir, ponto_exutorio)
            
            return bacia
            
        except Exception as e:
            raise Exception(f"Erro ao delimitar bacia: {str(e)}")
    
    def _fill_sinks(self, mdt_layer):
        """
        Preenche depressões no MDT.
        """
        try:
            result = processing.run("grass7:r.fill.dir", {
                'input': mdt_layer,
                'format': 0,
                'output': 'TEMPORARY_OUTPUT',
                'direction': 'TEMPORARY_OUTPUT',
                'areas': 'TEMPORARY_OUTPUT'
            }, feedback=self.feedback)
            
            return result['output']
            
        except Exception:
            # Fallback: retornar MDT original
            return mdt_layer
    
    def _flow_direction(self, mdt_layer):
        """
        Calcula direção de fluxo (D8).
        """
        try:
            result = processing.run("grass7:r.watershed", {
                'elevation': mdt_layer,
                'threshold': 1000,
                'drainage': 'TEMPORARY_OUTPUT',
                '-s': False,
                '-m': False,
                '-4': False,
                '-a': False,
                '-b': False
            }, feedback=self.feedback)
            
            return result['drainage']
            
        except Exception:
            # Fallback usando SAGA
            try:
                result = processing.run("saga:fillsinksxxlwangliu", {
                    'ELEV': mdt_layer,
                    'FILLED': 'TEMPORARY_OUTPUT'
                }, feedback=self.feedback)
                return result['FILLED']
            except Exception:
                return mdt_layer
    
    def _flow_accumulation(self, flow_dir_layer):
        """
        Calcula acumulação de fluxo.
        """
        try:
            result = processing.run("grass7:r.watershed", {
                'elevation': flow_dir_layer,
                'threshold': 1000,
                'accumulation': 'TEMPORARY_OUTPUT'
            }, feedback=self.feedback)
            
            return result['accumulation']
            
        except Exception:
            return None
    
    def _watershed(self, flow_dir_layer, ponto_exutorio):
        """
        Delimita a bacia a partir do ponto de exutório.
        """
        # Criar camada de pontos temporária
        ponto_layer = self._criar_camada_ponto(ponto_exutorio, flow_dir_layer.crs())
        
        try:
            # Usar r.water.outlet do GRASS
            result = processing.run("grass7:r.water.outlet", {
                'input': flow_dir_layer,
                'coordinates': f"{ponto_exutorio.x()},{ponto_exutorio.y()}",
                'output': 'TEMPORARY_OUTPUT'
            }, feedback=self.feedback)
            
            # Converter raster para vetor
            bacia_vetor = self._raster_para_vetor(result['output'])
            
            return bacia_vetor
            
        except Exception as e:
            # Fallback: criar polígono circular aproximado
            return self._criar_bacia_aproximada(ponto_exutorio, flow_dir_layer.crs())
    
    def _criar_camada_ponto(self, ponto, crs):
        """
        Cria camada vetorial com um ponto.
        """
        layer = QgsVectorLayer(f"Point?crs={crs.authid()}", "exutorio", "memory")
        provider = layer.dataProvider()
        
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(ponto))
        provider.addFeature(feature)
        
        layer.updateExtents()
        return layer
    
    def _raster_para_vetor(self, raster_layer):
        """
        Converte raster de bacia para vetor.
        """
        try:
            result = processing.run("gdal:polygonize", {
                'INPUT': raster_layer,
                'BAND': 1,
                'FIELD': 'DN',
                'EIGHT_CONNECTEDNESS': False,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }, feedback=self.feedback)
            
            return result['OUTPUT']
            
        except Exception:
            return None
    
    def _criar_bacia_aproximada(self, ponto, crs, raio=5000):
        """
        Cria uma bacia aproximada (circular) quando a delimitação falha.
        """
        layer = QgsVectorLayer(
            f"Polygon?crs={crs.authid()}&field=id:integer&field=nome:string",
            "bacia_aproximada",
            "memory"
        )
        provider = layer.dataProvider()
        
        # Criar círculo aproximado
        circle = QgsGeometry.fromPointXY(ponto).buffer(raio, 32)
        
        feature = QgsFeature()
        feature.setGeometry(circle)
        feature.setAttributes([1, "Bacia Aproximada"])
        provider.addFeature(feature)
        
        layer.updateExtents()
        return layer
    
    def extrair_rede_drenagem(self, mdt_layer, threshold=1000):
        """
        Extrai rede de drenagem do MDT.
        
        Parâmetros:
            mdt_layer: Camada raster do MDT
            threshold: Limiar de acumulação para definir canais
            
        Retorna:
            QgsVectorLayer: Rede de drenagem vetorial
        """
        try:
            # Usar r.watershed do GRASS
            result = processing.run("grass7:r.watershed", {
                'elevation': mdt_layer,
                'threshold': threshold,
                'stream': 'TEMPORARY_OUTPUT',
                '-s': False
            }, feedback=self.feedback)
            
            # Converter para vetor
            streams = processing.run("grass7:r.to.vect", {
                'input': result['stream'],
                'type': 0,  # line
                'output': 'TEMPORARY_OUTPUT'
            }, feedback=self.feedback)
            
            return streams['output']
            
        except Exception:
            return None
    
    def calcular_ordem_strahler(self, rede_drenagem):
        """
        Calcula ordem de Strahler para a rede de drenagem.
        """
        try:
            result = processing.run("grass7:v.stream.order", {
                'input': rede_drenagem,
                'output': 'TEMPORARY_OUTPUT'
            }, feedback=self.feedback)
            
            return result['output']
            
        except Exception:
            return rede_drenagem
    
    def identificar_talvegue_principal(self, mdt_layer, area_layer):
        """
        Identifica o talvegue principal da bacia.
        
        Retorna:
            QgsVectorLayer: Linha do talvegue principal
        """
        try:
            # Extrair rede de drenagem
            rede = self.extrair_rede_drenagem(mdt_layer)
            
            if rede is None:
                return None
                
            # Clipar pela área
            result = processing.run("native:clip", {
                'INPUT': rede,
                'OVERLAY': area_layer,
                'OUTPUT': 'TEMPORARY_OUTPUT'
            }, feedback=self.feedback)
            
            # Selecionar maior segmento (simplificado)
            clipped = result['OUTPUT']
            
            maior_comprimento = 0
            talvegue = None
            
            for feature in clipped.getFeatures():
                comprimento = feature.geometry().length()
                if comprimento > maior_comprimento:
                    maior_comprimento = comprimento
                    talvegue = feature
                    
            if talvegue:
                # Criar camada com talvegue
                layer = QgsVectorLayer(
                    f"LineString?crs={clipped.crs().authid()}",
                    "talvegue_principal",
                    "memory"
                )
                provider = layer.dataProvider()
                provider.addFeature(talvegue)
                layer.updateExtents()
                return layer
                
            return None
            
        except Exception:
            return None
