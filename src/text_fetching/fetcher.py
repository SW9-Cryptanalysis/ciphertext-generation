import requests
import random
from utils.formatting import clean_spaces, format_text
from utils.files import save_book, book_is_cached, get_cached_book
from parameter_validator import parameter_validator, non_negative, non_blank_string
import re

GUTENDEX_BASE_URL = "https://gutendex.com/books"


class Fetcher:
    """A class to fetch and slice random books from Project Gutenberg.

    Fetched via the Gutendex API. It supports caching fetched books locally
    to avoid redundant network requests.

    Attributes:
        BOOK_IDS (list): A predefined list of Project Gutenberg book IDs.
        book_id (str): The ID of the currently selected book.
        is_cached (bool): Indicates if the book is already cached locally.

    Methods:
    -------
        fetch_random_book_text(): Fetches the full text of a random book.
        get_random_book_slice(book_text, min_len, max_len): Extracts a random slice
            from the provided book text.

    """

    BOOK_IDS = [
        "2701",  # Moby Dick
        "2641",  # A Room with a View
        "145",  # Middlemarch
        "37106",  # Little Women; Or, Meg, Jo, Beth, and Amy
        "67979",  # The Blue Castle
        "43",  # The Strange Case of Dr. Jekyll and Mr. Hyde
        "1260",  # Jane Eyre
        "6761",  # The Adventures of Ferdinand Count Fathom
        "345",  # Dracula
        "4085",  # The Adventures of Roderick Random
        "5197",  # My Life - Volume 1
        "1232",  # The Prince
        "2554",  # Crime and Punishment
        "1080",  # A Modest Proposal
        "174",  # The Picture of Dorian Gray
        "98",  # A Tale of Two Cities
        "25344",  # The Scarlet Letter
        "2591",  # Grimm's Fairy Tales
        "2600",  # War and Peace
        "41",  # The Legend of Sleepy Hollow
        "46",  # A Christmas Carol in Prose; Being a Ghost Story of Christmas
        "3296",  # The Confessions of St. Augustine
        "408",  # The Souls of Black Folk
        "5200",  # Metamorphosis
        "205",  # Walden, and On The Duty Of Civil Disobedience
        "1497",  # The Republic
        "23",  # Narrative of the Life of Frederick Douglass, an American Slave
        "768",  # Wuthering Heights
        "28054",  # The Brothers Karamazov
        "45",  # Anne of Green Gables
        "34901",  # On Liberty
        "219",  # Heart of Darkness
        "20203",  # Autobiography of Benjamin Franklin
        "1184",  # The Count of Monte Cristo
        "1400",  # Great Expectations
        "74",  # The Adventures of Tom Sawyer
        "815",  # Democracy in America
        "4300",  # Ulysses
        "1023",  # Bleak House
        "4363",  # Beyond Good and Evil
        "34450",  # The Nature of Animal Light
        "36",  # War of the Worlds
        "55",  # The Wonderful Wizard of Oz
        "3300",  # An Inquiry into the Nature and Causes of the Wealth of Nations
        "135",  # les Misérables
        "2680",  # Meditations
        "16",  # Peter Pan
        "1399",  # Anna Karenina
        "56517",  # The Philosophy of Auguste Comte
        "52621",  # Society in America, Vol. 1
        "1228",  # On the Origin of Species by Means of Natural Selection
        "18269",  # Pascal's Penseés
        "10554",  # Right Ho, Jeeves
        "10007",  # Carmilla
        "33944",  # How to Observe: Morals and Manners
        "11",  # Alice's Adventures in Wonderland
        "236",  # The Jungle Book
        "4351",  # The English Constitution
        "64317",  # The Great Gatsby
        "8438",  # The Ethics of Aristotle
        "26659",  # The Will to Believe, and Other Essays in Popular Philosophy
    ]

    BOOK_IDS_VALIDATION = [
        "7241",  # Fables of La Fontaine
        "6593",  # History of Tom Jones, a Foundling
        "1342",  # Pride and Prejudice
        "1661",  # The Adventures of Sherlock Holmes
        "15399",  # The Interesting Narrative of the Life of Olaudah Equiano...
        "1998",  # Thus Spake Zarathustra
        "3207",  # Leviathan
        "120",  # Treasure Island
        "2160",  # The Expedition of Humphry Clinker
        "2542",  # A Doll's House
        "84",  # Frankenstein
        "7370",  # Second Treatise of Government
        "12",  # Through the Looking-Glass
        "2852",  # The Hound of the Baskervilles
        "76",  # The Adventures of Huckleberry Finn
        "2148",  # The Works of Edgar Allan Poe - Volume 2
        "1952",  # The Yellow Wallpaper
        "1259",  # Twenty Years After
        "394",  # Cranford
        "76939",  # The laws of contrast of color
        "829",  # Gulliver's Travels into Several Remote Nations of the World
        "60976",  # Rip Van Winkle
        "26184",  # Simple Sabotage Field Manual
        "2814",  # Dubliners
        "36034",  # White Nights and Other Stories
    ]

    def __init__(self, validation: bool = False) -> None:
        """Initialize the BookFetcher with a random book ID and cache status.

        Args:
            validation (bool): If True, use a predefined set of book IDs for validation.

        """
        if validation:
            self.book_id = random.choice(self.BOOK_IDS_VALIDATION)
        else:
            self.book_id = random.choice(self.BOOK_IDS)
        self.is_cached = book_is_cached(self.book_id)

        self.word_pattern = re.compile(r"\S+")

    def fetch_random_book_text(self) -> str:
        """Fetch metadata for a random book from Gutendex and return its text content.

        Returns:
            str: The full contents of a random book from Project Gutenberg.

        """
        url = GUTENDEX_BASE_URL

        if self.is_cached:
            return get_cached_book(self.book_id)

        try:
            r = requests.get(f"{url}/{self.book_id}", timeout=10)
            r.raise_for_status()
            book_metadata = r.json()

            # Now fetch the actual text
            formats = book_metadata.get("formats", {})

            text_url = None
            # Try different text format keys based on what we see in the API response
            for fmt in [
                "text/plain; charset=utf-8",
                "text/plain; charset=us-ascii",
                "text/plain",
            ]:
                if fmt in formats:
                    text_url = formats[fmt]
                    break

            if not text_url:
                raise RuntimeError(
                    f"No suitable text format found for book ID {self.book_id}. "
                    f"Available formats: {list(formats.keys())}",
                )

            text_response = requests.get(text_url, timeout=10)
            text_response.raise_for_status()
            book_text = text_response.text

            formatted_text_with_spaces = format_text(book_text)
            save_book(self.book_id, formatted_text_with_spaces)

            return formatted_text_with_spaces

        except requests.RequestException as e:
            raise RuntimeError(f"Error fetching book data: {e}") from e

    @parameter_validator(
        book_text=non_blank_string,
        min_len=non_negative,
        max_len=non_negative,
    )
    def get_random_book_slice(self, book_text: str, min_len: int, max_len: int) -> str:
        """Extract a random slice from the provided book text.

        Args:
            book_text (str): The entire contents of a book in string format.
            min_len (int): The minimum length of the text slice.
            max_len (int): The maximum length of the text slice.

        Returns:
            str: A random slice of text of a random length or an error
                    if the maximum length exceeds the length of the book.

        Raises:
            ValueError: If book_text is not a string or is shorter than min_len.

        """
        if min_len > max_len:
            raise ValueError(
                "min_len and max_len must be positive integers with min_len <= max_len",
            )

        if len(clean_spaces(book_text)) < max_len:
            raise ValueError("book_text is shorter than the specified max_len")

        length = random.randint(min_len, max_len)

        start_idx = self.get_start_idx(book_text, length)
        end_idx = self.get_end_idx(book_text, start_idx, length)

        return clean_spaces(book_text[start_idx:end_idx])

    def get_start_idx(self, book_text: str, length: int) -> int:
        """Find the start index of the book text slice.

        The start index should come right after a space.

        Args:
            book_text (str): The entire text of the book.
            length (int): The length of the book text slice.

        Returns:
            int: The start index of the book text slice.

        """
        idx = random.randint(0, int(len(book_text) - (length * 1.5)))

        # Walk backwards to find the start of a word
        while idx > 0 and not book_text[idx - 1].isspace():
            idx -= 1
        return idx

    def get_end_idx(self, text: str, start_idx: int, target_len: int) -> int:
        """Find the end index of the book text slice.

        The end index is the index of the last space before the end of the book text.
        The length should not include spaces.

        Args:
            text (str): The entire text of the book.
            start_idx (int): The start index of the book text slice.
            target_len (int): The intended length of the book text slice (no spaces).

        Returns:
            int: The end index of the book text slice.

        """
        current_content_len = 0
        end_idx = start_idx

        # We use finditer to iterate over words efficiently starting from start_idx
        # This skips over massive gaps of whitespace automatically
        for match in self.word_pattern.finditer(text, pos=start_idx):
            word_len = match.end() - match.start()

            current_content_len += word_len

            end_idx = match.end()

            if current_content_len >= target_len:
                break

        return end_idx

    def load_books(self) -> None:
        """Load books from the books directory."""
        for book in self.BOOK_IDS:
            self.book_id = book
            self.fetch_random_book_text()

        for book in self.BOOK_IDS_VALIDATION:
            self.book_id = book
            self.fetch_random_book_text()
