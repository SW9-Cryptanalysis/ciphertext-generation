import requests
import random
from unidecode import unidecode
from utils.formatting import numbers_to_words

GUTENDEX_BASE_URL = "https://gutendex.com/books"


class Fetcher:
	def fetch_random_book_text(self) -> str:
		"""Fetch metadata for a random book from Gutendex and return its text content.

		Returns:
			str: The full contents of a random book from Project Gutenberg.
		"""

		url = GUTENDEX_BASE_URL

		book_ids = [
			"84",  # Frankenstein
			"2701",  # Moby Dick
			"1513",  # Romeo and Juliet
			"1342",  # Pride and Prejudice
			"11",  # Alice's Adventures in Wonderland
			"1232",  # The Prince
			"98",  # A Tale of Two Cities
			"74",  # The Adventures of Tom Sawyer
			"1400",  # Great Expectations
			"16328",  # Beowulf
			"55",  # The Wonderful Wizard of Oz
			"345",  # Dracula
			"46",  # The Jungle Book
			"23",  # The Scarlet Letter
			"135",  # The Count of Monte Cristo
			"174",  # The Picture of Dorian Gray
			"1080",  # A Modest Proposal
			"768",  # Wuthering Heights
		]

		random_id = random.choice(book_ids)

		try:
			r = requests.get(f"{url}/{random_id}")
			r.raise_for_status()
			book_metadata = r.json()

			# Now fetch the actual text
			formats = book_metadata.get('formats', {})

			text_url = None
			# Try different text format keys based on what we see in the API response
			for fmt in ['text/plain; charset=utf-8', 'text/plain; charset=us-ascii', 'text/plain']:
				if fmt in formats:
					text_url = formats[fmt]
					break

			if not text_url:
				raise RuntimeError(
					f"No suitable text format found for book ID {random_id}. Available formats: {list(formats.keys())}")

			text_response = requests.get(text_url)
			text_response.raise_for_status()
			book_text = text_response.text

			return book_text

		except requests.RequestException as e:
			raise RuntimeError(f"Error fetching book data: {e}") from e

	def get_random_book_slice(self, book_text: str, min_len: int = 100, max_len: int = 5000) -> str:
		"""Extract a random slice from the provided book text.

		:param book_text: The full text of a book.
		:type book_text: str
		:param min_len: The minimum length of the text slice.
		:type min_len: int
		:param max_len: The maximum length of the text slice.
		:type max_len: int

		:return: A random slice of the book text with length between min_len and max_len.
		:rtype: str

		:raises ValueError: If book_text is not a string or is shorter than min_len.
		"""
		if not book_text:
			raise ValueError(
				"book_text must be a string"
			)

		if len(book_text) < min_len:
			raise ValueError(
				"Length of book_text must be equal to or greater than min_len"
			)
		
		book_text = self.format_text(book_text)

		# Get random slice
		start_idx = random.randint(0, max(0, len(book_text) - min_len))
		end_idx = min(len(book_text), start_idx + random.randint(min_len, max_len))
		slice_text = book_text[start_idx:end_idx]

		return slice_text

	def format_text(self, text: str) -> str:
		"""Format text by filtering to alphabetic characters and converting to lowercase.

		Args:
			text (str): A slice of text from a book

		Returns:
			str: The text slice converted to lowercase keeping only alphabetic characters.
		"""
		if not isinstance(text, str):
			raise ValueError(
				"Argument must be a string"
			)
		text = numbers_to_words(text)
		return unidecode("".join([c.lower() for c in text if c.isalpha()]))