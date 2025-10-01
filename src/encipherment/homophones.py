from decimal import Decimal


def extract_homophones(cipher_symbols, frequencies):
	"""Extract a dictionary mapping each letter to its number of homophones based on letter frequencies in English text.

	Args:
		cipher_symbols (int): The total number of cipher symbols to distribute among letters. Must be at least 26.

	Returns:
		(dict[str, int]): A dictionary mapping each letter to its number of homophones.
	"""

	ideal_homophones: list[Decimal] = [
		cipher_symbols * (freq / 100) for freq in frequencies.values()
	]
 
	# Ensure at least one homophone per letter which has a non-zero frequency
	ideal_homophones = [max(Decimal("1"), count) if count > 0 else Decimal("0") for count in ideal_homophones]

	homophones_dict: dict[str, int] = dict(
		zip(frequencies.keys(), map(round, ideal_homophones))
	)

	return homophones_dict
