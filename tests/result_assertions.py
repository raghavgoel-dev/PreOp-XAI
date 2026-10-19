"""Typed assertions at aggregate JSON/CSV test boundaries."""

from preop_xai.result_io import Json


def mapping(value: Json) -> dict[str, Json]:
    assert isinstance(value, dict)
    return value


def number(value: Json) -> float:
    assert isinstance(value, (int, float)) and not isinstance(value, bool)
    return float(value)
