from decimal import Decimal
from utils.constants import ALPHABET


def frequencies(text: str) -> dict[str, Decimal]:
	"""Calculate the frequency of each letter in the given text. 0 if not present.

	Args:
		text (str): The input text to analyze.

	Returns:
		dict[str, Decimal]: A dictionary mapping each letter to its frequency.

	"""
	letter_counts: dict[str, int] = {char: 0 for char in ALPHABET}
	for char in text:
		if char.isalpha():
			letter_counts[char] = letter_counts.get(char, 0) + 1

	total_letters = sum(letter_counts.values())

	if total_letters == 0:
		return {char: Decimal("0") for char in ALPHABET}

	return {
		char: Decimal(count) / Decimal(total_letters) * 100
		for char, count in letter_counts.items()
	}
