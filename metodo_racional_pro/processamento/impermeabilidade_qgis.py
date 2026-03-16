# -*- coding: utf-8 -*-
"""
Cálculo de impermeabilidade usando API nativa do QGIS
Suporta todos os tipos de camadas raster: GeoTIFF, XYZ Tiles, WMS, etc.
Não requer rasterio ou scikit-image
"""

import numpy as np
import os
from datetime import datetime

from qgis.core import (
    QgsProject, QgsRasterLayer, QgsVectorLayer, QgsGeometry,
    QgsCoordinateTransform, QgsCoordinateReferenceSystem,
    QgsRectangle, QgsPointXY, QgsMessageLog, Qgis,
    QgsMapSettings, QgsMapRendererCustomPainterJob
)
from qgis.PyQt.QtGui import QImage, QPainter, QColor
from qgis.PyQt.QtCore import Qt, QSize


def renderizar_camada_para_imagem(layer_raster, extent, width, height):
    """
    Renderiza uma camada raster para um array RGB numpy.
    Funciona com qualquer tipo de camada: GeoTIFF, XYZ Tiles, WMS, etc.
    
    Args:
        layer_raster: QgsRasterLayer
        extent: QgsRectangle com a área a renderizar
        width: largura em pixels
        height: altura em pixels
        
    Returns:
        tuple: (r_array, g_array, b_array) como arrays numpy
    """
    # Configurar mapa para renderização
    settings = QgsMapSettings()
    settings.setLayers([layer_raster])
    settings.setExtent(extent)
    settings.setOutputSize(QSize(width, height))
    settings.setBackgroundColor(Qt.white)
    settings.setDestinationCrs(layer_raster.crs())
    
    # Criar imagem de saída
    image = QImage(width, height, QImage.Format_RGB888)
    image.fill(Qt.white)
    
    # Renderizar
    painter = QPainter(image)
    job = QgsMapRendererCustomPainterJob(settings, painter)
    job.start()
    job.waitForFinished()
    painter.end()
    
    # Converter QImage para arrays numpy
    r_array = np.zeros((height, width), dtype=np.float32)
    g_array = np.zeros((height, width), dtype=np.float32)
    b_array = np.zeros((height, width), dtype=np.float32)
    
    for row in range(height):
        for col in range(width):
            color = image.pixelColor(col, row)
            r_array[row, col] = color.red()
            g_array[row, col] = color.green()
            b_array[row, col] = color.blue()
    
    return r_array, g_array, b_array


def calcular_impermeabilidade_qgis(layer_raster, geometria, source_crs=None):
    """
    Calcula impermeabilidade usando API nativa do QGIS.
    Suporta todos os tipos de raster: imagens locais, XYZ Tiles, WMS, etc.
    
    Args:
        layer_raster: QgsRasterLayer (qualquer tipo)
        geometria: QgsGeometry do polígono da área de estudo
        source_crs: CRS da geometria (para reprojeção se necessário)
        
    Returns:
        dict com resultados ou None se falhar
    """
    if not layer_raster or not layer_raster.isValid():
        raise ValueError("Camada raster inválida")
        
    if not geometria or geometria.isEmpty():
        raise ValueError("Geometria inválida ou vazia")
    
    # Reprojetar geometria para o CRS do raster
    raster_crs = layer_raster.crs()
    geometria_proc = QgsGeometry(geometria)
    
    if source_crs and source_crs != raster_crs:
        transform = QgsCoordinateTransform(source_crs, raster_crs, QgsProject.instance())
        geometria_proc.transform(transform)
        QgsMessageLog.logMessage(
            f"Geometria reprojetada de {source_crs.authid()} para {raster_crs.authid()}",
            'MetodoRacionalPro', Qgis.Info
        )
    
    # Obter extent da geometria
    geom_extent = geometria_proc.boundingBox()
    raster_extent = layer_raster.extent()
    
    # Verificar interseção
    if not geom_extent.intersects(raster_extent):
        QgsMessageLog.logMessage(
            "Área de estudo não intersecta a imagem raster",
            'MetodoRacionalPro', Qgis.Warning
        )
        return None
    
    # Usar a interseção dos extents
    clip_extent = geom_extent.intersect(raster_extent)
    
    # Calcular dimensões apropriadas para renderização
    # Usar resolução aproximada baseada no extent
    aspect_ratio = clip_extent.width() / max(clip_extent.height(), 0.001)
    
    # Tamanho base de renderização (limitar para performance)
    max_pixels = 1000
    if aspect_ratio > 1:
        width = min(max_pixels, int(clip_extent.width() / 0.5))  # ~0.5m por pixel
        width = max(100, min(width, max_pixels))
        height = int(width / aspect_ratio)
    else:
        height = min(max_pixels, int(clip_extent.height() / 0.5))
        height = max(100, min(height, max_pixels))
        width = int(height * aspect_ratio)
    
    width = max(50, width)
    height = max(50, height)
    
    QgsMessageLog.logMessage(
        f"Renderizando área {clip_extent.width():.1f}x{clip_extent.height():.1f}m em {width}x{height} pixels",
        'MetodoRacionalPro', Qgis.Info
    )
    
    # Renderizar a camada para obter RGB
    try:
        r_array, g_array, b_array = renderizar_camada_para_imagem(
            layer_raster, clip_extent, width, height
        )
    except Exception as e:
        raise RuntimeError(f"Erro ao renderizar camada: {str(e)}")
    
    # Criar máscara de pixels dentro da geometria
    valid_mask = np.zeros((height, width), dtype=bool)
    
    for row in range(height):
        for col in range(width):
            # Calcular coordenada do centro do pixel
            x = clip_extent.xMinimum() + (col + 0.5) * (clip_extent.width() / width)
            y = clip_extent.yMaximum() - (row + 0.5) * (clip_extent.height() / height)
            
            point = QgsPointXY(x, y)
            if geometria_proc.contains(point):
                valid_mask[row, col] = True
    
    # Verificar se há pixels válidos
    total_valid = np.count_nonzero(valid_mask)
    if total_valid == 0:
        QgsMessageLog.logMessage(
            "Nenhum pixel dentro da área de estudo",
            'MetodoRacionalPro', Qgis.Warning
        )
        return None
    
    # Ignorar pixels brancos puros (fundo/sem dados)
    white_mask = (r_array > 250) & (g_array > 250) & (b_array > 250)
    black_mask = (r_array < 5) & (g_array < 5) & (b_array < 5)
    valid_mask = valid_mask & ~white_mask & ~black_mask
    
    total_pixels = np.count_nonzero(valid_mask)
    if total_pixels == 0:
        QgsMessageLog.logMessage(
            "Nenhum pixel válido (apenas fundo branco/preto)",
            'MetodoRacionalPro', Qgis.Warning
        )
        return None
    
    # === CLASSIFICAÇÃO TERNÁRIA ===
    
    # 1. Calcular ExG (Excess Green Index)
    exg = 2.0 * g_array - r_array - b_array
    
    # 2. Calcular Intensidade
    intensidade = (r_array + g_array + b_array) / 3.0
    
    # 3. Calcular Saturação (fórmula HSV simplificada)
    max_rgb = np.maximum(np.maximum(r_array, g_array), b_array)
    min_rgb = np.minimum(np.minimum(r_array, g_array), b_array)
    
    with np.errstate(divide='ignore', invalid='ignore'):
        saturacao = np.where(max_rgb > 0, (max_rgb - min_rgb) / max_rgb, 0)
    
    # 4. Classificação
    # Vegetação: ExG > 0 E Saturação > 0.12
    is_vegetation = (exg > 0) & (saturacao > 0.12) & valid_mask
    
    # Sombra/Água: Intensidade < 50 E ExG < 0
    is_shadow = (intensidade < 50) & (exg < 0) & valid_mask & ~is_vegetation
    
    # Impermeável: Todo o resto
    is_impermeable = valid_mask & ~is_vegetation & ~is_shadow
    
    # Criar mapa de classificação
    classification_map = np.zeros((height, width), dtype=np.uint8)
    classification_map[is_vegetation] = 1
    classification_map[is_shadow] = 2
    # 0 = Impermeável (default)
    
    # === CONTAGEM E ESTATÍSTICAS ===
    
    impermeable_pixels = np.count_nonzero(is_impermeable)
    vegetation_pixels = np.count_nonzero(is_vegetation)
    shadow_pixels = np.count_nonzero(is_shadow)
    
    # Calcular percentuais
    coef_impermeavel = impermeable_pixels / total_pixels
    percent_impermeavel = coef_impermeavel * 100
    percent_vegetation = (vegetation_pixels / total_pixels) * 100
    percent_shadow = (shadow_pixels / total_pixels) * 100
    
    # Criar array RGB para visualização (formato C, H, W)
    rgb_image = np.stack([r_array, g_array, b_array], axis=0).astype(np.uint8)
    
    # Preparar resultados
    resultados = {
        'coeficiente': coef_impermeavel,
        'percentual': percent_impermeavel,
        'total_pixels': total_pixels,
        'impermeable_pixels': impermeable_pixels,
        'vegetation_pixels': vegetation_pixels,
        'shadow_pixels': shadow_pixels,
        'percent_vegetation': percent_vegetation,
        'percent_shadow': percent_shadow,
        'rgb_image': rgb_image,
        'classification_map': classification_map,
        'valid_mask': valid_mask,
        'exg': exg,
        'saturacao': saturacao,
        'intensidade': intensidade
    }
    
    QgsMessageLog.logMessage(
        f"Impermeabilidade calculada: {percent_impermeavel:.2f}% "
        f"(Veg: {percent_vegetation:.2f}%, Sombra: {percent_shadow:.2f}%)",
        'MetodoRacionalPro', Qgis.Info
    )
    
    return resultados


def salvar_imagem_original(rgb, valid_mask, output_dir):
    """
    Salva a imagem RGB original.
    
    Args:
        rgb: Array numpy (C, H, W) com as bandas RGB
        valid_mask: Máscara booleana dos pixels válidos
        output_dir: Diretório de saída
        
    Returns:
        str: Caminho do arquivo salvo ou None
    """
    try:
        from qgis.PyQt.QtGui import QImage, QColor
        from qgis.PyQt.QtCore import Qt
        
        # rgb tem formato (C, H, W), precisamos (H, W, C)
        h, w = rgb.shape[1], rgb.shape[2]
        
        # Criar imagem RGB original
        img = QImage(w, h, QImage.Format_RGB888)
        img.fill(Qt.white)
        
        for row in range(h):
            for col in range(w):
                if valid_mask[row, col]:
                    r = int(rgb[0, row, col])
                    g = int(rgb[1, row, col])
                    b = int(rgb[2, row, col])
                    img.setPixelColor(col, row, QColor(r, g, b))
        
        # Salvar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(output_dir, f"impermeabilidade_original_{timestamp}.png")
        img.save(img_path)
        
        return img_path
        
    except Exception as e:
        QgsMessageLog.logMessage(f"Erro ao salvar imagem original: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)
        return None


def salvar_imagem_classificacao_simples(rgb, classification_map, valid_mask, output_dir):
    """
    Salva imagem de classificação simples usando apenas bibliotecas padrão.
    
    Returns:
        str: Caminho do arquivo salvo ou None
    """
    try:
        from qgis.PyQt.QtGui import QImage, QColor
        from qgis.PyQt.QtCore import Qt
        
        h, w = classification_map.shape
        
        # Criar imagem de classificação
        img = QImage(w, h, QImage.Format_RGB888)
        img.fill(Qt.white)
        
        for row in range(h):
            for col in range(w):
                if valid_mask[row, col]:
                    cls = classification_map[row, col]
                    if cls == 0:  # Impermeável
                        color = QColor(80, 80, 80)
                    elif cls == 1:  # Vegetação
                        color = QColor(34, 139, 34)
                    else:  # Sombra
                        color = QColor(30, 144, 255)
                    img.setPixelColor(col, row, color)
        
        # Salvar
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(output_dir, f"impermeabilidade_classificacao_{timestamp}.png")
        img.save(img_path)
        
        return img_path
        
    except Exception as e:
        QgsMessageLog.logMessage(f"Erro ao salvar imagem: {str(e)}", 'MetodoRacionalPro', Qgis.Warning)
        return None


def salvar_relatorio_txt_simples(resultados, output_dir):
    """
    Salva relatório TXT com estatísticas.
    
    Returns:
        str: Caminho do arquivo salvo
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    txt_path = os.path.join(output_dir, f"impermeabilidade_relatorio_{timestamp_file}.txt")
    
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("RELATÓRIO DE IMPERMEABILIDADE DO SOLO\n")
        f.write("Método Racional Pro - Classificação Ternária de Pixels\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Data/Hora: {timestamp}\n\n")
        
        f.write("-" * 60 + "\n")
        f.write("RESULTADOS PRINCIPAIS\n")
        f.write("-" * 60 + "\n")
        f.write(f"Coeficiente de Impermeabilidade (C): {resultados['coeficiente']:.4f}\n")
        f.write(f"Percentual Impermeável:              {resultados['percentual']:.2f}%\n\n")
        
        f.write("-" * 60 + "\n")
        f.write("ESTATÍSTICAS DETALHADAS\n")
        f.write("-" * 60 + "\n")
        f.write(f"Total de Pixels Analisados:    {resultados['total_pixels']:,}\n")
        f.write(f"Pixels Impermeáveis:           {resultados['impermeable_pixels']:,} ({resultados['percentual']:.2f}%)\n")
        f.write(f"Pixels de Vegetação:           {resultados['vegetation_pixels']:,} ({resultados['percent_vegetation']:.2f}%)\n")
        f.write(f"Pixels de Sombra/Água:         {resultados['shadow_pixels']:,} ({resultados['percent_shadow']:.2f}%)\n\n")
        
        f.write("=" * 60 + "\n")
        f.write("Fim do Relatório\n")
        f.write("=" * 60 + "\n")
    
    return txt_path
