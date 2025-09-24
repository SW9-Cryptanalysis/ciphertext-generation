from text_fetching.fetcher import Fetcher


def main():
    print("Hello from ciphertext-generation!")

    fetcher = Fetcher()
    book_text = fetcher.fetch_random_book_text()
    if book_text:
        print("Fetched book text successfully!")
        print(f"First 500 characters:\n{book_text[:500]}")
        slice_text = fetcher.get_random_book_slice(book_text)
        if slice_text:
            print(f"\nRandom slice ({len(slice_text)} characters):\n{slice_text}")
            formatted = fetcher.format_text(slice_text)
            print(f"\nFormatted text length (alphabetic chars only): {len(formatted)}")
            print(f"First 100 characters of formatted text: {''.join(formatted[:100])}")
    else:
        print("Failed to fetch book text.")


if __name__ == "__main__":
    main()
