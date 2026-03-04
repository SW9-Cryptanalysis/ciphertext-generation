import pytest
from encipherment.cipher import HomophonicCipher, MonoalphabeticCipher
from utils.constants import MIN_DIFFICULTY, MAX_DIFFICULTY
from typing import Any
from dataclasses import dataclass

# --- Fixtures ---


@pytest.fixture(scope="module")
def sample_stream_short():
	"""Returns a very short valid TextStream dictionary."""
	return {
		"text": "abcbc",
		"text_with_boundaries": "abc_bc",
		"source_id": "short_1",
		"source_name": "Alphabet",
		"length": len("abcbc"),
		"genres": ["Sci-Fi & Fantasy"],
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
			"genres": [],
		}
		for text in sample_texts_illegal
	]


@dataclass
class BadStreamTestCase:
	"""Encapsulates parameters for testing invalid TextStream dictionaries."""
	desc: str
	stream: dict[str, Any]
	expected_exception: type[Exception]
	match: str


BAD_STREAM_CASES = [
	BadStreamTestCase(
		desc="Invalid: Empty plaintext string",
		stream={
			"text": "",
			"text_with_boundaries": "",
			"source_id": "book_123",
			"source_name": "Test Book",
			"length": 0,
			"genres": [],
		},
		expected_exception=ValueError,
		match="non-empty",
	),
	BadStreamTestCase(
		desc="Invalid: Whitespace only plaintext string",
		stream={
			"text": " ",
			"text_with_boundaries": " ",
			"source_id": "book_123",
			"source_name": "Test Book",
			"length": 0,
			"genres": [],
		},
		expected_exception=ValueError,
		match="lowercase alphabetic string with no spaces",
	),
	BadStreamTestCase(
		desc="Invalid: Length is None type",
		stream={
			"text": "invalid",
			"text_with_boundaries": "inval_id",
			"source_id": "book_123",
			"source_name": "Test Book",
			"length": None,
			"genres": [],
		},
		expected_exception=ValueError,
		match="Invalid type for key 'length'",
	),
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

				with pytest.raises(ValueError, match="Missing required keys"):
					HomophonicCipher(bad_stream)  # type: ignore

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

		@pytest.mark.parametrize("case", BAD_STREAM_CASES, ids=lambda c: c.desc)
		def test_invalid_stream_initialization(self, case: BadStreamTestCase):
			"""Test that invalid stream parameters raise the specific expected exceptions."""
			with pytest.raises(case.expected_exception, match=case.match):
				HomophonicCipher(case.stream) # type: ignore

	class TestHomophonicSerialization:
		def test_json_serialization(self, valid_text_stream):
			cipher = HomophonicCipher(valid_text_stream)
			json_data = cipher.__json__()
			assert isinstance(json_data, dict)
			assert json_data["plaintext"] == valid_text_stream["text"]
			assert (
				json_data["plaintext_with_boundaries"]
				== valid_text_stream["text_with_boundaries"]
			)
			assert json_data["source_id"] == valid_text_stream["source_id"]
			assert json_data["source_name"] == valid_text_stream["source_name"]
			assert json_data["difficulty"] == cipher.difficulty
			assert json_data["key"] == cipher.key
			assert json_data["ciphertext"] == cipher.ciphertext
			assert (
				json_data["ciphertext_with_boundaries"]
				== cipher.ciphertext_with_boundaries
			)

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
			cipher.key = {"a": [88], "b": [44, 11], "c": [22]}
			cipher.ciphertext = "88 44 22 11 22"

			cipher._apply_recurrence_and_remap_key()

			# First seen: 89 -> 1, Second seen: 88 -> 2, Third seen: 44 -> 3
			assert cipher.ciphertext == "1 2 3 4 3"
			assert set(cipher.key["a"]) == {1}
			assert set(cipher.key["b"]) == {2, 4}
			assert set(cipher.key["c"]) == {3}

		def test_unused_homophones_are_dropped(self, sample_stream_short):
			"""Verify that symbols in the key not appearing in ciphertext are removed."""
			cipher = HomophonicCipher(sample_stream_short)
			# 77 is assigned to 'a' but never used in the ciphertext
			cipher.key = {"a": [10], "b": [20], "c": [77, 11]}
			cipher.ciphertext = "10 20 11 20 77"

			cipher._apply_recurrence_and_remap_key()

			# 10 becomes 1, 20 becomes 2. 77 is missing from ciphertext.
			assert set(cipher.key["a"]) == {1}
			assert set(cipher.key["b"]) == {2}
			assert set(cipher.key["c"]) == {3, 4}
			assert 77 not in cipher.key["a"]

		def test_generate_bounded_ciphertext_logic(self, sample_stream_short):
			"""Verify that underscores from plaintext are perfectly mirrored into ciphertext."""
			cipher = HomophonicCipher(sample_stream_short)

			cipher.key = {"a": [99], "b": [10], "c": [50]}
			cipher.ciphertext = "99 10 50 10 50"

			cipher._apply_recurrence_and_remap_key()

			assert cipher.ciphertext == "1 2 3 2 3"
			assert cipher.ciphertext_with_boundaries == "1 2 3 _ 2 3"

	class TestRemappingIntegrity:
		def test_first_seen_is_always_one(self, sample_stream_short):
			"""
			Tests that the actual value of the original symbol doesn't matter;
			the first one encountered in the stream MUST become '1'.
			"""
			cipher = HomophonicCipher(sample_stream_short)

			cipher.key = {"a": [10], "b": [20], "c": [30]}
			cipher.ciphertext = "10 20 30 20 30"
			cipher._apply_recurrence_and_remap_key()
			assert cipher.ciphertext.startswith("1")
			assert set(cipher.key["a"]) == {1}
			assert set(cipher.key["b"]) == {2}
			assert set(cipher.key["c"]) == {3}

			# Swap the order. 'c' is seen first.
			cipher.ciphertext = "30 10 30 20 10"
			cipher.key = {"a": [10], "b": [20], "c": [30]}
			cipher._apply_recurrence_and_remap_key()
			assert cipher.ciphertext.startswith("1")
			assert set(cipher.key["c"]) == {1}
			assert set(cipher.key["a"]) == {2}
			assert set(cipher.key["b"]) == {3}

		def test_complex_overlap_integrity(self, sample_stream_short):
			"""
			Test a complex sequence to ensure no 'collisions' occur during remapping
			where a new ID accidentally overwrites an unmapped old ID.
			"""
			cipher = HomophonicCipher(sample_stream_short)
			# Setup: Numbers that might overlap with the 1..N range
			cipher.key = {"a": [3], "b": [2], "c": [1]}
			# Ciphertext where they appear in reverse order
			cipher.ciphertext = "3 2 1 2 1"

			cipher._apply_recurrence_and_remap_key()

			# If mapping is done correctly: 3->1, 2->2, 1->3
			assert cipher.ciphertext == "1 2 3 2 3"
			assert cipher.key["a"] == [1]
			assert cipher.key["b"] == [2]
			assert cipher.key["c"] == [3]


# --- MonoalphabeticCipher Tests ---


class TestMonoalphabeticCipher:
	def test_legal_plaintext(self, valid_text_stream):
		cipher = MonoalphabeticCipher(valid_text_stream)

		assert cipher.plaintext == valid_text_stream["text"]
		assert cipher.source_id == valid_text_stream["source_id"]
		assert cipher.source_name == valid_text_stream["source_name"]

		assert isinstance(cipher.key, dict)
		assert all(isinstance(v, list) and len(v) == 1 for v in cipher.key.values())
		assert isinstance(cipher.ciphertext, str)
		assert all(num.isdigit() for num in cipher.ciphertext.split())

		assert cipher.plaintext_with_boundaries == valid_text_stream["text_with_boundaries"]
		assert isinstance(cipher.ciphertext_with_boundaries, str)
		assert len(cipher.ciphertext_with_boundaries) >= len(cipher.ciphertext)

	def test_key_structure(self, sample_stream_short):
		cipher = MonoalphabeticCipher(sample_stream_short)

		assert len(cipher.key) == 3
		for letter in cipher.plaintext:
			assert letter in cipher.key
			assert len(cipher.key[letter]) >= 1

		all_numbers = [cipher.key[letter][0] for letter in cipher.plaintext]
		assert set(all_numbers) == set(range(1, 4))
		assert len(set(all_numbers)) == 3

	def test_ciphertext_length(self, valid_text_stream):
		cipher = MonoalphabeticCipher(valid_text_stream)
		ciphertext_numbers = cipher.ciphertext.split()
		assert len(ciphertext_numbers) == len(valid_text_stream["text"])

	def test_json_serialization_success(self, valid_text_stream):
		"""
		FIX: This previously expected failure. Now that MonoalphabeticCipher
		sets source_id/name, serialization should SUCCEED.
		"""
		cipher = MonoalphabeticCipher(valid_text_stream)
		json_data = cipher.__json__()

		assert isinstance(json_data, dict)
		assert json_data["plaintext"] == valid_text_stream["text"]
		assert (
			json_data["plaintext_with_boundaries"]
			== valid_text_stream["text_with_boundaries"]
		)
		assert (
			json_data["ciphertext_with_boundaries"] == cipher.ciphertext_with_boundaries
		)
		assert json_data["source_id"] == valid_text_stream["source_id"]
		assert json_data["source_name"] == valid_text_stream["source_name"]
		assert json_data["key"] == cipher.key
		assert json_data["ciphertext"] == cipher.ciphertext

	def test_str_representation(self, valid_text_stream):
		cipher = MonoalphabeticCipher(valid_text_stream)
		str_repr = str(cipher)
		assert 'MonoalphabeticCipher(Plaintext: "' in str_repr
		assert f'"{valid_text_stream["text"]}"' in str_repr
		assert f"Key: {cipher.key}" in str_repr
		assert f'Ciphertext: "{cipher.ciphertext}"' in str_repr

	@pytest.mark.parametrize("case", BAD_STREAM_CASES, ids=lambda c: c.desc)
	def test_invalid_stream_initialization(self, case: BadStreamTestCase):
		"""Test that invalid stream parameters raise the specific expected exceptions."""
		with pytest.raises(case.expected_exception, match=case.match):
			MonoalphabeticCipher(case.stream) # type: ignore
