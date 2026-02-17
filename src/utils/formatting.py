from unidecode import unidecode
import re
from num2words import num2words
from parameter_validator import parameter_validator, strongly_typed
from gutenberg_cleaner import simple_cleaner


def numbers_to_words(text: str) -> str:
	"""Convert all numbers in the input text to their word representations.

	Args:
			text (str): The input text containing numbers.

	Returns:
		str: The text with numbers converted to words.

	"""

	def replace_number(match: re.Match) -> str:
		groups = match.groupdict()
		number_str = groups["number"]
		suffix = groups["suffix"]
		
		number_val = float(number_str) if "." in number_str else int(number_str)
		
		if suffix:
			return num2words(number_val, ordinal=True)
		return num2words(number_val)

	pattern = r"(?P<number>\d+(\.\d+)?)(?P<suffix>st|nd|rd|th)?"

	return re.sub(pattern, replace_number, text, flags=re.IGNORECASE)


@parameter_validator(text=strongly_typed)
def format_text(text: str) -> str:
	"""Format text by filtering to alphabetic characters and converting to lowercase.

	Args:
			text (str): A slice of text from a book

	Returns:
			str: The text slice converted to lowercase
				keeping only alphabetic characters.

	"""
	text = simple_cleaner(text)
	text = numbers_to_words(text)
	text = unidecode(text.lower())

	# This seems weird, but there is a reason for it
	# This is necessary when we have a sentence like "he loved--cake!"
	# Since we want "--" to not just be removed, but replaced by a space
	# We want multiple symbols to be replaced by a single space
	text = re.sub(r"[^a-z\s]", "", text)
	return re.sub(r"\s+", " ", text).strip()


@parameter_validator(text=strongly_typed)
def clean_spaces(text: str) -> str:
	"""Remove spaces from the input text.

	Args:
	text (str): The input text

	Returns:
	str: The text with all whitespace removed.

	"""
	return "".join(text.split())
