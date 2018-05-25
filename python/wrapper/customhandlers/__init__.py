import pkgutil
from importlib import import_module

__path__ = pkgutil.extend_path(__path__, __name__)
for mod_info in pkgutil.iter_modules(path=__path__, prefix=__name__+'.'):
    import_module(mod_info.name)
