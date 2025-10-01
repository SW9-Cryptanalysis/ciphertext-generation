from encipherment.cipher import Cipher

def save_book(book_id: str, book_text: str) -> None:
	"""Save the fetched book text to a local file for caching.

	Args:
		book_id (str): The ID of the book.
		book_text (str): The entire contents of a book in string format.
	"""
	if not book_text:
		raise ValueError("book_text must be a non-empty string")

	import os
	if not os.path.exists("books"):
		os.makedirs("books")
	with open(f"books/{book_id}.txt", "w") as f:
		f.write(book_text)

def book_is_cached(book_id: str) -> bool:
	"""Check if a book with the given ID exists in the local cache.

	Args:
		book_id (str): The ID of the book.

	Returns:
		bool: True if the book file exists, False otherwise.
	"""
	import os
	return os.path.exists(f"books/{book_id}.txt")

def get_cached_book(book_id: str) -> str:
	"""Retrieve the cached book text from a local file.

	Args:
		book_id (str): The ID of the book.
	Returns:
		str: The entire contents of the cached book in string format.
	Raises:
		FileNotFoundError: If the book file does not exist.
	"""
	import os
	if not os.path.exists(f"books/{book_id}.txt"):
		raise FileNotFoundError(f"Book with ID {book_id} is not cached.")
	with open(f"books/{book_id}.txt", "r") as f:
		return f.read()
   
   
def save_cipher(cipher_data: Cipher, filename: str) -> None:
	"""Save the cipher data to a JSON file.

	Args:
		cipher_data (dict): The cipher data to save.
		filename (str): The name of the file to save the cipher.
	"""
	import json
	import os
	if not os.path.exists("ciphers"):
		os.makedirs("ciphers")
	with open(f"ciphers/{filename}", "w") as f:
		json.dump(cipher_data.__json__(), f, indent=2)