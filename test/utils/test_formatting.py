from utils.formatting import numbers_to_words

def test_numbers_to_words():
	assert numbers_to_words("I have 3 dogs and 21 cats.") == "I have three dogs and twenty-one cats."
	assert numbers_to_words("The year 2024 will be followed by 2025.") == "The year two thousand and twenty-four will be followed by two thousand and twenty-five."
	assert numbers_to_words("In 2020, the population was 7.8 billion.") == "In two thousand and twenty, the population was seven point eight billion."
	assert numbers_to_words("No numbers here!") == "No numbers here!"
	assert numbers_to_words("Mixed 100 and text 42.5.") == "Mixed one hundred and text forty-two point five."
	assert numbers_to_words("Leading zeros 007 should be seven.") == "Leading zeros seven should be seven."
	assert numbers_to_words("") == ""
	assert numbers_to_words("1234567890") == "one billion, two hundred and thirty-four million, five hundred and sixty-seven thousand, eight hundred and ninety"
