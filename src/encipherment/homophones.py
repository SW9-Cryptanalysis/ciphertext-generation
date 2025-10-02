from decimal import Decimal
import random


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

def get_homophones(homophones: list[int], letter_occurrences: int) -> list[int]:
	"""Get a list of homophones for a letter generated from the list of available homophones.
	It ensures that all homophones are used at least once if letter_occurrences is greater than the number of available homophones.
	Args:
		homophones (list[int]): A list of available homophones.
		letter_occurrences (int): The number of homophones to select for the letter.

	Returns:
		list[int]: A list of selected homophones.
	"""
	if letter_occurrences < len(homophones):
		return random.sample(homophones, letter_occurrences) # Impossible to use all homophones, so just sample

	selected_homophones = homophones.copy()
 
	for _ in range(letter_occurrences - len(homophones)):
		selected_homophones.append(random.choice(homophones))

	random.shuffle(selected_homophones)
	return selected_homophones