import sys
sys.path.insert(0, "src")
from parser.parse import parse_de_number

def test_parses_standard_german_number():
    assert parse_de_number("101.000,00 EUR") == 101000.0

def test_parses_number_without_currency():
    assert parse_de_number("55,26 m²") == 55.26

def test_handles_none():
    assert parse_de_number(None) is None

def test_handles_empty_string():
    assert parse_de_number("") is None

def test_handles_nan_from_pandas():
    import math
    assert parse_de_number(float("nan")) is None