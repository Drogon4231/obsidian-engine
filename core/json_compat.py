"""Lenient JSON parsing — patches json.loads/json.load to allow control characters."""
import json

_original_json_loads = json.loads
_original_json_load = json.load
_patched = False

def _lenient_json_loads(s, *args, **kwargs):
    kwargs.setdefault("strict", False)
    return _original_json_loads(s, *args, **kwargs)

def _lenient_json_load(fp, *args, **kwargs):
    kwargs.setdefault("strict", False)
    return _original_json_load(fp, *args, **kwargs)

def apply_lenient_json():
    global _patched
    if _patched:
        return
    json.loads = _lenient_json_loads
    json.load = _lenient_json_load
    _patched = True
