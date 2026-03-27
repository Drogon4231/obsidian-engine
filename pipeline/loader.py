"""Dynamic agent loader."""
from importlib.util import spec_from_file_location, module_from_spec
from core.paths import BASE_DIR

def load_agent(filename):
    path = BASE_DIR / "agents" / filename
    if not path.exists():
        raise FileNotFoundError(f"Agent not found: {path}")
    spec = spec_from_file_location(filename.stem, path)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
