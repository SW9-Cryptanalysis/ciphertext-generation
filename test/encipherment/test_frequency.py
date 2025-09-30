import pytest
from decimal import Decimal

from encipherment.frequency import frequencies

def test_frequencies_all_letters():
	text = "abcdefghijklmnopqrstuvwxyz"
	freq = frequencies(text)
	expected_freq = {char: Decimal("100") / Decimal("26") for char in "abcdefghijklmnopqrstuvwxyz"}
	assert freq == expected_freq


def test_frequencies_some_letters():
	text = "aaabbc"
	freq = frequencies(text)
	expected_freq = {
		"a": Decimal("50"),
		"b": Decimal("33.33333333333333333333333333"),
		"c": Decimal("16.66666666666666666666666667"),
	}
	for char in "defghijklmnopqrstuvwxyz":
		expected_freq[char] = Decimal("0")
	assert freq == expected_freq
 
def test_frequencies_no_letters():
	text = "12345!@#$%"
	freq = frequencies(text)
	expected_freq = {char: Decimal("0") for char in "abcdefghijklmnopqrstuvwxyz"}
	assert freq == expected_freq