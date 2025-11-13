import os
import json
from utils.logging import get_colored_logger

logger = get_colored_logger("overlapping_ciphers")


def get_jaccard_similarity(str1: str, str2: str) -> float:
	"""Calculate intersection over union of words.

	0.0 = No shared words.
	1.0 = Identical set of words.

	Args:
		str1 (str): First string to compare.
		str2 (str): Second string to compare.

	Returns:
		float: Jaccard similarity between the two strings.

	"""
	a = set(str1.lower().split())
	b = set(str2.lower().split())

	if not a or not b:
		return 0.0

	intersection = len(a.intersection(b))
	union = len(a.union(b))

	return intersection / union


def get_ciphers() -> list[dict]:
	"""Get all ciphers from the ciphers directory."""
	ciphers = []
	for filename in os.listdir("ciphers"):
		if filename.endswith(".json") and filename.startswith("c_"):
			with open(f"ciphers/{filename}", encoding="utf-8") as f:
				cipher = json.load(f)
				cipher["name"] = filename
				ciphers.append(cipher)

	return ciphers


def check_cipher_overlap() -> dict[str, list[str]]:
	"""Check for overlapping ciphers.

	Returns a dictionary of ciphers with overlapping plaintexts.

	Returns:
		dict[str, list[str]]: A dictionary mapping cipher names to lists of
			overlapping cipher names.

	"""
	result = {}
	for cipher in get_ciphers():
		name = cipher["name"]
		overlapping_ciphers = []
		for other_cipher in get_ciphers():
			if cipher["plaintext"] == other_cipher["plaintext"]:
				continue

			if (
				get_jaccard_similarity(cipher["plaintext"], other_cipher["plaintext"])
				> 0.01
			):
				overlapping_ciphers.append(other_cipher["name"])

		if overlapping_ciphers:
			result[cipher["name"]] = overlapping_ciphers

		logger.info(
			f"Found {len(overlapping_ciphers)} overlapping ciphers for {name}",
		)
	return result


if __name__ == "__main__":
	check_cipher_overlap()  # pragma: no cover
