import pytest
from encipherment.cipher import HomophonicCipher
from utils.files import save_book, book_is_cached, get_cached_book, save_cipher


@pytest.fixture
def sample_cipher(valid_text_stream):
	return HomophonicCipher(valid_text_stream, difficulty=10)


@pytest.fixture(autouse=True)
def run_around_tests(tmp_path, monkeypatch):
	monkeypatch.chdir(tmp_path)  # Change to the temporary directory for the test
	yield  # Cleanup: Nothing needed as tmp_path is automatically cleaned up


def test_save_book(tmp_path):
	book_id = "test_book"
	book_text = "This is a test book."
	save_book(book_id, book_text)
	saved_file = tmp_path / "books" / f"{book_id}.txt"
	assert saved_file.exists()
	assert saved_file.read_text() == book_text


def test_save_book_empty_text():
	book_id = "empty_book"
	book_text = ""
	with pytest.raises(ValueError):
		save_book(book_id, book_text)


def test_book_is_cached(tmp_path):
	book_id = "cached_book"
	book_text = "This book is cached."
	assert not book_is_cached(book_id)
	save_book(book_id, book_text)
	assert book_is_cached(book_id)


def test_get_cached_book(tmp_path):
	book_id = "cached_book"
	book_text = "This book is cached."
	save_book(book_id, book_text)
	retrieved_text = get_cached_book(book_id)
	assert retrieved_text == book_text


def test_get_cached_book_not_found():
	book_id = "nonexistent_book"
	with pytest.raises(FileNotFoundError):
		get_cached_book(book_id)


def test_save_cipher(tmp_path, sample_cipher):
	filename = "test_cipher.json"
	save_cipher(sample_cipher, filename)
	saved_file = tmp_path / "ciphers" / filename
	assert saved_file.exists()
	import json

	saved_content = json.loads(saved_file.read_text())
	assert saved_content == sample_cipher.__json__()


def test_save_cipher_no_ciphers_dir(tmp_path, sample_cipher):
	filename = "test_cipher.json"
	# Ensure ciphers directory does not exist
	ciphers_dir = tmp_path / "ciphers"
	if ciphers_dir.exists():
		for file in ciphers_dir.iterdir():
			file.unlink()
		ciphers_dir.rmdir()
	save_cipher(sample_cipher, filename)
	saved_file = tmp_path / "ciphers" / filename
	assert saved_file.exists()


def test_save_book_error_creating_dir(monkeypatch, sample_cipher):
	def mock_makedirs_fail(path, exist_ok=False):
		raise OSError("Mocked error creating directory")

	monkeypatch.setattr("os.makedirs", mock_makedirs_fail)
	with pytest.raises(RuntimeError) as excinfo:
		save_book("book_id", "Some book text")
	assert "Error creating books directory" in str(excinfo.value)


def test_save_book_error_writing_file(monkeypatch, tmp_path):
	def mock_open_fail(*args, **kwargs):
		raise OSError("Mocked error opening file")

	monkeypatch.setattr("builtins.open", mock_open_fail)
	with pytest.raises(RuntimeError) as excinfo:
		save_book("book_id", "Some book text")
	assert "Error saving book" in str(excinfo.value)
