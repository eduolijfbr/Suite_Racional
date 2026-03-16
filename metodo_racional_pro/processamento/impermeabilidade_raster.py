# -*- coding: utf-8 -*-
"""
Cálculo de impermeabilidade baseado em imagem raster (RGB)
Utiliza classificação ternária de pixels para determinar áreas impermeáveis
"""

import numpy as np
import tempfile
import json
import os

# Rasterio para manipulação de imagens
try:
    import rasterio
    from rasterio.mask import mask
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

# scikit-image para cálculo de saturação HSV
try:
    from skimage import color
    HAS_SKIMAGE = True
except ImportError:
    HAS_SKIMAGE = False


def calcular_exg(rgb_image):
    """
    Calcula o Excess Green Index (ExG): 2G - R - B.
    
    Args:
        rgb_image: Imagem RGB como (C, H, W). Assume 0=Red, 1=Green, 2=Blue.
    Returns:
        Array ExG (H, W).
    """
    r = rgb_image[0].astype(float)
    g = rgb_image[1].astype(float)
    b = rgb_image[2].astype(float)
    return 2 * g - r - b


def calcular_intensidade(rgb_image):
    """
    Calcula intensidade média: (R + G + B) / 3.
    """
    return rgb_image.mean(axis=0)


def calcular_saturacao(rgb_image):
    """
    Calcula o canal Saturação do espaço HSV.
    Saturação ajuda a distinguir vegetação (maior saturação) de 
    superfícies cinzas como asfalto/concreto (menor saturação).
    
    Returns:
        Array de saturação (H, W) com valores 0-1.
    """
    if not HAS_SKIMAGE:
        # Fallback simples se skimage não disponível
        r = rgb_image[0].astype(float)
        g = rgb_image[1].astype(float)
        b = rgb_image[2].astype(float)
        max_rgb = np.maximum(np.maximum(r, g), b)
        min_rgb = np.minimum(np.minimum(r, g), b)
        # Evitar divisão por zero
        with np.errstate(divide='ignore', invalid='ignore'):
            sat = np.where(max_rgb > 0, (max_rgb - min_rgb) / max_rgb, 0)
        return sat
    
    # Converter para formato (H, W, C)
    rgb_hwc = np.moveaxis(rgb_image, 0, -1)
    
    # Normalizar para 0-1 se necessário
    if rgb_hwc.max() > 1:
        rgb_hwc = rgb_hwc.astype(float) / 255.0
    
    # Converter para HSV e extrair saturação
    hsv = color.rgb2hsv(rgb_hwc)
    return hsv[:, :, 1]


def classificar_ternario(exg, saturacao, intensidade, 
                         exg_veg_threshold=0, 
                         sat_veg_threshold=0.12,
                         intensity_shadow_threshold=50):
    """
    Classificação ternária: Vegetação, Água/Sombra, Impermeável.
    
    Lógica:
    1. VEGETAÇÃO: ExG > 0 E Saturação > 0.12 (pixels verdes com cor)
    2. ÁGUA/SOMBRA: Intensidade < 50 E ExG < 0 (pixels escuros sem verde)
    3. IMPERMEÁVEL: Todo o resto (classe residual)
    
    Returns:
        tuple: (is_impermeable, classification_map)
            - is_impermeable: Máscara booleana de pixels impermeáveis
            - classification_map: Mapa inteiro (0=Impermeável, 1=Vegetação, 2=Sombra/Água)
    """
    classification = np.zeros_like(exg, dtype=np.uint8)
    
    # Regra 1: Vegetação
    is_vegetation = (exg > exg_veg_threshold) & (saturacao > sat_veg_threshold)
    classification[is_vegetation] = 1
    
    # Regra 2: Água/Sombra
    is_shadow_water = (intensidade < intensity_shadow_threshold) & (exg < 0) & ~is_vegetation
    classification[is_shadow_water] = 2
    
    # Regra 3: Impermeável = residual
    is_impermeable = (classification == 0)
    
    return is_impermeable, classification


from qgis.core import (
    QgsProject, QgsGeometry, QgsCoordinateTransform, QgsCoordinateReferenceSystem
)

def calcular_impermeabilidade_raster(raster_path, geometria_qgs, source_crs=None, salvar_resultados=False, output_dir=None):
    """
    Calcula impermeabilidade a partir de imagem raster (RGB) cortada pela área de estudo.
    
    Args:
        raster_path: Caminho para arquivo raster (GeoTIFF, PNG, JPG)
        geometria_qgs: QgsGeometry do polígono da área de estudo
        crs: Sistema de referência de coordenadas (opcional)
        salvar_resultados: Se True, salva imagem e relatório
        output_dir: Diretório para salvar resultados (se None, usa temp)
        
    Returns:
        dict: {
            'coeficiente': float (0.0 a 1.0),
            'percentual': float (0.0 a 100.0),
            'total_pixels': int,
            'impermeable_pixels': int,
            'vegetation_pixels': int,
            'shadow_pixels': int,
            'percent_vegetation': float,
            'percent_shadow': float,
            'rgb_image': array (para visualização),
            'classification_map': array (0=Impermeável, 1=Vegetação, 2=Sombra),
            'valid_mask': array (máscara de pixels válidos),
            'imagem_path': str (caminho da imagem salva, se salvar_resultados=True),
            'relatorio_path': str (caminho do relatório, se salvar_resultados=True)
        }
    """
    if not HAS_RASTERIO:
        raise ImportError("Biblioteca 'rasterio' não está instalada. Execute: pip install rasterio")
    
    if not os.path.exists(raster_path):
        raise FileNotFoundError(f"Arquivo raster não encontrado: {raster_path}")
    
    # Converter QgsGeometry para GeoJSON com reprojeção se necessário
    try:
        with rasterio.open(raster_path) as src:
            raster_crs_wkt = src.crs.to_wkt()
            
            # Se fornecido um CRS de origem, verificar se precisa reprojetar
            geometria_proc = geometria_qgs
            if source_crs is not None:
                raster_qgs_crs = QgsCoordinateReferenceSystem.fromWkt(raster_crs_wkt)
                if source_crs != raster_qgs_crs:
                    transform = QgsCoordinateTransform(source_crs, raster_qgs_crs, QgsProject.instance())
                    geometria_proc = QgsGeometry(geometria_qgs)
                    geometria_proc.transform(transform)
            
            # Converter para GeoJSON
            geojson_dict = json.loads(geometria_proc.asJson())
            geoms = [geojson_dict]

            # Aplicar máscara da geometria
            out_image, out_transform = mask(src, geoms, crop=True)
            
            # Verificar se imagem tem pixels válidos (se o crop funcionou e tem área)
            if out_image.size == 0 or np.all(out_image == 0):
                return None

            # Verificar se imagem tem pelo menos 3 bandas (RGB)
            if out_image.shape[0] < 3:
                raise ValueError("Imagem deve ter pelo menos 3 bandas (RGB)")
            
            # Usar apenas as 3 primeiras bandas (RGB)
            rgb = out_image[:3]
            
            # Calcular índices
            exg = calcular_exg(rgb)
            intensidade = calcular_intensidade(rgb)
            saturacao = calcular_saturacao(rgb)
            
            # Criar máscara de pixels válidos (dentro do polígono e não vazios)
            valid_pixels_mask = np.any(rgb != 0, axis=0)
            
            # Classificação ternária
            impermeable_mask, classification_map = classificar_ternario(
                exg, saturacao, intensidade
            )
            
            # Decisão final: dentro do polígono E classificado como impermeável
            final_impermeable = impermeable_mask & valid_pixels_mask
            
            # Contagem de pixels
            total_pixels = np.count_nonzero(valid_pixels_mask)
            impermeable_pixels = np.count_nonzero(final_impermeable)
            veg_pixels = np.count_nonzero((classification_map == 1) & valid_pixels_mask)
            shadow_pixels = np.count_nonzero((classification_map == 2) & valid_pixels_mask)
            
            if total_pixels == 0:
                return None
            
            # Calcular percentuais
            coef_impermeavel = impermeable_pixels / total_pixels
            percent_impermeavel = coef_impermeavel * 100
            percent_vegetation = (veg_pixels / total_pixels) * 100
            percent_shadow = (shadow_pixels / total_pixels) * 100
            
            # Preparar resultados
            resultados = {
                'coeficiente': coef_impermeavel,
                'percentual': percent_impermeavel,
                'total_pixels': total_pixels,
                'impermeable_pixels': impermeable_pixels,
                'vegetation_pixels': veg_pixels,
                'shadow_pixels': shadow_pixels,
                'percent_vegetation': percent_vegetation,
                'percent_shadow': percent_shadow,
                'rgb_image': rgb,
                'classification_map': classification_map,
                'valid_mask': valid_pixels_mask,
                'exg': exg,
                'saturacao': saturacao,
                'intensidade': intensidade
            }
            
            # Salvar resultados se solicitado
            if salvar_resultados:
                if output_dir is None:
                    output_dir = tempfile.gettempdir()
                
                # Salvar imagem de classificação
                img_path = salvar_imagem_classificacao(
                    rgb, classification_map, valid_pixels_mask, 
                    exg, saturacao, output_dir
                )
                resultados['imagem_path'] = img_path
                
                # Salvar relatório TXT
                txt_path = salvar_relatorio_txt(resultados, output_dir)
                resultados['relatorio_path'] = txt_path
            
            return resultados
            
    except Exception as e:
        raise RuntimeError(f"Erro ao processar raster: {str(e)}")


def salvar_imagem_classificacao(rgb, classification_map, valid_mask, exg, saturacao, output_dir):
    """
    Salva imagem de visualização com 4 painéis: RGB, ExG, Saturação, Classificação.
    
    Returns:
        str: Caminho do arquivo salvo
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Backend sem GUI
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(1, 4, figsize=(16, 4))
        
        # Painel 1: RGB
        rgb_plot = np.moveaxis(rgb, 0, -1)
        if rgb_plot.max() > 1:
            rgb_plot = rgb_plot / 255.0
        axes[0].imshow(rgb_plot)
        axes[0].set_title("Área de Estudo (RGB)")
        axes[0].axis('off')
        
        # Painel 2: ExG
        im1 = axes[1].imshow(exg, cmap='RdYlGn')
        axes[1].set_title("Índice ExG")
        axes[1].axis('off')
        plt.colorbar(im1, ax=axes[1], fraction=0.046)
        
        # Painel 3: Saturação
        im2 = axes[2].imshow(saturacao, cmap='viridis', vmin=0, vmax=1)
        axes[2].set_title("Saturação (HSV)")
        axes[2].axis('off')
        plt.colorbar(im2, ax=axes[2], fraction=0.046)
        
        # Painel 4: Classificação
        display_map = np.zeros_like(classification_map, dtype=np.uint8)
        display_map[valid_mask] = classification_map[valid_mask] + 1
        
        cmap_class = plt.cm.colors.ListedColormap(['#000000', '#808080', '#228B22', '#1E90FF'])
        im3 = axes[3].imshow(display_map, cmap=cmap_class, vmin=0, vmax=3)
        axes[3].set_title("Classificação\n(Cinza=Imper, Verde=Veg, Azul=Sombra)")
        axes[3].axis('off')
        
        plt.tight_layout()
        
        # Salvar
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = os.path.join(output_dir, f"impermeabilidade_classificacao_{timestamp}.png")
        plt.savefig(img_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        return img_path
        
    except ImportError:
        # Se matplotlib não disponível, retornar None
        return None


def salvar_relatorio_txt(resultados, output_dir):
    """
    Salva relatório TXT com estatísticas detalhadas.
    
    Returns:
        str: Caminho do arquivo salvo
    """
    from datetime import datetime
    
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
        
        f.write("-" * 60 + "\n")
        f.write("MÉTODO DE CLASSIFICAÇÃO\n")
        f.write("-" * 60 + "\n")
        f.write("Classificação Ternária baseada em:\n")
        f.write("  • ExG (Excess Green Index): 2G - R - B\n")
        f.write("  • Saturação HSV\n")
        f.write("  • Intensidade RGB\n\n")
        
        f.write("Regras de Classificação:\n")
        f.write("  1. VEGETAÇÃO:   ExG > 0 E Saturação > 0.12\n")
        f.write("  2. SOMBRA/ÁGUA: Intensidade < 50 E ExG < 0\n")
        f.write("  3. IMPERMEÁVEL: Demais pixels (classe residual)\n\n")
        
        f.write("=" * 60 + "\n")
        f.write("Fim do Relatório\n")
        f.write("=" * 60 + "\n")
    
    return txt_path



def verificar_dependencias():
    """
    Verifica se as dependências necessárias estão instaladas.
    
    Returns:
        tuple: (ok, mensagem)
    """
    missing = []
    if not HAS_RASTERIO:
        missing.append("rasterio")
    if not HAS_SKIMAGE:
        missing.append("scikit-image")
    
    if missing:
        return False, f"Bibliotecas faltando: {', '.join(missing)}. Execute: pip install {' '.join(missing)}"
    return True, "Todas as dependências instaladas"
