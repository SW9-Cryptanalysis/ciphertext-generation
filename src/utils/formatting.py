from unidecode import unidecode
import re
from num2words import num2words


def numbers_to_words(text: str) -> str:
    """Convert all numbers in the input text to their word representations.

    Args:
                    text (str): The input text containing numbers.
    Returns:
            str: The text with numbers converted to words.
    """

    def replace_number(match: re.Match) -> str:
        """Replace a number in the text with its word representation.

        Args:
                text (str): The input text containing numbers.
        Returns:
                str: The text with numbers converted to words.
        """
        number_str = match.group()
        number_float = float(number_str)
        return num2words(number_float)

    return re.sub(r"\d+(\.\d+)?+", replace_number, text)


def format_text(text: str) -> str:
    """Format text by filtering to alphabetic characters and converting to lowercase.

    Args:
                    text (str): A slice of text from a book

    Returns:
                    str: The text slice converted to lowercase keeping only alphabetic characters.
    """
    if not isinstance(text, str):
        raise ValueError("Argument must be a string")
    text = numbers_to_words(text)
    text = numbers_to_words(text)
    text = unidecode(text.lower())
    return "".join([c for c in text if c.isalpha()])
