import pytest
from encipherment.cipher import HomophonicCipher, MonoalphabeticCipher
from utils.constants import MIN_DIFFICULTY, MAX_DIFFICULTY

# --- Fixtures ---

@pytest.fixture(scope="module")
def sample_text_short():
	return "abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(scope="module")
def sample_stream_short(sample_text_short):
	"""Returns a short valid TextStream dictionary."""
	return {
		"text": sample_text_short,
		"text_with_boundaries": sample_text_short,
		"source_id": "short_1",
		"source_name": "Alphabet",
		"length": len(sample_text_short),
	}


@pytest.fixture(scope="module")
def sample_texts_illegal():
	return [
		"ThisTextHasUppercaseLettersAnd12345Numbers!@#",
		"This text has spaces",
		"this-text-has-dashes",
		"this.text.has.punctuation!",
	]


@pytest.fixture(scope="module")
def sample_stream_illegal(sample_texts_illegal):
	"""Returns an invalid TextStream dictionary for HomophonicCipher."""
	return [
		{
			"text": text,
			"text_with_boundaries": text,
			"source_id": "book_123",
			"source_name": "Test Book",
			"length": len(text),
		}
		for text in sample_texts_illegal
	]


@pytest.fixture
def bad_streams():
	"""Returns a list of invalid TextStream dictionaries for HomophonicCipher."""
	return [
		{
			"text": "",
			"text_with_boundaries": "",
			"source_id": "book_123",
			"source_name": "Test Book",
			"length": len("invalid"),
		},
		{
			"text": " ",
			"text_with_boundaries": " ",
			"source_id": "book_123",
			"source_name": "Test Book",
			"length": 0,
		},
		{
			"text": "inval id",
			"text_with_boundaries": "inval_id",
			"source_id": "book_123",
			"source_name": "Test Book",
			"length": None,
		},
	]


# --- HomophonicCipher Tests ---


class TestHomophonicCipher:
	class TestHomophonicCipherInit:
		def test_legal_plaintext(self, valid_text_stream):
			# Pass the stream object (dict), not just the string
			cipher = HomophonicCipher(valid_text_stream)
			cipher.generate_key()
			cipher.encipher()

			assert cipher.plaintext == valid_text_stream["text"]
			assert cipher.source_id == valid_text_stream["source_id"]
			assert cipher.source_name == valid_text_stream["source_name"]

			assert MIN_DIFFICULTY <= cipher.difficulty <= MAX_DIFFICULTY
			assert isinstance(cipher.key, dict)
			assert all(isinstance(v, list) for v in cipher.key.values())
			assert isinstance(cipher.ciphertext, str)
			assert all(num.isdigit() for num in cipher.ciphertext.split())

		def test_all_homophones_used(self, valid_text_stream):
			cipher = HomophonicCipher(valid_text_stream)
			used_homophones = set(int(num) for num in cipher.ciphertext.split())
			all_homophones = set()
			for homophones in cipher.key.values():
				all_homophones.update(homophones)
			assert used_homophones == all_homophones, (
				f"Used homophones {used_homophones} do not match all homophones {all_homophones}"
			)

		def test_illegal_plaintext(self, sample_texts_illegal):
			for text in sample_texts_illegal:
				# Wrap illegal text in a TextStream dict structure
				bad_stream = {"text": text, "source_name": "bad"}

				with pytest.raises(KeyError) as excinfo:
					HomophonicCipher(bad_stream)  # type: ignore
				assert "text_obj" in str(excinfo.value)
				assert "Missing keys:" in str(excinfo.value)
				assert "source_id" in str(excinfo.value)
				assert "source_name" in str(excinfo.value)

		def test_defined_difficulty(self, valid_text_stream):
			for difficulty in range(4, 11):
				cipher = HomophonicCipher(valid_text_stream, difficulty=difficulty)
				assert cipher.difficulty == difficulty

		def test_key_homophones_count(self, valid_text_stream):
			cipher = HomophonicCipher(valid_text_stream)
			cipher.generate_key()
			total_homophones = sum(len(v) for v in cipher.key.values())
			expected_homophones = round(
				len(valid_text_stream["text"]) / cipher.difficulty
			)

			unique_letters = len(set(valid_text_stream["text"]))

			assert total_homophones >= unique_letters, (
				f"Total homophones {total_homophones} is less than unique letters {unique_letters}"
			)

			expected_range = max(15, expected_homophones)
			assert abs(total_homophones - expected_homophones) <= expected_range, (
				f"Total homophones {total_homophones} not within acceptable range."
			)

		def test_ciphertext_numbers_within_range(self, valid_text_stream):
			cipher = HomophonicCipher(valid_text_stream)
			ciphertext_numbers = list(map(int, cipher.ciphertext.split()))
			total_homophones = sum(len(v) for v in cipher.key.values())
			assert all(1 <= num <= total_homophones for num in ciphertext_numbers)

		def test_ciphertext_length(self, valid_text_stream):
			cipher = HomophonicCipher(valid_text_stream)
			cipher.generate_key()
			cipher.encipher()
			ciphertext_numbers = cipher.ciphertext.split()
			assert len(ciphertext_numbers) == len(valid_text_stream["text"])

		def test_invalid_difficulty(self, valid_text_stream):
			for invalid_difficulty in [3, 31, -1, 0]:
				with pytest.raises(ValueError) as excinfo:
					HomophonicCipher(valid_text_stream, difficulty=invalid_difficulty)
				assert (
					f"Parameter `difficulty` must be between {MIN_DIFFICULTY} and {MAX_DIFFICULTY}."
					in str(excinfo.value)
				)

		def test_non_integer_difficulty(self, valid_text_stream):
			for non_integer in [5.5, "ten"]:
				with pytest.raises(TypeError) as excinfo:
					HomophonicCipher(valid_text_stream, difficulty=non_integer)
				assert "Parameter `difficulty` must be of type int, or None." in str(
					excinfo.value
				)

		def test_non_stream_plaintext(self):
			# The validator expects text_obj to be the first arg, validation might fail
			# inside __init__ when accessing ["text"] if input is not subscriptable
			for invalid_input in [12345, None, 5.67]:
				with pytest.raises(TypeError):
					HomophonicCipher(invalid_input)

		def test_empty_string_plaintext_in_stream(self, bad_streams):
			for bad_stream in bad_streams:
				with pytest.raises(ValueError) as excinfo:
					HomophonicCipher(bad_stream)  # type: ignore
				assert (
					"must include a non-empty, lowercase alphabetic string with no spaces in the text field."
					in str(excinfo.value)
				)

	class TestHomophonicSerialization:
		def test_json_serialization(self, valid_text_stream):
			cipher = HomophonicCipher(valid_text_stream)
			json_data = cipher.__json__()
			assert isinstance(json_data, dict)
			assert json_data["plaintext"] == valid_text_stream["text"]
			assert json_data["source_id"] == valid_text_stream["source_id"]
			assert json_data["source_name"] == valid_text_stream["source_name"]
			assert json_data["difficulty"] == cipher.difficulty
			assert json_data["key"] == cipher.key
			assert json_data["ciphertext"] == cipher.ciphertext

		def test_str_representation(self, valid_text_stream):
			cipher = HomophonicCipher(valid_text_stream)
			str_repr = str(cipher)
			assert 'HomophonicCipher(Plaintext: "' in str_repr
			assert f'"{valid_text_stream["text"]}"' in str_repr
			assert f"Difficulty: {cipher.difficulty}" in str_repr
			assert f"Key: {cipher.key}" in str_repr
			assert f'Ciphertext: "{cipher.ciphertext}"' in str_repr

	def test_recurrence_encoding(self, valid_text_stream):
		cipher = HomophonicCipher(valid_text_stream)
		cipher.generate_key()
		cipher.encipher()
		encoding = cipher.recurrence_encoding
		assert isinstance(encoding, str)
		assert len(encoding.split()) == len(valid_text_stream["text"])

		encoding_numbers = list(map(int, encoding.split()))
		assert all(num >= 1 for num in encoding_numbers)
		assert set(encoding_numbers) == set(range(1, max(encoding_numbers) + 1))

	class TestApplyRecurrenceAndRemapKey:
		def test_standard_remapping_logic(self, sample_stream_short):
			"""Verify that arbitrary cipher symbols are remapped to 1..N order."""
			cipher = HomophonicCipher(sample_stream_short)
			# Manually inject state to test the remapping logic in isolation
			# Plaintext: abc... (from sample_stream_short)
			# Let's simulate a ciphertext where 'a'=99, 'b'=10, 'c'=50
			cipher.key = {"a": [99], "b": [10], "c": [50]}
			cipher.ciphertext = "99 10 50 10 50"  # Represents "abcbc"

			cipher._apply_recurrence_and_remap_key()

			# 1. Ciphertext should now be 1 2 3 2 3
			assert cipher.ciphertext == "1 2 3 2 3"

			# 2. Key must match the new values
			assert cipher.key["a"] == [1]
			assert cipher.key["b"] == [2]
			assert cipher.key["c"] == [3]

		def test_homophone_remapping(self, sample_stream_short):
			"""Ensure multiple homophones for one letter are mapped to distinct IDs."""
			cipher = HomophonicCipher(sample_stream_short)
			# 'a' has two homophones, 'b' has one
			cipher.key = {"a": [88, 89], "b": [44]}
			# Sequence: a(89) a(88) b(44)
			cipher.ciphertext = "89 88 44"

			cipher._apply_recurrence_and_remap_key()

			# First seen: 89 -> 1, Second seen: 88 -> 2, Third seen: 44 -> 3
			assert cipher.ciphertext == "1 2 3"
			assert set(cipher.key["a"]) == {1, 2}
			assert cipher.key["b"] == [3]

		def test_unused_homophones_are_dropped(self, sample_stream_short):
			"""Verify that symbols in the key not appearing in ciphertext are removed."""
			cipher = HomophonicCipher(sample_stream_short)
			# 77 is assigned to 'a' but never used in the ciphertext
			cipher.key = {"a": [10, 77], "b": [20]}
			cipher.ciphertext = "10 20"

			cipher._apply_recurrence_and_remap_key()

			# 10 becomes 1, 20 becomes 2. 77 is missing from ciphertext.
			assert cipher.key["a"] == [1]
			assert cipher.key["b"] == [2]
			assert 77 not in cipher.key["a"]

	class TestRemappingIntegrity:
		def test_first_seen_is_always_one(self, sample_stream_short):
			"""
			Tests that the actual value of the original symbol doesn't matter;
			the first one encountered in the stream MUST become '1'.
			"""
			cipher = HomophonicCipher(sample_stream_short)

			# Scenario A: 'z' is 500, 'a' is 10. Text starts with 'z'.
			cipher.key = {"z": [500], "a": [10]}
			cipher.ciphertext = "500 10 500"
			cipher._apply_recurrence_and_remap_key()
			assert cipher.ciphertext.startswith("1")
			assert cipher.key["z"] == [1]
			assert cipher.key["a"] == [2]

			# Scenario B: Swap the order. 'a' is seen first.
			cipher.key = {"z": [500], "a": [10]}
			cipher.ciphertext = "10 500 10"
			cipher._apply_recurrence_and_remap_key()
			assert cipher.ciphertext.startswith("1")
			assert cipher.key["a"] == [1]
			assert cipher.key["z"] == [2]

		def test_key_value_consistency(self, sample_stream_short):
			"""
			Verify that if a letter has multiple homophones, the remapping
			correctly updates all of them within the key list.
			"""
			cipher = HomophonicCipher(sample_stream_short)
			# 'e' has three homophones. We use them in a specific order.
			cipher.key = {"e": [100, 200, 300]}
			cipher.ciphertext = "300 100 200"

			cipher._apply_recurrence_and_remap_key()

			# Appearance: 300->1, 100->2, 200->3
			assert cipher.ciphertext == "1 2 3"
			# The list in the key should now reflect these new values
			assert set(cipher.key["e"]) == {1, 2, 3}

		def test_complex_overlap_integrity(self, sample_stream_short):
			"""
			Test a complex sequence to ensure no 'collisions' occur during remapping
			where a new ID accidentally overwrites an unmapped old ID.
			"""
			cipher = HomophonicCipher(sample_stream_short)
			# Setup: Numbers that might overlap with the 1..N range
			cipher.key = {"a": [1], "b": [2], "c": [3]}
			# Ciphertext where they appear in reverse order
			cipher.ciphertext = "3 2 1"

			cipher._apply_recurrence_and_remap_key()

			# If mapping is done correctly: 3->1, 2->2, 1->3
			assert cipher.ciphertext == "1 2 3"
			assert cipher.key["c"] == [1]
			assert cipher.key["b"] == [2]
			assert cipher.key["a"] == [3]

		def test_key_remains_int_types(self, sample_stream_short):
			"""
			Ensure the remapped key contains integers (for JSON)
			while the ciphertext remains a string of numbers.
			"""
			cipher = HomophonicCipher(sample_stream_short)
			cipher.key = {"a": [123]}
			cipher.ciphertext = "123"

			cipher._apply_recurrence_and_remap_key()

			assert isinstance(cipher.key["a"][0], int)
			assert isinstance(cipher.ciphertext.split()[0], str)


# --- MonoalphabeticCipher Tests ---


class TestMonoalphabeticCipher:
	def test_legal_plaintext(self, sample_stream_short):
		# FIX: Pass stream dict, not string
		cipher = MonoalphabeticCipher(sample_stream_short)

		assert cipher.plaintext == sample_stream_short["text"]
		assert cipher.source_id == sample_stream_short["source_id"]
		assert cipher.source_name == sample_stream_short["source_name"]

		assert isinstance(cipher.key, dict)
		assert all(isinstance(v, list) and len(v) == 1 for v in cipher.key.values())
		assert isinstance(cipher.ciphertext, str)
		assert all(num.isdigit() for num in cipher.ciphertext.split())

	def test_key_structure(self, sample_stream_short):
		cipher = MonoalphabeticCipher(sample_stream_short)

		assert len(cipher.key) == 26
		for letter in "abcdefghijklmnopqrstuvwxyz":
			assert letter in cipher.key
			assert len(cipher.key[letter]) == 1

		all_numbers = [cipher.key[letter][0] for letter in "abcdefghijklmnopqrstuvwxyz"]
		assert sorted(all_numbers) == list(range(1, 27))
		assert len(set(all_numbers)) == 26

	def test_ciphertext_length(self, sample_stream_short):
		cipher = MonoalphabeticCipher(sample_stream_short)
		ciphertext_numbers = cipher.ciphertext.split()
		assert len(ciphertext_numbers) == len(sample_stream_short["text"])

	def test_json_serialization_success(self, sample_stream_short):
		"""
		FIX: This previously expected failure. Now that MonoalphabeticCipher
		sets source_id/name, serialization should SUCCEED.
		"""
		cipher = MonoalphabeticCipher(sample_stream_short)
		json_data = cipher.__json__()

		assert isinstance(json_data, dict)
		assert json_data["plaintext"] == sample_stream_short["text"]
		assert json_data["source_id"] == sample_stream_short["source_id"]
		assert json_data["source_name"] == sample_stream_short["source_name"]
		assert json_data["key"] == cipher.key
		assert json_data["ciphertext"] == cipher.ciphertext

	def test_str_representation(self, sample_stream_short):
		cipher = MonoalphabeticCipher(sample_stream_short)
		str_repr = str(cipher)
		assert 'MonoalphabeticCipher(Plaintext: "' in str_repr
		assert f'"{sample_stream_short["text"]}"' in str_repr
		assert f"Key: {cipher.key}" in str_repr
		assert f'Ciphertext: "{cipher.ciphertext}"' in str_repr

	def test_illegal_plaintext(self, sample_stream_illegal):
		for text_obj in sample_stream_illegal:

			with pytest.raises(ValueError) as excinfo:
				MonoalphabeticCipher(text_obj)  # type: ignore

			# Use the error message from validate_text_obj
			assert (
				"must include a non-empty, lowercase alphabetic string with no spaces"
				in str(excinfo.value)
			)

	def test_non_dict_input(self):
		# FIX: The validator now checks if input is a dict/TextStream
		for invalid_input in [12345, None, 5.67, "just a string"]:
			with pytest.raises(TypeError):
				MonoalphabeticCipher(invalid_input)  # type: ignore

	def test_empty_string_plaintext(self, bad_streams):
		for bad_stream in bad_streams:
			with pytest.raises(ValueError) as excinfo:
				MonoalphabeticCipher(bad_stream)  # type: ignore
			assert "must include a non-empty, lowercase alphabetic string" in str(
				excinfo.value
			)
