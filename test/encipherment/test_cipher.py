import pytest

from encipherment.cipher import Cipher
from utils.constants import MIN_DIFFICULTY, MAX_DIFFICULTY


@pytest.fixture
def sample_text_legal():
    return (
        "thisisatestplaintextthatneedstobeencrypteditisjustarandomstringoflowercaselettersthatshouldworkfineanditislong"
        "enoughtotestthecipherwiththelengthshouldbeoverfourhundredcharactersmaybeevenfivehundredduetothistweneedtoensure"
        "thecipherworksasexpectedandcanhandlelargerinputswithoutanyissuesandthatthistextisextremelylongsoitcanbeusedtotest"
        "theperformanceoftheciphergenerationprocess"
    )


@pytest.fixture
def sample_texts_illegal():
    return [
        "ThisTextHasUppercaseLettersAnd12345Numbers!@#",
        "This text has spaces",
        "this-text-has-dashes",
        "this.text.has.punctuation!",
    ]


def test_legal_plaintext(sample_text_legal):
    cipher = Cipher(sample_text_legal)
    assert cipher.plaintext == sample_text_legal
    assert MIN_DIFFICULTY <= cipher.difficulty <= MAX_DIFFICULTY
    assert isinstance(cipher.key, dict)
    assert all(isinstance(v, list) for v in cipher.key.values())
    assert isinstance(cipher.ciphertext, str)
    assert all(num.isdigit() for num in cipher.ciphertext.split())


def test_all_homophones_used(sample_text_legal):
    cipher = Cipher(sample_text_legal)
    used_homophones = set(int(num) for num in cipher.ciphertext.split())
    all_homophones = set()
    for homophones in cipher.key.values():
        all_homophones.update(homophones)
    assert used_homophones == all_homophones, (
        f"Used homophones {used_homophones} do not match all homophones {all_homophones}"
    )


def test_illegal_plaintext(sample_texts_illegal):
    for text in sample_texts_illegal:
        with pytest.raises(ValueError) as excinfo:
            Cipher(text)
        assert (
            "Plaintext must contain only lowercase letters with no punctuation or spaces."
            in str(excinfo.value)
        )


def test_defined_difficulty(sample_text_legal):
    for difficulty in range(4, 11):
        cipher = Cipher(sample_text_legal, difficulty=difficulty)
        assert cipher.difficulty == difficulty


def test_key_homophones_count(sample_text_legal):
    cipher = Cipher(sample_text_legal)
    total_homophones = sum(len(v) for v in cipher.key.values())
    expected_homophones = round(len(sample_text_legal) / cipher.difficulty)

    # Assert that the total number of homophones is within a reasonable range of the expected value
    assert abs(total_homophones - expected_homophones) <= 10, (
        f"Total homophones {total_homophones} not within acceptable range of expected {expected_homophones}"
    )
    assert total_homophones >= expected_homophones, (
        f"Total homophones {total_homophones} is less than expected {expected_homophones}"
    )


def test_ciphertext_numbers_within_range(sample_text_legal):
    cipher = Cipher(sample_text_legal)
    ciphertext_numbers = list(map(int, cipher.ciphertext.split()))
    total_homophones = sum(len(v) for v in cipher.key.values())
    assert all(1 <= num <= total_homophones for num in ciphertext_numbers)


def test_ciphertext_length(sample_text_legal):
    cipher = Cipher(sample_text_legal)
    ciphertext_numbers = cipher.ciphertext.split()
    assert len(ciphertext_numbers) == len(sample_text_legal)


def test_json_serialization(sample_text_legal):
    cipher = Cipher(sample_text_legal)
    json_data = cipher.__json__()
    assert isinstance(json_data, dict)
    assert json_data["plaintext"] == sample_text_legal
    assert json_data["difficulty"] == cipher.difficulty
    assert json_data["key"] == cipher.key
    assert json_data["ciphertext"] == cipher.ciphertext


def test_str_representation(sample_text_legal):
    cipher = Cipher(sample_text_legal)
    str_repr = str(cipher)
    assert 'Cipher(Plaintext: "' in str_repr
    assert f'"{sample_text_legal}"' in str_repr
    assert f"Difficulty: {cipher.difficulty}" in str_repr
    assert f"Key: {cipher.key}" in str_repr
    assert f'Ciphertext: "{cipher.ciphertext}"' in str_repr


def test_invalid_difficulty(sample_text_legal):
    for invalid_difficulty in [3, 21, -1, 0]:
        with pytest.raises(ValueError) as excinfo:
            Cipher(sample_text_legal, difficulty=invalid_difficulty)
        assert "Difficulty must be between 4 and 20." in str(excinfo.value), (
            f"Failed for difficulty {invalid_difficulty}"
        )


def test_non_integer_difficulty(sample_text_legal):
    for non_integer in [5.5, "ten"]:
        with pytest.raises(ValueError) as excinfo:
            Cipher(sample_text_legal, difficulty=non_integer)
        assert "Difficulty must be an integer." in str(excinfo.value)


def test_non_string_plaintext():
    for non_string in [12345, None, 5.67, ["list"], {"dict": "value"}]:
        with pytest.raises(ValueError) as excinfo:
            Cipher(non_string)
        assert "Plaintext must be a string." in str(excinfo.value)


def test_empty_string_plaintext():
    with pytest.raises(ValueError) as excinfo:
        Cipher("")
    assert "Plaintext must be a non-empty string." in str(excinfo.value)


def test_plaintext_with_non_english_letters():
    for text in [
        "thisisatestplaintextwithé",
        "thisisatestplaintextwithñ",
        "thisisatestplaintextwithü",
    ]:
        with pytest.raises(ValueError) as excinfo:
            Cipher(text)
        assert (
            "Plaintext must contain only lowercase letters with no punctuation or spaces."
            in str(excinfo.value)
        )
