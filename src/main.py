from tqdm import tqdm
def generate_cipher(length: int | None, filename: str) -> None:
	"""Generate a cipher from a random book slice and save it to a JSON file.
	Args:
		length (int | None): The length of the text slice to fetch. If None, a random length between 500 and 5000 will be used.
		filename (str): The name of the file to save the cipher.
	"""
	from text_fetching.fetcher import Fetcher
	from encipherment.cipher import Cipher
	from utils.files import save_cipher
 
	fetcher = Fetcher()
	book_text = fetcher.fetch_random_book_text()
	sliced_text = fetcher.get_random_book_slice(book_text, min_len=length if length else 500, max_len=length if length else 5000)
	formatted_text = fetcher.format_text(sliced_text)

	cipher = Cipher(formatted_text)

	save_cipher(cipher_data=cipher, filename=filename)


if __name__ == "__main__": # pragma: no cover
	for i in tqdm(range(10000)):
		generate_cipher(5000, f"cipher-{i}.json")
