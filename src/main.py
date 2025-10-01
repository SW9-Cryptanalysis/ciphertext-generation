def generate_cipher(length: int | None, filename: str) -> None:
	"""Generate a cipher from a random book slice and save it to a JSON file.
	Args:
		length (int | None): The length of the text slice to fetch. If None, a random length between 500 and 5000 will be used.
		filename (str): The name of the file to save the cipher.
	"""
	from text_fetching.fetcher import Fetcher
	from encipherment.cipher import Cipher
	import json
	# import timing library to measure execution time
	import time
	from utils.files import save_cipher
 
	fetcher = Fetcher()
	start_time = time.time()
	book_text = fetcher.fetch_random_book_text()
	book_fetch_time = time.time() - start_time
	print(f"Fetched book text in {book_fetch_time:.2f} seconds.")
	sliced_text = fetcher.get_random_book_slice(book_text, min_len=length if length else 500, max_len=length if length else 5000)
	formatted_text = fetcher.format_text(sliced_text)

	cipher = Cipher(formatted_text)

	save_cipher(cipher_data=cipher, filename=filename)


if __name__ == "__main__": # pragma: no cover
	import sys 
	generate_cipher(int(sys.argv[1]) if len(sys.argv) > 1 else None, "cipher-1.json")
