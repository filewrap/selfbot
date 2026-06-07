import importlib
import pathlib
import pkgutil

__all__ = ["modules"]
current = pathlib.Path(__file__).parent.resolve()
modules = [
    importlib.import_module(f".{module.name}", __name__)
    for module in pkgutil.iter_modules([str(current)])
]
if globals().get("reload", False):
    for module in modules:
        importlib.reload(module)
else:
    reload = True
    
