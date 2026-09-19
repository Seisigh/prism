"""server/features/signal_descriptions.py must stay a perfect match for
the real signal registry -- a stale or missing description is worse than
none, per that module's own docstring."""
from server.features.signal_descriptions import SIGNAL_DESCRIPTIONS
from server.features.signals import SIGNAL_REGISTRY
from server.features.signals_directional import DIRECTIONAL_SIGNAL_REGISTRY
from server.features.signals_gate1 import GATE1_SIGNAL_REGISTRY

ALL_SIGNALS = {**SIGNAL_REGISTRY, **GATE1_SIGNAL_REGISTRY, **DIRECTIONAL_SIGNAL_REGISTRY}


def test_every_registered_signal_has_a_description():
    missing = set(ALL_SIGNALS) - set(SIGNAL_DESCRIPTIONS)
    assert not missing, f"signals with no description: {missing}"


def test_no_description_for_a_signal_that_does_not_exist():
    stray = set(SIGNAL_DESCRIPTIONS) - set(ALL_SIGNALS)
    assert not stray, f"descriptions for signals no longer in the registry: {stray}"


def test_every_description_has_all_four_fields_non_empty():
    for name, desc in SIGNAL_DESCRIPTIONS.items():
        for field in ("measures", "higher", "lower", "unavailable_when"):
            value = getattr(desc, field)
            assert isinstance(value, str) and value.strip(), f"{name}.{field} is empty"
