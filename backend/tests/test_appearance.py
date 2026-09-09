"""Account appearance preference — stored on the user document."""
from server import APPEARANCE_VALUES, _normalize_appearance


def test_normalize_appearance_defaults_to_light():
    assert _normalize_appearance(None) == "light"
    assert _normalize_appearance("") == "light"
    assert _normalize_appearance("nope") == "light"


def test_normalize_appearance_accepts_valid():
    for value in APPEARANCE_VALUES:
        assert _normalize_appearance(value) == value
        assert _normalize_appearance(value.upper()) == value
