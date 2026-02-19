import pytest
from encipherment.cipher import HomophonicCipher, MonoalphabeticCipher
from utils.constants import MIN_DIFFICULTY, MAX_DIFFICULTY

# --- Fixtures ---


@pytest.fixture(scope="module")
def sample_text_content():
	return (
		"thisisatestplaintextthatneedstobeencrypteditisjustarandomstringoflowercaselettersthatshouldworkfineanditislong"
		"enoughtotestthecipherwiththelengthshouldbeoverfourhundredcharactersmaybeevenfivehundredduetothistweneedtoensure"
		"thecipherworksasexpectedandcanhandlelargerinputswithoutanyissuesandthatthistextisextremelylongsoitcanbeusedtotest"
		"theperformanceoftheciphergenerationprocess"
	)


@pytest.fixture(scope="module")
def sample_stream_legal(sample_text_content):
	"""Returns a valid TextStream dictionary for HomophonicCipher."""
	return {
		"text": sample_text_content,
		"source_id": "book_123",
		"source_name": "Test Book",
		"length": len(sample_text_content),
	}


@pytest.fixture(scope="module")
def sample_text_short():
	return "abcdefghijklmnopqrstuvwxyz"


@pytest.fixture(scope="module")
def sample_stream_short(sample_text_short):
	"""Returns a short valid TextStream dictionary."""
	return {
		"text": sample_text_short,
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
	"""Returns a valid TextStream dictionary for HomophonicCipher."""
	return [
		{
			"text": text,
			"source_id": "book_123",
			"source_name": "Test Book",
			"length": len(text),
		}
		for text in sample_texts_illegal
	]

# --- HomophonicCipher Tests ---


class TestHomophonicCipher:
	def test_legal_plaintext(self, sample_stream_legal):
		# Pass the stream object (dict), not just the string
		cipher = HomophonicCipher(sample_stream_legal)
		cipher.generate_key()
		cipher.encipher()

		assert cipher.plaintext == sample_stream_legal["text"]
		assert cipher.source_id == sample_stream_legal["source_id"]
		assert cipher.source_name == sample_stream_legal["source_name"]

		assert MIN_DIFFICULTY <= cipher.difficulty <= MAX_DIFFICULTY
		assert isinstance(cipher.key, dict)
		assert all(isinstance(v, list) for v in cipher.key.values())
		assert isinstance(cipher.ciphertext, str)
		assert all(num.isdigit() for num in cipher.ciphertext.split())

	def test_all_homophones_used(self, sample_stream_legal):
		cipher = HomophonicCipher(sample_stream_legal)
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

	def test_defined_difficulty(self, sample_stream_legal):
		for difficulty in range(4, 11):
			cipher = HomophonicCipher(sample_stream_legal, difficulty=difficulty)
			assert cipher.difficulty == difficulty

	def test_key_homophones_count(self, sample_stream_legal):
		cipher = HomophonicCipher(sample_stream_legal)
		cipher.generate_key()
		total_homophones = sum(len(v) for v in cipher.key.values())
		expected_homophones = round(
			len(sample_stream_legal["text"]) / cipher.difficulty
		)

		unique_letters = len(set(sample_stream_legal["text"]))

		assert total_homophones >= unique_letters, (
			f"Total homophones {total_homophones} is less than unique letters {unique_letters}"
		)

		expected_range = max(15, expected_homophones)
		assert abs(total_homophones - expected_homophones) <= expected_range, (
			f"Total homophones {total_homophones} not within acceptable range."
		)

	def test_ciphertext_numbers_within_range(self, sample_stream_legal):
		cipher = HomophonicCipher(sample_stream_legal)
		ciphertext_numbers = list(map(int, cipher.ciphertext.split()))
		total_homophones = sum(len(v) for v in cipher.key.values())
		assert all(1 <= num <= total_homophones for num in ciphertext_numbers)

	def test_ciphertext_length(self, sample_stream_legal):
		cipher = HomophonicCipher(sample_stream_legal)
		cipher.generate_key()
		cipher.encipher()
		ciphertext_numbers = cipher.ciphertext.split()
		assert len(ciphertext_numbers) == len(sample_stream_legal["text"])

	def test_json_serialization(self, sample_stream_legal):
		cipher = HomophonicCipher(sample_stream_legal)
		json_data = cipher.__json__()
		assert isinstance(json_data, dict)
		assert json_data["plaintext"] == sample_stream_legal["text"]
		assert json_data["source_id"] == sample_stream_legal["source_id"]
		assert json_data["source_name"] == sample_stream_legal["source_name"]
		assert json_data["difficulty"] == cipher.difficulty
		assert json_data["key"] == cipher.key
		assert json_data["ciphertext"] == cipher.ciphertext

	def test_str_representation(self, sample_stream_legal):
		cipher = HomophonicCipher(sample_stream_legal)
		str_repr = str(cipher)
		assert 'HomophonicCipher(Plaintext: "' in str_repr
		assert f'"{sample_stream_legal["text"]}"' in str_repr
		assert f"Difficulty: {cipher.difficulty}" in str_repr
		assert f"Key: {cipher.key}" in str_repr
		assert f'Ciphertext: "{cipher.ciphertext}"' in str_repr
		assert f'Recurrence Encoding: "{cipher.recurrence_encoding}"' in str_repr  # type: ignore

	def test_invalid_difficulty(self, sample_stream_legal):
		for invalid_difficulty in [3, 31, -1, 0]:
			with pytest.raises(ValueError) as excinfo:
				HomophonicCipher(sample_stream_legal, difficulty=invalid_difficulty)
			assert (
				f"Parameter `difficulty` must be between {MIN_DIFFICULTY} and {MAX_DIFFICULTY}."
				in str(excinfo.value)
			)

	def test_non_integer_difficulty(self, sample_stream_legal):
		for non_integer in [5.5, "ten"]:
			with pytest.raises(TypeError) as excinfo:
				HomophonicCipher(sample_stream_legal, difficulty=non_integer)
			assert "Parameter `difficulty` must be of type int, or None." in str(
				excinfo.value
			)

	def test_non_stream_plaintext(self):
		# The validator expects text_obj to be the first arg, validation might fail
		# inside __init__ when accessing ["text"] if input is not subscriptable
		for invalid_input in [12345, None, 5.67]:
			with pytest.raises(TypeError):
				HomophonicCipher(invalid_input)

	def test_empty_string_plaintext_in_stream(self):
		bad_stream = {"text": " ", "source_id": "1", "source_name": "test", "length": 1}
		with pytest.raises(ValueError) as excinfo:
			HomophonicCipher(bad_stream)  # type: ignore
		assert (
			"must include a non-empty, lowercase alphabetic string with no spaces in the text field."
			in str(excinfo.value)
		)

	def test_recurrence_encoding(self, sample_stream_legal):
		cipher = HomophonicCipher(sample_stream_legal)
		cipher.generate_key()
		cipher.encipher()
		encoding = cipher.recurrence_encoding
		assert isinstance(encoding, str)
		assert len(encoding.split()) == len(sample_stream_legal["text"])

		encoding_numbers = list(map(int, encoding.split()))
		assert all(num >= 1 for num in encoding_numbers)
		assert set(encoding_numbers) == set(range(1, max(encoding_numbers) + 1))


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

    def test_randomization(self, sample_stream_short):
        cipher1 = MonoalphabeticCipher(sample_stream_short)
        cipher2 = MonoalphabeticCipher(sample_stream_short)

        key1_numbers = [cipher1.key[letter][0] for letter in "abcde"]
        key2_numbers = [cipher2.key[letter][0] for letter in "abcde"]

        assert key1_numbers != key2_numbers, "Keys should be randomized"

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

    def test_illegal_plaintext(self, sample_texts_illegal):
        for text in sample_texts_illegal:
            # FIX: Wrap illegal text in a TextStream dict structure
            bad_stream = {
                "text": text,
                "source_id": "1",
                "source_name": "test",
                "length": len(text)
            }

            with pytest.raises(ValueError) as excinfo:
                MonoalphabeticCipher(bad_stream) # type: ignore

            # Use the error message from validate_text_obj
            assert (
                "must include a non-empty, lowercase alphabetic string with no spaces"
                in str(excinfo.value)
            )

    def test_non_dict_input(self):
        # FIX: The validator now checks if input is a dict/TextStream
        for invalid_input in [12345, None, 5.67, "just a string"]:
            with pytest.raises(TypeError):
                MonoalphabeticCipher(invalid_input) # type: ignore

    def test_empty_string_plaintext(self):
        bad_stream = {
            "text": "",
            "source_id": "1",
            "source_name": "test",
            "length": 0
        }
        with pytest.raises(ValueError) as excinfo:
            MonoalphabeticCipher(bad_stream) # type: ignore
        assert (
            "must include a non-empty, lowercase alphabetic string"
            in str(excinfo.value)
        )
