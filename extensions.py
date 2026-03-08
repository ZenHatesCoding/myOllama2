from models import AppState

_state = None


def init_state():
    global _state
    _state = AppState()
    return _state


def get_state():
    global _state
    if _state is None:
        _state = AppState()
    return _state


state = get_state()
