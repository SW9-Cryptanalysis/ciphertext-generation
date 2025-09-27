def numbers_to_words(text: str) -> str:
	"""Convert all numbers in the input text to their word representations.
 
	Args:
		text (str): The input text containing numbers.

	Returns:
		str: The text with numbers converted to words.
	"""
	from num2words import num2words
	import re
	def replace_number(match):
		number_str = match.group()
		number_float = float(number_str)
		return num2words(number_float)

	return re.sub(r"\d+(\.\d+)?+", replace_number, text)