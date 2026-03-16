# -*- coding: utf-8 -*-
"""
Método Racional Pro - Plugin QGIS para Cálculo de Drenagem
"""


def classFactory(iface):
    """Carrega a classe do plugin."""
    from .plugin_main import MetodoRacionalPro
    return MetodoRacionalPro(iface)
