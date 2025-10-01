def generate_cipher(length: int | None, difficulty: int | None, filename: str) -> None:
	"""Generate a cipher from a random book slice and save it to a JSON file.
	Args:
		length (int | None): The length of the text slice to fetch. If None, a random length between 500 and 5000 will be used.
		difficulty (int | None): The difficulty of the cipher, i.e., higher difficulty = more homophones.
		filename (str): The name of the file to save the cipher.
	"""
	from text_fetching.fetcher import Fetcher
	from encipherment.cipher import Cipher
	import json
	import os
	# import timing library to measure execution time
	import time
 
	fetcher = Fetcher()
	start_time = time.time()
	book_text = fetcher.fetch_random_book_text()
	book_fetch_time = time.time() - start_time
	print(f"Fetched book text in {book_fetch_time:.2f} seconds.")
	sliced_text = fetcher.get_random_book_slice(book_text, min_len=length if length else 500, max_len=length if length else 5000)
	formatted_text = fetcher.format_text(sliced_text)

	cipher = Cipher(formatted_text, difficulty)

	# Save to json file in ciphers folder
	# Create directory if it doesn't exist
	os.makedirs(os.path.dirname(filename), exist_ok=True)
	with open(filename, "w") as f:
		json.dump(cipher.__json__(), f, indent=2)


if __name__ == "__main__": # pragma: no cover
	import sys
	import random
	for i in range(0,1000):
		length = random.randint(4000, 10000)
		generate_cipher(length, None, f"ciphers/cipher-{i}.json")
