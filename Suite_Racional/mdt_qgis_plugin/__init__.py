def classFactory(iface):
    from .mdt_plugin import MDTPlugin
    return MDTPlugin(iface)
