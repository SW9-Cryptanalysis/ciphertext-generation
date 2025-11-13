from utils.formatting import format_text, numbers_to_words


def test_numbers_to_words():
	assert (
		numbers_to_words("I have 3 dogs and 21 cats.")
		== "I have three dogs and twenty-one cats."
	)
	assert (
		numbers_to_words("The year 2024 will be followed by 2025.")
		== "The year two thousand and twenty-four will be followed by two thousand and twenty-five."
	)
	assert (
		numbers_to_words("In 2020, the population was 7.8 billion.")
		== "In two thousand and twenty, the population was seven point eight billion."
	)
	assert numbers_to_words("No numbers here!") == "No numbers here!"
	assert (
		numbers_to_words("Mixed 100 and text 42.5.")
		== "Mixed one hundred and text forty-two point five."
	)
	assert (
		numbers_to_words("Leading zeros 007 should be seven.")
		== "Leading zeros seven should be seven."
	)
	assert numbers_to_words("") == ""
	assert (
		numbers_to_words("1234567890")
		== "one billion, two hundred and thirty-four million, five hundred and sixty-seven thousand, eight hundred and ninety"
	)


def test_format_text():
	assert (
		format_text(
			"I met a traveller from an antique land, Who said—“Two vast and trunkless legs of stone Stand in the desert..."
		)
		== "i met a traveller from an antique land who said two vast and trunkless legs of stone stand in the desert"
	)
	assert format_text("Kózuscek Fránçois àéäöåôëëën") == "kozuscek francois aeaoaoeeen"
	assert format_text("123 ABC def!@#") == "one hundred and twenty three abc def"
	assert format_text("") == ""
	try:
		format_text(12345)  # type: ignore
	except TypeError as e:
		assert str(e) == "Parameter 'text' requires type 'str' but received type 'int'."


def test_format_text_only_numbers():
	assert (
		format_text("2024 100 3.14")
		== "two thousand and twenty four one hundred three point one four"
	)


def test_format_text_all_non_alpha():
	assert (
		format_text("1234!@#$%^&'*()’_+-=[]{}’|;:',.<>?/`~")
		== "one thousand two hundred and thirty four"
	)
