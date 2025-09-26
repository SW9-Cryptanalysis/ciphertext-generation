def generate_cipher():
	from text_fetching.fetcher import Fetcher
	from encipherment.cipher import Cipher
	import json
	# import timing library to measure execution time
	import time
 
	fetcher = Fetcher()
	start_time = time.time()
	book_text = fetcher.fetch_random_book_text()
	book_fetch_time = time.time() - start_time
	print(f"Fetched book text in {book_fetch_time:.2f} seconds.")
	sliced_text = fetcher.get_random_book_slice(book_text, 700, 700)
	if not isinstance(sliced_text, str):
		print("Failed to fetch a valid book slice.")
		return
	formatted_text = fetcher.format_text(sliced_text)
	format_time = time.time() - start_time - book_fetch_time
	print(f"Formatted text in {format_time:.2f} seconds.")

	cipher = Cipher(formatted_text)
	print("Generated cipher text of length:", len(cipher.plaintext))
	cipher_time = time.time() - start_time - book_fetch_time - format_time
	print(f"Generated cipher in {cipher_time:.2f} seconds.")
	print(f"Total execution time: {time.time() - start_time:.2f} seconds.")

	# Save to json file in ciphers folder
	with open("ciphers/cipher-1.json", "w") as f:
		json.dump(cipher.__json__(), f, indent=2)


if __name__ == "__main__":
	generate_cipher()
