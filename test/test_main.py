import pytest

from main import generate_cipher
from utils.formatting import format_text


@pytest.fixture
def book_text():
	# Return a very long string to simulate book text (at least 5000 characters)
	return (
		"""
		Once upon a time, in a land far, far away, there lived a wise old owl. The owl had seen many things in its long
		life and was known throughout the land for its wisdom. Every evening, animals from all over the forest would
		gather around the owl's tree to hear its stories and seek advice. One day, a young rabbit approached the owl with
		a problem. The rabbit was afraid of the dark and could not sleep at night. The owl listened carefully and then
		shared a story about bravery and facing one's fears. The rabbit felt comforted and thanked the owl for its wisdom.
		From that day on, the rabbit no longer feared the dark and would often visit the owl to learn more about the world.
		The owl continued to share its wisdom, and the forest became a place of harmony and understanding.
		"""
		* 100
	)  # Repeat to ensure it's long enough


@pytest.fixture(autouse=True)
def mock_save_book(mocker):
	mocker.patch("utils.files.save_book")


def test_generate_cipher(mocker, book_text):
	# Test with a specific length
	mocker = mocker.patch(
		"text_fetching.fetcher.Fetcher.fetch_random_book_text",
		return_value="".join(format_text(book_text)),
	)

	generate_cipher(1000, 5000, "test_cipher.json")
	with open("ciphers/test_cipher.json", encoding="utf-8") as f:
		data = f.read()
		assert len(data) > 0  # Ensure the file is not empty

	# Clean up
	import os

	if os.path.exists("ciphers/test_cipher.json"):
		os.remove("ciphers/test_cipher.json")


def test_generate_cipher_fails_cipher(mocker, book_text):
	# Test with a specific length
	mocker = mocker.patch(
		"text_fetching.fetcher.Fetcher.fetch_random_book_text",
		return_value="".join(book_text),
	)

	with pytest.raises(ValueError) as excinfo:
		generate_cipher(1000, 5000, "test_cipher.json")
	assert "Plaintext must contain only lowercase letters" in str(excinfo.value)

	# Clean up
	import os

	if os.path.exists("ciphers/test_cipher.json"):
		os.remove("ciphers/test_cipher.json")
