from text_fetching.fetcher import Fetcher
from encipherment.cipher import HomophonicCipher, MonoalphabeticCipher
from utils.files import save_cipher
from utils.formatting import clean_spaces
from utils.logging import get_logger
from tqdm import tqdm
from utils.constants import DIFFICULTIES, LENGTHS
from utils.z408 import (
	plaintext_str as z408_plaintext,
	plaintext_str_with_boundaries as z408_plaintext_with_boundaries,
	cipher_str as z408_cipher,
	key_formatted as z408_key,
)
from fetching.text_splits import TextStream

logger = get_logger("Main")


def generate_cipher(
	min_len: int,
	max_len: int,
	filename: str,
	difficulty: int | None = None,
) -> None:
	"""Generate a cipher from a random book slice and save it to a JSON file.

	Args:
		min_len (int): The minimum length of the text slice.
		max_len (int): The maximum length of the text slice.
		filename (str): The name of the file to save the cipher.
		difficulty (int | None): The difficulty level for the cipher (4-30). If None,
			a random difficulty will be chosen.

	"""
	fetcher = Fetcher()
	book_text = fetcher.fetch_random_book_text()
	sliced_text = fetcher.get_random_book_slice(book_text, min_len, max_len)
	cleaned_text = clean_spaces(sliced_text)

	try:
		text_obj: TextStream = {
			"text": cleaned_text,
			"text_with_boundaries": sliced_text,
			"source_id": fetcher.book_id,
			"source_name": "Test",
			"length": len(cleaned_text),
		}
		cipher = HomophonicCipher(text_obj, difficulty=difficulty)
		cipher.generate_difficulty()
		cipher.generate_key()
		cipher.encipher()
	except ValueError as e:
		logger.error(f"Error generating cipher for book id: {fetcher.book_id}")
		raise e

	save_cipher(cipher_data=cipher, filename=filename)


def generate_monoalphabetic_cipher(min_len: int, max_len: int, filename: str) -> None:
	"""Generate a monoalphabetic cipher from a random book slice and save to JSON file.

	Args:
		min_len (int): The minimum length of the text slice.
		max_len (int): The maximum length of the text slice.
		filename (str): The name of the file to save the cipher.

	"""
	fetcher = Fetcher()
	book_text = fetcher.fetch_random_book_text()
	sliced_text = fetcher.get_random_book_slice(book_text, min_len, max_len)
	cleaned_text = clean_spaces(sliced_text)
	text_obj: TextStream = {
		"text": cleaned_text,
		"text_with_boundaries": sliced_text,
		"source_id": fetcher.book_id,
		"source_name": "Test",
		"length": len(cleaned_text),
	}
	try:
		cipher = MonoalphabeticCipher(text_obj)
	except ValueError as e:
		logger.error(
			f"Error generating monoalphabetic cipher for book id: {fetcher.book_id}",
		)
		raise e

	save_cipher(cipher_data=cipher, filename=filename)


if __name__ == "__main__":  # pragma: no cover
	# Homophonic Ciphers
	with tqdm(total=len(DIFFICULTIES) * len(LENGTHS) + 2) as pbar:
		for difficulty in DIFFICULTIES:
			for length in LENGTHS:
				generate_cipher(
					length,
					length,
					f"c_{length}_{difficulty}.json",
					difficulty,
				)
				pbar.update(1)

		# Z408 Cipher
		z408_text_obj: TextStream = {
			"text": z408_plaintext,
			"text_with_boundaries": z408_plaintext_with_boundaries,
			"source_id": "z408",
			"source_name": "Test",
			"length": len(z408_plaintext),
		}
		z408 = HomophonicCipher(z408_text_obj, difficulty=7)
		z408.key = z408_key
		z408.ciphertext = z408_cipher
		z408.num_symbols = 54

		save_cipher(cipher_data=z408, filename="z408.json")
		pbar.update(1)

		# Monoalphabetic Cipher
		generate_monoalphabetic_cipher(4000, 4000, "c_mono_4000.json")
		pbar.update(1)
