import pytest

from main import generate_cipher, generate_monoalphabetic_cipher
from utils.formatting import format_text


@pytest.fixture
def book_text():
	"""
	Return a string of roughly 5,500 characters to simulate a book text.
	Multiplying the base text by 7 easily clears the 5000 character minimum
	without needlessly processing an 80,000 character string.
	"""
	return (
		"Once upon a time, in a land far, far away, there lived a wise old owl. The owl had seen many things in its long "
		"life and was known throughout the land for its wisdom. Every evening, animals from all over the forest would "
		"gather around the owl's tree to hear its stories and seek advice. One day, a young rabbit approached the owl with "
		"a problem. The rabbit was afraid of the dark and could not sleep at night. The owl listened carefully and then "
		"shared a story about bravery and facing one's fears. The rabbit felt comforted and thanked the owl for its wisdom. "
		"From that day on, the rabbit no longer feared the dark and would often visit the owl to learn more about the world. "
		"The owl continued to share its wisdom, and the forest became a place of harmony and understanding. "
	) * 10


@pytest.fixture(autouse=True)
def mock_save_book(mocker):
	mocker.patch("utils.files.save_book")


def test_generate_cipher(mocker, book_text):
	"""Test with a specific length."""
	mocker.patch(
		"text_fetching.fetcher.Fetcher.fetch_random_book_text",
		return_value="".join(format_text(book_text)),
	)

	"""Mock built-in open to intercept the disk write."""
	mock_file = mocker.patch("builtins.open", mocker.mock_open())

	generate_cipher(1000, 5000, "test_cipher.json", difficulty=10)

	"""Ensure the function executed the write command with data."""
	assert mock_file().write.called


def test_generate_cipher_fails_cipher(mocker, book_text):
	"""Test with a specific length."""
	mocker.patch(
		"text_fetching.fetcher.Fetcher.fetch_random_book_text",
		return_value="".join(book_text),
	)

	with pytest.raises(ValueError) as excinfo:
		generate_cipher(1000, 5000, "test_cipher.json", 10)

	assert "Plaintext must be a lowercase alphabetic string with no spaces" in str(
		excinfo.value
	)


def test_generate_monoalphabetic_cipher(mocker, book_text):
	"""Test with a specific length."""
	mocker.patch(
		"text_fetching.fetcher.Fetcher.fetch_random_book_text",
		return_value="".join(format_text(book_text)),
	)

	"""Mock built-in open to intercept the disk write."""
	mock_file = mocker.patch("builtins.open", mocker.mock_open())

	generate_monoalphabetic_cipher(1000, 5000, "test_mono_cipher.json")

	"""Ensure the function executed the write command with data."""
	assert mock_file().write.called


def test_generate_monoalphabetic_cipher_fails(mocker, book_text):
	"""Test with a specific length."""
	mocker.patch(
		"text_fetching.fetcher.Fetcher.fetch_random_book_text",
		return_value="".join(book_text),
	)

	with pytest.raises(ValueError) as excinfo:
		generate_monoalphabetic_cipher(1000, 5000, "test_mono_cipher.json")

	assert "Plaintext must be a lowercase alphabetic string with no spaces" in str(
		excinfo.value
	)
