import pytest
from utils.cipher_conversion import CipherConverter
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

@pytest.fixture
def mono_data(
    sample_monoalphabetic_plaintext,
    sample_monoalphabetic_ciphertext,
    sample_monoalphabetic_mappings
):
    """Bundles monoalphabetic test data to reduce argument count."""
    return {
        "pt": sample_monoalphabetic_plaintext,
        "ct": sample_monoalphabetic_ciphertext,
        "map": sample_monoalphabetic_mappings
    }


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

    def test_convert(self, mocker, sample_plaintext, sample_ciphertext, sample_mappings):
        # MOCK: Patch the cipher class used inside CipherConverter.
        # We assume CipherConverter imports it as: from encipherment.cipher import HomophonicCipher
        # So we patch it where it is USED: utils.cipher_conversion.HomophonicCipher
        mock_homophonic_cls = mocker.patch("utils.cipher_conversion.HomophonicCipher")
        mock_cipher_instance = mock_homophonic_cls.return_value

        # Setup the mock instance to behave like a cipher
        mock_cipher_instance.plaintext = sample_plaintext
        mock_cipher_instance.ciphertext = sample_ciphertext
        mock_cipher_instance.key = sample_mappings
        mock_cipher_instance.recurrence_encoding = "1 2 3"
        mock_cipher_instance.difficulty = 4

        converter = CipherConverter(
            plaintext=sample_plaintext,
            ciphertext=sample_ciphertext,
            mappings=sample_mappings,
        )

        cipher = converter.convert_to_cipher()

        # Verify the converter initialized the class correctly
        mock_homophonic_cls.assert_called_once()
        # Note: The provided CipherConverter passes (self.plaintext, difficulty=4)
        assert mock_homophonic_cls.call_args[0][0]["text"] == sample_plaintext

        assert cipher.plaintext == sample_plaintext
        assert cipher.ciphertext == sample_ciphertext
        assert cipher.key == converter.mappings

    def test_convert_is_idempotent(
        self, mocker, sample_plaintext, sample_ciphertext, sample_mappings
    ):
        mocker.patch("utils.cipher_conversion.HomophonicCipher")

        converter = CipherConverter(
            plaintext=sample_plaintext,
            ciphertext=sample_ciphertext,
            mappings=sample_mappings,
        )
        cipher1 = converter.convert_to_cipher()
        cipher2 = converter.convert_to_cipher()
        assert cipher1 is cipher2

    def test_init_with_z408_data(self, mocker):
        mocker.patch("utils.cipher_conversion.HomophonicCipher")

        converter = CipherConverter(
            plaintext=plaintext_str, ciphertext=cipher_str, mappings=key_formatted
        )
        cipher = converter.convert_to_cipher()

        # We verify attributes on the mock, or just the converter state
        # Since we mocked the class, we rely on the converter setting attributes on the mock
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

        # The new code raises ValueError with a tuple of arguments.
        # str(excinfo.value) will look like: "('Symbol \'4\' not found in mappings.', ...)"
        assert "Symbol '4' not found in mappings." in str(excinfo.value)

    def test_from_ciphertext_and_mappings_ambiguous_mapping(self):
        with pytest.raises(ValueError) as excinfo:
            CipherConverter.from_ciphertext_and_mappings(
                ciphertext="1 2 3",
                mappings={"a": ["1"], "b": ["2"], "c": ["3"], "d": ["1"]},
            )
        assert "Invalid mappings provided" in str(excinfo.value)
        assert "Ambiguous mapping: Symbol '1' maps to multiple characters" in str(excinfo.value)

    def test_from_ciphertext_and_mappings_z408_no_ambiguity(self):
        new_key = copy.deepcopy(key_formatted)

        new_key["s"].remove("▲")
        new_key["s"].append("Æ")

        new_cipher_str_list = cipher_str.split()
        for i in range(len(plaintext_str)):
            if plaintext_str[i] == "s" and cipher_str.split()[i] == "▲":
                new_cipher_str_list[i] = "Æ"

        new_cipher_str = " ".join(new_cipher_str_list)

        converter = CipherConverter.from_ciphertext_and_mappings(
            ciphertext=new_cipher_str, mappings=new_key
        )
        assert converter.ciphertext == new_cipher_str
        assert converter.mappings == new_key
        # Check plaintext length to ensure full conversion
        assert len(converter.plaintext) == len(plaintext_str)

    def test_from_plaintext_and_ciphertext_z408(self):
        converter = CipherConverter.from_plaintext_and_ciphertext(
            ciphertext=cipher_str, plaintext=plaintext_str
        )
        assert converter.plaintext == plaintext_str
        assert converter.ciphertext == cipher_str
        # Verify keys match (order might differ so we check sets)
        assert set(converter.mappings.keys()) == set(key_formatted.keys())

    def test_from_plaintext_and_ciphertext_monoalphabetic(
        self,
        mocker,
        sample_monoalphabetic_ciphertext,
        sample_monoalphabetic_plaintext,
    ):
        mock_mono = mocker.patch("utils.cipher_conversion.MonoalphabeticCipher")

        converter = CipherConverter.from_plaintext_and_ciphertext(
            plaintext=sample_monoalphabetic_plaintext,
            ciphertext=sample_monoalphabetic_ciphertext,
        )
        assert converter.plaintext == sample_monoalphabetic_plaintext
        assert converter.ciphertext == sample_monoalphabetic_ciphertext

        # Check that it detects monoalphabetic correctly
        assert not converter._is_homophonic()

        # Check conversion uses MonoalphabeticCipher
        converter.convert_to_cipher()
        mock_mono.assert_called_once()

    @pytest.mark.parametrize(
        "construction_method",
        [
            "from_init",
            "from_factory"
        ],
    )
    def test_monoalphabetic_construction(
        self,
        mocker,
        construction_method,
        mono_data
    ):
        # Patch BOTH to be safe, though we expect Monoalphabetic to be used
        mock_mono = mocker.patch("utils.cipher_conversion.MonoalphabeticCipher")
        mocker.patch("utils.cipher_conversion.HomophonicCipher")

        if construction_method == "from_init":
            converter = CipherConverter(
                plaintext=mono_data["pt"],
                ciphertext=mono_data["ct"],
                mappings=mono_data["map"],
            )
        elif construction_method == "from_factory":
            converter = CipherConverter.from_ciphertext_and_mappings(
                ciphertext=mono_data["ct"],
                mappings=mono_data["map"],
            )
        else:
            pytest.fail(f"Unknown construction_method: {construction_method}")

        expected = {
			"plaintext": mono_data["pt"],
			"ciphertext": mono_data["ct"],
			"mappings": mono_data["map"],
		}

        self._assert_monoalphabetic_converter_state(
            converter,
            expected,
            mock_mono
        )

    def _assert_monoalphabetic_converter_state(
        self,
        converter: CipherConverter,
        expected: dict,
        mock_mono_cls
    ):
        assert converter.plaintext == expected["plaintext"]
        assert converter.ciphertext == expected["ciphertext"]
        assert converter.mappings == expected["mappings"]

        assert not converter._is_homophonic()

        cipher = converter.convert_to_cipher()

        # Verify MonoalphabeticCipher was instantiated
        mock_mono_cls.assert_called()
        # And that the returned object is the mock's return value
        assert cipher == mock_mono_cls.return_value
