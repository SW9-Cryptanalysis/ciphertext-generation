import requests
import random

GUTENDEX_BASE_URL = "https://gutendex.com/books"

class Fetcher:
	def __init__(self):
		self.books_metadata = []

	def fetch_random_book_text(self):

		url = GUTENDEX_BASE_URL
		all_metadata = []

		book_ids = [
			"84", # Frankenstein
			"2701", # Moby Dick
			"1513", # Romeo and Juliet
			"1342", # Pride and Prejudice
			"11", # Alice's Adventures in Wonderland
			"1232", # The Prince
			"98", # A Tale of Two Cities
			"74", # The Adventures of Tom Sawyer
			"1400", # Great Expectations
			"16328", # Beowulf
			"55", # The Wonderful Wizard of Oz
			"345", # Dracula
			"46", # The Jungle Book
			"23", # The Scarlet Letter
			"135", # The Count of Monte Cristo
			"174", # The Picture of Dorian Gray
			"1080", # A Modest Proposal
			"768", # Wuthering Heights
		]

		random_id = random.choice(book_ids)
		print(f"Fetching metadata for book ID: {random_id}")
		try:
			r = requests.get(f"{url}/{random_id}")
			r.raise_for_status()
			book_metadata = r.json()
			self.books_metadata = [book_metadata]  # Store as a single-item list
			print(f"Fetched metadata for book ID {random_id}: {book_metadata.get('title', 'Unknown')}")
			
			# Now fetch the actual text
			formats = book_metadata.get('formats', {})
			print(f"Available formats: {list(formats.keys())}")
			
			text_url = None
			# Try different text format keys based on what we see in the API response
			for fmt in ['text/plain; charset=utf-8', 'text/plain; charset=us-ascii', 'text/plain']:
				if fmt in formats:
					text_url = formats[fmt]
					print(f"Using format: {fmt}")
					break
			
			if not text_url:
				print("No suitable text format found for the selected book.")
				print(f"Available formats were: {list(formats.keys())}")
				return None
				
			print(f"Downloading text from: {text_url}")
			text_response = requests.get(text_url)
			text_response.raise_for_status()
			book_text = text_response.text
			
			print(f"Downloaded {len(book_text)} characters")
			return book_text
			
		except requests.RequestException as e:
			print(f"Error fetching book data: {e}")
			return None

	def display_book_metadata(self):
		"""Display the first 100 books' metadata"""
		if not self.books_metadata:
			self.fetch_book_metadata()
		
		print(f"\nDisplaying metadata for first {len(self.books_metadata)} books:")
		print("=" * 80)
		
		for i, book_metadata in enumerate(self.books_metadata, 1):
			title = book_metadata.get('title', 'Unknown')
			authors = [author.get('name', 'Unknown') for author in book_metadata.get('authors', [])]
			download_count = book_metadata.get('download_count', 0)
			languages = book_metadata.get('languages', [])
			book_id = book_metadata.get('id', 'Unknown')
			
			print(f"{i:3d}. {title}")
			print(f"     Authors: {', '.join(authors) if authors else 'Unknown'}")
			print(f"     Downloads: {download_count:,}")
			print(f"     Languages: {', '.join(languages)}")
			print(f"     ID: {book_id}")
			print()
	
	def get_random_book_slice(self, book_text, min_len=100, max_len=5000):
		"""Extract a random slice from the provided book text."""
		if not book_text:
			print("No book text provided.")
			return None
			
		if len(book_text) < min_len:
			print(f"Book text is shorter than minimum length requirement ({min_len}).")
			return None
			
		# Get random slice
		start_idx = random.randint(0, max(0, len(book_text) - min_len))
		end_idx = min(len(book_text), start_idx + random.randint(min_len, max_len))
		slice_text = book_text[start_idx:end_idx]
		
		print(f"Extracted slice from position {start_idx} to {end_idx} ({len(slice_text)} characters)")
		
		return slice_text
		
	def format_text(self, text):
		return [c.upper() for c in text if c.isalpha()]
		

# Example usage
if __name__ == "__main__":
	fetcher = Fetcher()

	# Fetch random book text
	print("Fetching random book text from Gutendx...")
	book_text = fetcher.fetch_random_book_text()
	
	if not book_text:
		print("Failed to fetch book text")
		exit(1)
	
	print("\n" + "="*50)
	print("Getting a random book slice...")
	
	text_slice = fetcher.get_random_book_slice(book_text)
	
	if text_slice:
		print(f"\n--- Random slice ---")
		print(text_slice)
		print("--- End of slice ---")
	else:
		print("Failed to get book slice")
		exit(1)

	formatted = fetcher.format_text(text_slice)
	print(f"Formatted text length (alphabetic chars only): {len(formatted)}")
	print(f"First 100 characters of formatted text: {''.join(formatted[:100])}")