from fetcher import Fetcher

def main():
	print("Hello from ciphertext-generation!")

	fetcher = Fetcher()
	book_text = fetcher.fetch_random_book_text()
	if book_text:
		print("Fetched book text successfully!")
	else:
		print("Failed to fetch book text.")

if __name__ == "__main__":
	main()
