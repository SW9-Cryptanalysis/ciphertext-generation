from unidecode import unidecode
import re
from num2words import num2words
from parameter_validator import parameter_validator, strongly_typed
from gutenberg_cleaner import simple_cleaner


def numbers_to_words(text: str, source_id: str = "Unknown") -> str:
	"""Convert all numbers in the input text to their word representations.

	Note: This function converts decimal numbers to integers if they have a suffix.
	Massive number strings (e.g., from ArXiv data dumps) are logged and stripped.

	Args:
		text (str): The input text containing numbers.
		source_id (str, optional): Identifier for logging. Defaults to "Unknown".

	Returns:
		str: The text with numbers converted to words, or stripped if too large.

	"""

	def replace_number(match: re.Match) -> str:
		"""Process individual regex matches, guarding against overflow limits."""
		groups = match.groupdict()
		number_str = groups["number"]
		suffix = groups["suffix"]

		if len(number_str) > 50:
			with open("arxiv_parsing_errors.log", "a", encoding="utf-8") as f:
				f.write(
					f"--- ERROR: Massive Number Detected (Source: {source_id}) ---\n",
				)
				f.write(f"Number length: {len(number_str)}\n")
				f.write(f"Snippet: {number_str[:100]}...\n")
			return ""

		try:
			if suffix:
				sanitized_number = number_str.replace(".", "")
				return num2words(int(sanitized_number), ordinal=True)

			number_val = float(number_str) if "." in number_str else int(number_str)
			return num2words(number_val)

		except Exception as e:
			with open("arxiv_parsing_errors.log", "a", encoding="utf-8") as f:
				context = match.string[max(0, match.start() - 50) : match.end() + 50]
				f.write(f"--- ERROR: num2words failure (Source: {source_id}) ---\n")
				f.write(f"Failed on: {number_str[:100]}\n")
				f.write(f"Context: {context}\n")
				f.write(f"Exception: {e}\n")
			return ""

	pattern = r"(?P<number>\d+(\.\d+)?)(?P<suffix>st|nd|rd|th)?"

	return re.sub(pattern, replace_number, text, flags=re.IGNORECASE)


@parameter_validator(text=strongly_typed)
def format_text(text: str, source_id: str = "Unknown") -> str:
	"""Format text by filtering to alphabetic characters and converting to lowercase.

	Args:
		text (str): A slice of text from a book
		source_id (str, optional): Identifier for logging. Defaults to "Unknown".

	Returns:
		str: The text slice converted to lowercase
			keeping only alphabetic characters.

	"""
	text = simple_cleaner(text)
	text = numbers_to_words(text, source_id)
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
