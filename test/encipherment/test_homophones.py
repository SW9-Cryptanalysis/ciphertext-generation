import pytest
from decimal import Decimal

import encipherment.homophones


@pytest.fixture
def homphone_dict():
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


def test_extract_homophones():
	cipher_symbols = [100, 55, 26, 250]  # Must be at least 26 to cover all letters
	for cipher_symbol in cipher_symbols:
		homophones_dict = encipherment.homophones.extract_homophones(cipher_symbol)
		total_homophones = sum(homophones_dict.values())
		assert total_homophones == cipher_symbol
		assert all(count >= 1 for count in homophones_dict.values())


def test_extract_homophones_invalid():
	invalid_cipher_symbols = [0, 1, 10, 25]  # Must be at least 26 to cover all letters
	for cipher_symbol in invalid_cipher_symbols:
		with pytest.raises(ValueError) as excinfo:
			encipherment.homophones.extract_homophones(cipher_symbol)
		assert "cipher_symbols must be at least 26 to cover all letters." in str(
			excinfo.value
		)


def test_add_noise():
	ideal_homophones: list[Decimal] = [
		Decimal("5.0"),
		Decimal("3.32"),
		Decimal("1.5"),
		Decimal("0.78"),
		Decimal("0.1"),
	]
	noisy_homophones = encipherment.homophones.add_noise(ideal_homophones, k=2)
	assert len(noisy_homophones) == len(ideal_homophones)
	assert all(isinstance(count, int) for count in noisy_homophones)
	assert all(
		count >= 1 for count in noisy_homophones
	)  # Ensure no count is less than 1

def test_adjust_homophones(homphone_dict):
	total_homophones = [sum(homphone_dict.values()), 150]
	for total in total_homophones:
		adjusted_dict = encipherment.homophones.adjust_homophones(total, homphone_dict.copy())
		adjusted_total = sum(adjusted_dict.values())
		assert adjusted_total == total
		assert all(count >= 1 for count in adjusted_dict.values())
  
def test_adjust_homophones_invalid(homphone_dict):
	invalid_totals = [0, 10, 25]  # Must be at least 26 to cover all letters
	for total in invalid_totals:
		with pytest.raises(ValueError) as excinfo:
			encipherment.homophones.adjust_homophones(total, homphone_dict.copy())
		assert "cipher_symbols must be at least 26 to cover all letters." in str(
			excinfo.value
		)