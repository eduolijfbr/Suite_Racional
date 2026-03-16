# -*- coding: utf-8 -*-

def classFactory(iface):
    from .suite_main import SuiteRacional
    return SuiteRacional(iface)
