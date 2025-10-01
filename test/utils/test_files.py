import pytest

@pytest.fixture
def sample_cipher():
	from encipherment.cipher import Cipher
	return Cipher("thisisatestcipher", 12)

@pytest.fixture(autouse=True)
def run_around_tests(tmp_path, monkeypatch):
	monkeypatch.chdir(tmp_path) # Change to the temporary directory for the test
	yield # Cleanup: Nothing needed as tmp_path is automatically cleaned up

def test_save_book(tmp_path):
	from utils.files import save_book
	book_id = "test_book"
	book_text = "This is a test book."
	save_book(book_id, book_text)
	saved_file = tmp_path / "books" / f"{book_id}.txt"
	assert saved_file.exists()
	assert saved_file.read_text() == book_text
 
def test_save_book_empty_text():
	from utils.files import save_book
	book_id = "empty_book"
	book_text = ""
	with pytest.raises(ValueError):
		save_book(book_id, book_text)
  
def test_book_is_cached(tmp_path):
	from utils.files import save_book, book_is_cached
	book_id = "cached_book"
	book_text = "This book is cached."
	assert not book_is_cached(book_id)
	save_book(book_id, book_text)
	assert book_is_cached(book_id)
 
def test_get_cached_book(tmp_path):
	from utils.files import save_book, get_cached_book
	book_id = "cached_book"
	book_text = "This book is cached."
	save_book(book_id, book_text)
	retrieved_text = get_cached_book(book_id)
	assert retrieved_text == book_text
 
def test_get_cached_book_not_found():
	from utils.files import get_cached_book
	book_id = "nonexistent_book"
	with pytest.raises(FileNotFoundError):
		get_cached_book(book_id)
  
def test_save_cipher(tmp_path, sample_cipher):
	from utils.files import save_cipher
	from encipherment.cipher import Cipher
	filename = "test_cipher.json"
	save_cipher(sample_cipher, filename)
	saved_file = tmp_path / "ciphers" / filename
	assert saved_file.exists()
	import json
	saved_content = json.loads(saved_file.read_text())
	assert saved_content == sample_cipher.__json__()