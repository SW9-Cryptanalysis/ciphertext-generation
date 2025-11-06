import pytest
from utils.cipher_conversion import CipherConverter
from encipherment.cipher import HomophonicCipher, MonoalphabeticCipher
import copy
from utils.z408 import plaintext_str, cipher_str, key_formatted


@pytest.fixture
def sample_plaintext():
	return "ilikekillingpeople"


@pytest.fixture
def sample_ciphertext():
	return "1 2 1 3 4 3 1 2 2 1 5 6 7 4 8 7 2 4"


@pytest.fixture
def sample_mappings():
	return {
		"i": ["1"],
		"l": ["2"],
		"k": ["3"],
		"e": ["S", "\u03b2", "4"],
		"n": ["5"],
		"g": ["6"],
		"p": ["7"],
		"o": ["8"],
	}


@pytest.fixture
def sample_monoalphabetic_mappings():
	return {
		"i": ["1"],
		"l": ["2"],
		"k": ["3"],
		"e": ["4"],
		"n": ["5"],
		"g": ["6"],
		"p": ["7"],
		"o": ["8"],
	}


@pytest.fixture
def sample_monoalphabetic_plaintext():
	return "ilikekillingpeople"


@pytest.fixture
def sample_monoalphabetic_ciphertext():
	return "1 2 1 3 4 3 1 2 2 1 5 6 7 4 8 7 2 4"


class TestCipherConverter:
	def test_init_with_all_inputs(
		self, sample_plaintext, sample_ciphertext, sample_mappings
	):
		converter = CipherConverter(
			plaintext=sample_plaintext,
			ciphertext=sample_ciphertext,
			mappings=sample_mappings,
		)
		assert converter.plaintext == sample_plaintext
		assert converter.ciphertext == sample_ciphertext
		assert converter.mappings == sample_mappings

	def test_convert(self, sample_plaintext, sample_ciphertext, sample_mappings):
		converter = CipherConverter(
			plaintext=sample_plaintext,
			ciphertext=sample_ciphertext,
			mappings=sample_mappings,
		)
		cipher = converter.convert_to_cipher()

		assert isinstance(cipher, HomophonicCipher)
		assert cipher.plaintext == sample_plaintext
		assert cipher.ciphertext == sample_ciphertext
		assert cipher.key == converter.mappings
		assert cipher.difficulty == 4
		assert (
			cipher.recurrence_encoding is not None and cipher.recurrence_encoding != ""
		)

	def test_convert_is_idempotent(
		self, sample_plaintext, sample_ciphertext, sample_mappings
	):
		converter = CipherConverter(
			plaintext=sample_plaintext,
			ciphertext=sample_ciphertext,
			mappings=sample_mappings,
		)
		cipher1 = converter.convert_to_cipher()
		cipher2 = converter.convert_to_cipher()
		assert cipher1 is cipher2

	def test_init_with_z408_data(self):
		converter = CipherConverter(
			plaintext=plaintext_str, ciphertext=cipher_str, mappings=key_formatted
		)
		cipher = converter.convert_to_cipher()
		assert isinstance(cipher, HomophonicCipher)
		assert cipher.plaintext == plaintext_str
		assert cipher.ciphertext == cipher_str
		assert cipher.key == key_formatted

	def test_from_plaintext_and_ciphertext(self):
		converter = CipherConverter.from_plaintext_and_ciphertext(
			plaintext="abc", ciphertext="1 2 3"
		)

		assert converter.plaintext == "abc"
		assert converter.ciphertext == "1 2 3"
		assert converter.mappings == {"a": ["1"], "b": ["2"], "c": ["3"]}

	def test_from_plaintext_and_ciphertext_invalid_length(self):
		with pytest.raises(ValueError) as excinfo:
			CipherConverter.from_plaintext_and_ciphertext(
				plaintext="abc", ciphertext="1 2"
			)
		assert (
			"Plaintext length (3) and number of ciphertext symbols (2) do not match."
			in str(excinfo.value)
		)

	def test_from_ciphertext_and_mappings(self):
		converter = CipherConverter.from_ciphertext_and_mappings(
			ciphertext="1 2 3", mappings={"a": ["1"], "b": ["2"], "c": ["3"]}
		)

		assert converter.plaintext == "abc"
		assert converter.ciphertext == "1 2 3"
		assert converter.mappings == {"a": ["1"], "b": ["2"], "c": ["3"]}

	def test_from_ciphertext_and_mappings_invalid_symbol(self):
		with pytest.raises(ValueError) as excinfo:
			CipherConverter.from_ciphertext_and_mappings(
				ciphertext="1 2 3 4",
				mappings={"a": ["1"], "b": ["2"], "c": ["3"], "d": ["5"]},
			)
		assert "Symbol '4' not found in mappings." in str(excinfo.value)

	def test_from_ciphertext_and_mappings_ambiguous_mapping(self):
		with pytest.raises(ValueError) as excinfo:
			CipherConverter.from_ciphertext_and_mappings(
				ciphertext="1 2 3",
				mappings={"a": ["1"], "b": ["2"], "c": ["3"], "d": ["1"]},
			)
		assert (
			"Invalid mappings provided: Ambiguous mapping: Symbol '1' maps to multiple characters"
			in str(excinfo.value)
		)

	def test_from_ciphertext_and_mappings_z408_no_ambiguity(self):
		new_key = copy.deepcopy(key_formatted)

		new_key["s"].remove("▲")
		new_key["s"].append("Æ")

		new_cipher_str = cipher_str.split()
		for i in range(len(plaintext_str)):
			if plaintext_str[i] == "s" and cipher_str[i] == "▲":
				new_cipher_str[i] = "Æ"

		new_cipher_str = " ".join(new_cipher_str)

		assert len(new_cipher_str.split()) == len(cipher_str.split())
		assert len(plaintext_str) == len(new_cipher_str.split())

		converter = CipherConverter.from_ciphertext_and_mappings(
			ciphertext=new_cipher_str, mappings=new_key
		)
		# assert len(converter.plaintext) == len(plaintext_str)
		# assert converter.plaintext == plaintext_str
		assert converter.ciphertext == new_cipher_str
		assert converter.mappings == new_key

	def test_from_ciphertext_and_mappings_z408_ambiguity(self):
		with pytest.raises(ValueError) as excinfo:
			CipherConverter.from_ciphertext_and_mappings(
				ciphertext=cipher_str, mappings=key_formatted
			)
		assert (
			"Invalid mappings provided: Ambiguous mapping: Symbol '▲' maps to multiple characters"
			in str(excinfo.value)
		)

	def test_from_plaintext_and_ciphertext_z408(self):
		converter = CipherConverter.from_plaintext_and_ciphertext(
			ciphertext=cipher_str, plaintext=plaintext_str
		)
		assert converter.plaintext == plaintext_str
		assert converter.ciphertext == cipher_str
		assert set(converter.mappings) == set(key_formatted)

	def test_from_plaintext_and_ciphertext_monoalphabetic(
		self,
		sample_monoalphabetic_ciphertext,
		sample_monoalphabetic_plaintext,
	):
		converter = CipherConverter.from_plaintext_and_ciphertext(
			plaintext=sample_monoalphabetic_plaintext,
			ciphertext=sample_monoalphabetic_ciphertext,
		)
		assert converter.plaintext == sample_monoalphabetic_plaintext
		assert converter.ciphertext == sample_monoalphabetic_ciphertext
		assert converter.mappings == {
			"i": ["1"],
			"l": ["2"],
			"k": ["3"],
			"e": ["4"],
			"n": ["5"],
			"g": ["6"],
			"p": ["7"],
			"o": ["8"],
		}
		assert not converter._is_homophonic()
		assert isinstance(converter.convert_to_cipher(), MonoalphabeticCipher)

	@pytest.mark.parametrize(
		"construction_method",
		[
			"from_init",         # Test the __init__ constructor
			"from_factory"       # Test the classmethod factory
		],
	)
	def test_monoalphabetic_construction(
		self,
		construction_method,  # This parameter comes from @pytest.mark.parametrize
		sample_monoalphabetic_plaintext,
		sample_monoalphabetic_ciphertext,
		sample_monoalphabetic_mappings,
	):
		if construction_method == "from_init":
			converter = CipherConverter(
				plaintext=sample_monoalphabetic_plaintext,
				ciphertext=sample_monoalphabetic_ciphertext,
				mappings=sample_monoalphabetic_mappings,
			)
		elif construction_method == "from_factory":
			converter = CipherConverter.from_ciphertext_and_mappings(
				ciphertext=sample_monoalphabetic_ciphertext,
				mappings=sample_monoalphabetic_mappings,
			)
		else:
			pytest.fail(f"Unknown construction_method: {construction_method}")

		self._assert_monoalphabetic_converter_state(
			converter,
			sample_monoalphabetic_plaintext,
			sample_monoalphabetic_ciphertext,
			sample_monoalphabetic_mappings,
		)

	def _assert_monoalphabetic_converter_state(
		self,
		converter: CipherConverter,
		expected_plaintext: str,
		expected_ciphertext: str,
		expected_mappings: dict,
	):
		assert converter.plaintext == expected_plaintext
		assert converter.ciphertext == expected_ciphertext
		assert converter.mappings == expected_mappings

		# Note: Testing private methods like _is_homophonic() is
		# generally discouraged, but we'll keep it as it was in your original code.
		assert not converter._is_homophonic()
		assert isinstance(converter.convert_to_cipher(), MonoalphabeticCipher)
