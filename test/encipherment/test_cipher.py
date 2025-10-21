import pytest

from encipherment.cipher import HomophonicCipher, MonoalphabeticCipher
from utils.constants import MIN_DIFFICULTY, MAX_DIFFICULTY


@pytest.fixture(scope="module")
def sample_text_legal():
	return (
		"thisisatestplaintextthatneedstobeencrypteditisjustarandomstringoflowercaselettersthatshouldworkfineanditislong"
		"enoughtotestthecipherwiththelengthshouldbeoverfourhundredcharactersmaybeevenfivehundredduetothistweneedtoensure"
		"thecipherworksasexpectedandcanhandlelargerinputswithoutanyissuesandthatthistextisextremelylongsoitcanbeusedtotest"
		"theperformanceoftheciphergenerationprocess"
	)


@pytest.fixture(scope="module")
def sample_text_short():
	return "abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(scope="module")
def sample_texts_illegal():
	return [
		"ThisTextHasUppercaseLettersAnd12345Numbers!@#",
		"This text has spaces",
		"this-text-has-dashes",
		"this.text.has.punctuation!",
	]


class TestHomophonicCipher:
	def test_legal_plaintext(self, sample_text_legal):
		cipher = HomophonicCipher(sample_text_legal)
		cipher.generate_key()
		cipher.encipher()

		assert cipher.plaintext == sample_text_legal
		assert MIN_DIFFICULTY <= cipher.difficulty <= MAX_DIFFICULTY
		assert isinstance(cipher.key, dict)
		assert all(isinstance(v, list) for v in cipher.key.values())
		assert isinstance(cipher.ciphertext, str)
		assert all(num.isdigit() for num in cipher.ciphertext.split())

	def test_all_homophones_used(self, sample_text_legal):
		cipher = HomophonicCipher(sample_text_legal)
		used_homophones = set(int(num) for num in cipher.ciphertext.split())
		all_homophones = set()
		for homophones in cipher.key.values():
			all_homophones.update(homophones)
		assert used_homophones == all_homophones, (
			f"Used homophones {used_homophones} do not match all homophones {all_homophones}"
		)

	def test_illegal_plaintext(self, sample_texts_illegal):
		for text in sample_texts_illegal:
			with pytest.raises(ValueError) as excinfo:
				HomophonicCipher(text)
			assert (
				"Parameter `plaintext` must be a lowercase alphabetic string with no spaces."
				in str(excinfo.value)
			)

	def test_defined_difficulty(self, sample_text_legal):
		for difficulty in range(4, 11):
			cipher = HomophonicCipher(sample_text_legal, difficulty=difficulty)
			assert cipher.difficulty == difficulty

	def test_key_homophones_count(self, sample_text_legal):
		cipher = HomophonicCipher(sample_text_legal)
		cipher.generate_key()
		total_homophones = sum(len(v) for v in cipher.key.values())
		expected_homophones = round(len(sample_text_legal) / cipher.difficulty)

		# Assert that the total number of homophones is reasonable
		# At minimum, we need one homophone per unique letter in the text
		unique_letters = len(set(sample_text_legal))

		assert total_homophones >= unique_letters, (
			f"Total homophones {total_homophones} is less than unique letters {unique_letters}"
		)

		# For high difficulties, expected homophones might be very low, so we allow more flexibility
		expected_range = max(
			15, expected_homophones
		)  # Allow more range for high difficulties
		assert abs(total_homophones - expected_homophones) <= expected_range, (
			f"Total homophones {total_homophones} not within acceptable range of expected {expected_homophones} ± {expected_range}"
		)

	def test_ciphertext_numbers_within_range(self, sample_text_legal):
		cipher = HomophonicCipher(sample_text_legal)
		ciphertext_numbers = list(map(int, cipher.ciphertext.split()))
		total_homophones = sum(len(v) for v in cipher.key.values())
		assert all(1 <= num <= total_homophones for num in ciphertext_numbers)

	def test_ciphertext_length(self, sample_text_legal):
		cipher = HomophonicCipher(sample_text_legal)
		cipher.generate_key()
		cipher.encipher()
		ciphertext_numbers = cipher.ciphertext.split()
		assert len(ciphertext_numbers) == len(sample_text_legal)

	def test_json_serialization(self, sample_text_legal):
		cipher = HomophonicCipher(sample_text_legal)
		json_data = cipher.__json__()
		assert isinstance(json_data, dict)
		assert json_data["plaintext"] == sample_text_legal
		assert json_data["difficulty"] == cipher.difficulty
		assert json_data["key"] == cipher.key
		assert json_data["ciphertext"] == cipher.ciphertext
		assert json_data["recurrence_encoding"] == cipher.recurrence_encoding

	def test_str_representation(self, sample_text_legal):
		cipher = HomophonicCipher(sample_text_legal)
		str_repr = str(cipher)
		assert 'HomophonicCipher(Plaintext: "' in str_repr
		assert f'"{sample_text_legal}"' in str_repr
		assert f"Difficulty: {cipher.difficulty}" in str_repr
		assert f"Key: {cipher.key}" in str_repr
		assert f'Ciphertext: "{cipher.ciphertext}"' in str_repr
		assert f'Recurrence Encoding: "{cipher.recurrence_encoding}"' in str_repr

	def test_invalid_difficulty(self, sample_text_legal):
		for invalid_difficulty in [3, 31, -1, 0]:
			with pytest.raises(ValueError) as excinfo:
				HomophonicCipher(sample_text_legal, difficulty=invalid_difficulty)
			assert (
				f"Parameter `difficulty` must be between {MIN_DIFFICULTY} and {MAX_DIFFICULTY}."
				in str(excinfo.value)
			), f"Failed for difficulty {invalid_difficulty}"

	def test_non_integer_difficulty(self, sample_text_legal):
		for non_integer in [5.5, "ten"]:
			with pytest.raises(TypeError) as excinfo:
				HomophonicCipher(sample_text_legal, difficulty=non_integer)
			assert "Parameter `difficulty` must be of type int, or None." in str(excinfo.value)

	def test_non_string_plaintext(self):
		for non_string in [12345, None, 5.67, ["list"], {"dict": "value"}]:
			with pytest.raises(TypeError) as excinfo:
				HomophonicCipher(non_string)
			assert "Parameter `plaintext` must be of type str." in str(excinfo.value)

	def test_empty_string_plaintext(self):
		with pytest.raises(ValueError) as excinfo:
			HomophonicCipher(" ")
		assert "Parameter `plaintext` must be a non-blank string." in str(excinfo.value)

	def test_plaintext_with_non_english_letters(self):
		for text in [
			"thisisatestplaintextwithé",
			"thisisatestplaintextwithñ",
			"thisisatestplaintextwithü",
		]:
			with pytest.raises(ValueError) as excinfo:
				HomophonicCipher(text)
			assert (
				"Parameter `plaintext` must be a lowercase alphabetic string with no spaces."
				in str(excinfo.value)
			)

	def test_recurrence_encoding(self, sample_text_legal):
		cipher = HomophonicCipher(sample_text_legal)
		cipher.generate_key()
		cipher.encipher()
		encoding = cipher.recurrence_encoding
		assert isinstance(encoding, str)
		assert len(encoding.split()) == len(sample_text_legal)

		# Check that the encoding uses numbers starting from 1
		encoding_numbers = list(map(int, encoding.split()))
		assert all(num >= 1 for num in encoding_numbers)
		assert set(encoding_numbers) == set(range(1, max(encoding_numbers) + 1))
		# Check that the same symbol in ciphertext maps to the same number in encoding
		ciphertext_numbers = cipher.ciphertext.split()
		mapping = {}
		for ct_num, enc_num in zip(ciphertext_numbers, encoding_numbers, strict=False):
			if ct_num not in mapping:
				mapping[ct_num] = enc_num
			else:
				assert mapping[ct_num] == enc_num, (
					"Inconsistent mapping in recurrence encoding"
				)


class TestMonoalphabeticCipher:
	def test_legal_plaintext(self, sample_text_short):
		cipher = MonoalphabeticCipher(sample_text_short)
		assert cipher.plaintext == sample_text_short
		assert isinstance(cipher.key, dict)
		assert all(isinstance(v, list) and len(v) == 1 for v in cipher.key.values())
		assert isinstance(cipher.ciphertext, str)
		assert all(num.isdigit() for num in cipher.ciphertext.split())

	def test_key_structure(self, sample_text_short):
		cipher = MonoalphabeticCipher(sample_text_short)

		# Test that all 26 letters have exactly one homophone
		assert len(cipher.key) == 26
		for letter in "abcdefghijklmnopqrstuvwxyz":
			assert letter in cipher.key
			assert len(cipher.key[letter]) == 1

		# Test that numbers 1-26 are used exactly once
		all_numbers = [cipher.key[letter][0] for letter in "abcdefghijklmnopqrstuvwxyz"]
		assert sorted(all_numbers) == list(range(1, 27))
		assert len(set(all_numbers)) == 26  # All unique

	def test_randomization(self, sample_text_short):
		"""Test that different instances generate different random mappings."""
		cipher1 = MonoalphabeticCipher(sample_text_short)
		cipher2 = MonoalphabeticCipher(sample_text_short)

		# Keys should be different (randomized)
		key1_numbers = [cipher1.key[letter][0] for letter in "abcde"]
		key2_numbers = [cipher2.key[letter][0] for letter in "abcde"]

		# It's extremely unlikely that the first 5 letters map to the same numbers
		assert key1_numbers != key2_numbers, "Keys should be randomized"

	def test_consistency(self, sample_text_short):
		"""Test that same letters consistently map to same numbers within one cipher."""
		plaintext = "aabbccdd"
		cipher = MonoalphabeticCipher(plaintext)

		ciphertext_numbers = [int(x) for x in cipher.ciphertext.split()]

		# Same letters should map to same numbers
		assert ciphertext_numbers[0] == ciphertext_numbers[1]  # Both 'a's
		assert ciphertext_numbers[2] == ciphertext_numbers[3]  # Both 'b's
		assert ciphertext_numbers[4] == ciphertext_numbers[5]  # Both 'c's
		assert ciphertext_numbers[6] == ciphertext_numbers[7]  # Both 'd's

	def test_ciphertext_length(self, sample_text_short):
		cipher = MonoalphabeticCipher(sample_text_short)
		ciphertext_numbers = cipher.ciphertext.split()
		assert len(ciphertext_numbers) == len(sample_text_short)

	def test_json_serialization(self, sample_text_short):
		cipher = MonoalphabeticCipher(sample_text_short)
		json_data = cipher.__json__()
		assert isinstance(json_data, dict)
		assert json_data["plaintext"] == sample_text_short
		assert json_data["difficulty"] == cipher.difficulty
		assert json_data["key"] == cipher.key
		assert json_data["ciphertext"] == cipher.ciphertext
		assert json_data["recurrence_encoding"] == cipher.recurrence_encoding

	def test_str_representation(self, sample_text_short):
		cipher = MonoalphabeticCipher(sample_text_short)
		str_repr = str(cipher)
		assert 'MonoalphabeticCipher(Plaintext: "' in str_repr
		assert f'"{sample_text_short}"' in str_repr
		assert f"Difficulty: {cipher.difficulty}" in str_repr
		assert f"Key: {cipher.key}" in str_repr
		assert f'Ciphertext: "{cipher.ciphertext}"' in str_repr
		assert f'Recurrence Encoding: "{cipher.recurrence_encoding}"' in str_repr

	def test_illegal_plaintext(self, sample_texts_illegal):
		for text in sample_texts_illegal:
			with pytest.raises(ValueError) as excinfo:
				MonoalphabeticCipher(text)
			assert (
				"Parameter `plaintext` must be a lowercase alphabetic string with no spaces."
				in str(excinfo.value)
			)

	def test_non_string_plaintext(self):
		for non_string in [12345, None, 5.67, ["list"], {"dict": "value"}]:
			with pytest.raises(TypeError) as excinfo:
				MonoalphabeticCipher(non_string)
			assert "Parameter `plaintext` must be of type str." in str(excinfo.value)

	def test_empty_string_plaintext(self):
		with pytest.raises(ValueError) as excinfo:
			MonoalphabeticCipher("")
		assert "Parameter `plaintext` must be a non-blank string." in str(excinfo.value)

	def test_recurrence_encoding(self, sample_text_short):
		cipher = MonoalphabeticCipher(sample_text_short)
		encoding = cipher.recurrence_encoding
		assert isinstance(encoding, str)
		assert len(encoding.split()) == len(sample_text_short)

		# For monoalphabetic cipher, recurrence encoding should show the order
		# in which unique cipher symbols first appeared
		encoding_numbers = list(map(int, encoding.split()))
		assert all(num >= 1 for num in encoding_numbers)

		# Check consistency: same ciphertext number should map to same encoding number
		ciphertext_numbers = cipher.ciphertext.split()
		mapping = {}
		for ct_num, enc_num in zip(ciphertext_numbers, encoding_numbers, strict=False):
			if ct_num not in mapping:
				mapping[ct_num] = enc_num
			else:
				assert mapping[ct_num] == enc_num, (
					"Inconsistent mapping in recurrence encoding"
				)
