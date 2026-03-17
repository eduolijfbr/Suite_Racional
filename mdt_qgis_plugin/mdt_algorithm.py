"""
MDT Algorithm - Core processing logic using ONLY GDAL (no scipy/numpy).
Uses gdal.Grid() for Delaunay triangulation-based linear interpolation.
"""
import os
import math
import random
import tempfile
import traceback
from osgeo import gdal, ogr, osr


class MDTAlgorithm:
    """
    Generates MDT/MDS using GDAL Grid with linear interpolation.
    Zero external dependencies beyond GDAL (always available in QGIS).
    """

    def __init__(self):
        self.log_messages = []

    def log(self, msg):
        self.log_messages.append(str(msg))

    def snap_to_grid(self, value, resolution, mode="floor"):
        if mode == "floor":
            return math.floor(value / resolution) * resolution
        elif mode == "ceil":
            return math.ceil(value / resolution) * resolution
        return value

    def process(self, points_xyz, extent, resolution, output_path, crs_wkt, progress_fn=None):
        """
        Main processing function.

        Args:
            points_xyz: list of (x, y, z) tuples (pure Python)
            extent: tuple (xmin, ymin, xmax, ymax)
            resolution: float (pixel size in meters)
            output_path: str (path to output GeoTIFF)
            crs_wkt: str (WKT of the coordinate reference system)
            progress_fn: callable(int_percent, str_message) or None
        Returns:
            True on success
        Raises:
            Exception with detailed message on failure
        """
        tmp_shp = None
        tmp_files = []
        mem_ds = None
        mem_layer = None

        try:
            # ---- Step 1: Validate input ----
            if progress_fn:
                progress_fn(5, "Validando dados de entrada...")

            total_pts = len(points_xyz)
            if total_pts < 3:
                raise Exception(
                    f"Apenas {total_pts} pontos encontrados. "
                    "São necessários pelo menos 3 pontos para triangulação."
                )

            # Filtering duplicates and adding jitter (crucial for Delaunay stability)
            # Jitter of 5mm prevents perfectly collinear points from causing triangulation failure
            unique_points = {}
            for x, y, z in points_xyz:
                # Add tiny random jitter (1e-3 meters = 1mm to 1cm range)
                # Using 0.005 range = 5mm
                xj = x + (random.random() - 0.5) * 0.010
                yj = y + (random.random() - 0.5) * 0.010
                
                # Higher precision key to avoid merging jittered points
                key = (round(xj, 5), round(yj, 5))
                if key not in unique_points:
                    unique_points[key] = z
            
            if len(unique_points) < 3:
                raise Exception("Pontos insuficientes após remover duplicados.")
            
            if len(unique_points) < total_pts:
                self.log(f"Removidos {total_pts - len(unique_points)} pontos duplicados.")
                total_pts = len(unique_points)

            # Check Z variation
            z_min = min(unique_points.values())
            z_max = max(unique_points.values())

            if z_min == z_max:
                raise Exception(
                    f"Todos os valores Z são iguais ({z_min:.2f}). "
                    "Verifique se o campo de cota está correto."
                )

            self.log(f"Pontos Únicos: {total_pts}, Z: [{z_min:.2f}, {z_max:.2f}]")

            # ---- Step 2: Create In-Memory Point Layer (Faster than file) ----
            if progress_fn:
                progress_fn(10, f"Criando nuvem de pontos em memória...")

            # Use OGR Memory driver
            mem_driver = ogr.GetDriverByName("Memory")
            mem_ds = mem_driver.CreateDataSource("mem_points")
            
            srs = osr.SpatialReference()
            srs.ImportFromWkt(crs_wkt)
            # Ensure proper axis mapping for GDAL 3+
            if hasattr(srs, 'SetAxisMappingStrategy'):
                srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)

            mem_layer = mem_ds.CreateLayer("points", srs, ogr.wkbPoint25D)
            mem_layer.CreateField(ogr.FieldDefn("Z", ogr.OFTReal))

            feat_defn = mem_layer.GetLayerDefn()
            for idx, ((x, y), z) in enumerate(unique_points.items()):
                feat = ogr.Feature(feat_defn)
                pt = ogr.Geometry(ogr.wkbPoint25D)
                pt.AddPoint(x, y, z)
                feat.SetGeometry(pt)
                feat.SetField("Z", z)
                mem_layer.CreateFeature(feat)
                
                if progress_fn and idx % 10000 == 0:
                    pct = int(10 + (idx / total_pts) * 20)
                    progress_fn(pct, f"Carregando pontos... {idx}/{total_pts}")

            # ---- Step 3: Setup grid parameters (Snap to Grid) ----
            if progress_fn:
                progress_fn(35, "Configurando grid...")

            xmin, ymin, xmax, ymax = extent

            xmin_snap = self.snap_to_grid(xmin, resolution, "floor")
            ymax_snap = self.snap_to_grid(ymax, resolution, "ceil")
            xmax_snap = self.snap_to_grid(xmax, resolution, "ceil")
            ymin_snap = self.snap_to_grid(ymin, resolution, "floor")

            width = int(round((xmax_snap - xmin_snap) / resolution))
            height = int(round((ymax_snap - ymin_snap) / resolution))

            if width <= 0 or height <= 0:
                raise Exception(f"Extensão inválida: {width}x{height}.")

            # Limitation: GDAL Grid can be memory intensive for huge rasters
            pix_count = width * height
            if pix_count > 100_000_000: # ~10k x 10k
                raise Exception(f"Resolução muito alta para esta área ({width}x{height}). Tente aumentar o valor em 'Resolução'.")

            self.log(f"Grid: {width}x{height} pixels, Resolução: {resolution}m")

            # ---- Step 4: Run GDAL Grid ----
            if progress_fn:
                progress_fn(40, "Interpolando TIN (GDAL Grid)... Aguarde.")

            # Linear algorithm = Delaunay Triangulation
            grid_options = gdal.GridOptions(
                format="GTiff",
                outputType=gdal.GDT_Float32,
                algorithm="linear:radius=-1:nodata=-9999",
                zfield="Z",
                width=width,
                height=height,
                outputBounds=[xmin_snap, ymin_snap, xmax_snap, ymax_snap],
                outputSRS=srs.ExportToWkt(),
                creationOptions=["COMPRESS=DEFLATE", "TILED=YES"]
            )

            # Close existing if open
            if os.path.exists(output_path):
                try: os.remove(output_path)
                except: pass

            result_ds = gdal.Grid(
                output_path,
                mem_ds,
                options=grid_options
            )
            
            # --- Fallback to IDW (Inverse Distance Weighting) if Linear fails ---
            if result_ds is None:
                self.log("Triangulação Delaunay falhou. Tentando fallback para IDW (invdist)...")
                grid_options_fallback = gdal.GridOptions(
                    format="GTiff",
                    outputType=gdal.GDT_Float32,
                    algorithm="invdist:power=2.0:smoothing=0.0:radius1=0.0:radius2=0.0:angle=0.0:max_points=0:min_points=0:nodata=-9999",
                    zfield="Z",
                    width=width,
                    height=height,
                    outputBounds=[xmin_snap, ymin_snap, xmax_snap, ymax_snap],
                    outputSRS=srs.ExportToWkt(),
                    creationOptions=["COMPRESS=DEFLATE", "TILED=YES"]
                )
                
                result_ds = gdal.Grid(
                    output_path,
                    mem_ds,
                    options=grid_options_fallback
                )

            if result_ds is None:
                gdal_err = gdal.GetLastErrorMsg()
                # A very distinct message so we know it's THIS version of the code
                raise Exception(f"ERRO_GERACAO_MDT_FINAL (Linear+IDW): {gdal_err or 'Erro desconhecido GDAL'}")

            # Finalize metadata
            band = result_ds.GetRasterBand(1)
            band.SetNoDataValue(-9999.0)
            result_ds.FlushCache()
            result_ds = None 

            if progress_fn:
                progress_fn(100, "MDT gerado com sucesso!")

            return True

        except Exception as e:
            self.log(f"ERRO: {str(e)}")
            self.log(traceback.format_exc())
            raise

        finally:
            # Cleanup
            mem_ds = None
            mem_layer = None
            try:
                if tmp_shp and os.path.exists(tmp_shp):
                    shp_driver = ogr.GetDriverByName("ESRI Shapefile")
                    if shp_driver:
                        shp_driver.DeleteDataSource(tmp_shp)
                for d in tmp_files:
                    if os.path.isdir(d):
                        import shutil
                        shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
