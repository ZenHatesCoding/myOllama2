from core.models import AppState
from resources.skills import skill_registry

_state = None


def init_state():
    global _state
    _state = AppState()
    skill_registry.discover_skills()
    return _state


def get_state():
    global _state
    if _state is None:
        _state = AppState()
        skill_registry.discover_skills()
    return _state


state = get_state()
