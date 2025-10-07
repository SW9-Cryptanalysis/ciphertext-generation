import re
from num2words import num2words

def numbers_to_words(text: str) -> str:
	"""Convert all numbers in the input text to their word representations.
 
	Args:
		text (str): The input text containing numbers.

	Returns:
		str: The text with numbers converted to words.
	"""
	def replace_number(match):
		"""Replace a number in the text with its word representation.

		Args:
			match (re.Match): The regex match object containing the number.

		Returns:
			str: The word representation of the number.
		"""
		number_str = match.group()
		number_float = float(number_str)
		return num2words(number_float)

	return re.sub(r"\d+(\.\d+)?+", replace_number, text)