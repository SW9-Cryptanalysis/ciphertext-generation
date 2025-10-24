import logging
from text_fetching.fetcher import Fetcher
from encipherment.cipher import HomophonicCipher, MonoalphabeticCipher
from utils.files import save_cipher
from utils.constants import (
	MIN_PLAINTEXT_LENGTH,
	MAX_PLAINTEXT_LENGTH,
	NUM_CIPHERS,
)
from tqdm import tqdm

logging.basicConfig(
	level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
)


def generate_cipher(
	min_len: int, max_len: int, filename: str, difficulty: int | None = None,
) -> None:
	"""Generate a cipher from a random book slice and save it to a JSON file.

	Args:
		min_len (int): The minimum length of the text slice.
		max_len (int): The maximum length of the text slice.
		filename (str): The name of the file to save the cipher.
		difficulty (int | None): The difficulty level for the cipher (4-30). If None,
			a random difficulty will be chosen.

	"""
	fetcher = Fetcher(True)
	book_text = fetcher.fetch_random_book_text()
	sliced_text = fetcher.get_random_book_slice(book_text, min_len, max_len)
	try:
		cipher = HomophonicCipher(sliced_text, difficulty=difficulty)
		cipher.generate_difficulty()
		cipher.generate_key()
		cipher.encipher()
	except ValueError as e:
		logging.error(f"Error generating cipher for book id: {fetcher.book_id}")
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
	try:
		cipher = MonoalphabeticCipher(sliced_text)
	except ValueError as e:
		logging.error(
			f"Error generating monoalphabetic cipher for book id: {fetcher.book_id}",
		)
		raise e

	save_cipher(cipher_data=cipher, filename=filename)


if __name__ == "__main__":  # pragma: no cover
	for i in tqdm(range(4, 30), desc="Generating ciphers"):
		generate_cipher(
			MIN_PLAINTEXT_LENGTH,
			MAX_PLAINTEXT_LENGTH,
			f"cipher-{i}.json",
		)
	pass
