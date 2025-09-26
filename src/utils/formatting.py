def numbers_to_words(text: str) -> str:
	"""Convert all numbers in the input text to their word representations.

	:param text: The input text containing numbers.
	:type text: str

	:return: The text with numbers converted to words.
	:rtype: str
	"""
	from num2words import num2words
	import re
	def replace_number(match):
		number_str = match.group()
		number_float = float(number_str)
		return num2words(number_float)

	return re.sub(r"\d+(\.\d+)?+", replace_number, text)