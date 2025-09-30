import pytest
from decimal import Decimal

import encipherment.homophones


@pytest.fixture
def homophone_dict():
    # Return a dictionary of letters to homophone counts that is near expected frequencies, startng with e, t, a...
    return {
        "e": 7,
        "t": 9,
        "a": 6,
        "o": 5,
        "i": 3,
        "n": 3,
        "s": 6,
        "r": 3,
        "h": 2,
        "d": 5,
        "l": 2,
        "u": 1,
        "c": 1,
        "m": 4,
        "f": 2,
        "y": 1,
        "w": 3,
        "g": 1,
        "p": 1,
        "b": 1,
        "v": 1,
        "k": 1,
        "x": 1,
        "q": 1,
        "j": 2,
        "z": 1,
    }
    
@pytest.fixture
def sample_frequencies():
    return {
		"e": Decimal("12.03"),
		"t": Decimal("9.10"),
		"a": Decimal("8.12"),
		"o": Decimal("7.68"),
		"i": Decimal("7.31"),
		"n": Decimal("6.95"),
		"s": Decimal("6.28"),
		"r": Decimal("6.02"),
		"h": Decimal("5.92"),
		"d": Decimal("4.32"),
		"l": Decimal("3.98"),
		"u": Decimal("2.88"),
		"c": Decimal("2.71"),
		"m": Decimal("2.61"),
		"f": Decimal("2.30"),
		"y": Decimal("2.11"),
		"w": Decimal("2.09"),
		"g": Decimal("2.03"),
		"p": Decimal("1.82"),
		"b": Decimal("1.49"),
		"v": Decimal("1.11"),
		"k": Decimal("0.69"),
		"x": Decimal("0.17"),
		"q": Decimal("0"),
		"j": Decimal("0.10"),
		"z": Decimal("0"),
	}


def test_extract_homophones(sample_frequencies):
    cipher_symbols = [100, 55, 26, 250]  # Must be at least 26 to cover all letters
    for cipher_symbol in cipher_symbols:
        homophones_dict = encipherment.homophones.extract_homophones(cipher_symbol, sample_frequencies)
        total_homophones = sum(homophones_dict.values())
        assert all(
            (count >= 1 if sample_frequencies[letter] > 0 else count == 0)
            for letter, count in homophones_dict.items()
        )
        assert total_homophones <= cipher_symbol + 10  # Allow a small margin due to noise


def test_extract_homophones_small_numbers(sample_frequencies):
    invalid_cipher_symbols = [25, 4, 2, 1, 0]  # Must be at least 26 to cover all letters
    for cipher_symbol in invalid_cipher_symbols:
        encipherment.homophones.extract_homophones(cipher_symbol, sample_frequencies)
        assert True  # Just ensure no exception is raised