import pytest
import requests
import itertools

from text_fetching.fetcher import Fetcher
from utils.formatting import format_text


@pytest.fixture
def sample_text_book():
	return """
		I met a traveller from an antique land,
		Who said—“Two vast and trunkless legs of stone
		Stand in the desert. . . ."""


@pytest.fixture(autouse=True)
def mock_save_book(mocker):
	mocker.patch("text_fetching.fetcher.save_book")


@pytest.fixture
def long_text():
	return "a" * 10000


@pytest.fixture
def short_text():
	return "a" * 10


@pytest.fixture
def no_text():
	return None


@pytest.fixture
def empty_text():
	return ""


@pytest.fixture
def accented_text():
	return "kožušček François æåø äö êèéêñ"


@pytest.fixture
def text_with_spaces():
	return "this is a text for testing purposes which is extremely long and has spaces in it as well so that it can be sliced properly i cannot come up with a better example so i will just use this one so lets just write a lot of nonsense text and hope it works and then we can see if it breaks or not and if it does break we can fix it and then we can write a new one and so on and so forth until we run out of ideas and we have to write the next one"


def test_slicing_text(text_with_spaces):
	fetcher = Fetcher()
	sliced_text = fetcher.get_random_book_slice(
		book_text=text_with_spaces, min_len=5, max_len=20
	)
	assert isinstance(sliced_text, str)
	assert 5 <= len(sliced_text) <= 20


def test_slicing_text_long(text_with_spaces):
	fetcher = Fetcher()
	sliced_text = fetcher.get_random_book_slice(
		book_text=text_with_spaces, min_len=100, max_len=200
	)
	assert isinstance(sliced_text, str)
	assert 100 <= len(sliced_text) <= 200


def test_slicing_empty_text(empty_text):
	fetcher = Fetcher()
	with pytest.raises(ValueError) as excinfo:
		fetcher.get_random_book_slice(empty_text, min_len=100, max_len=200)
	assert "Parameter `book_text` cannot be blank nor empty" in str(excinfo.value)


def test_slicing_no_text(no_text):
	fetcher = Fetcher()
	with pytest.raises(TypeError) as excinfo:
		fetcher.get_random_book_slice(no_text, min_len=100, max_len=200)
	assert "Parameter 'book_text' must be `str`, got `NoneType`." in str(excinfo.value)


def test_slicing_short_text(short_text):
	fetcher = Fetcher()
	min_len = 100
	assert len(short_text) < min_len
	with pytest.raises(ValueError) as excinfo:
		fetcher.get_random_book_slice(
			book_text=short_text, min_len=min_len, max_len=200
		)
	assert "book_text is shorter than the specified max_le" in str(excinfo.value)


def test_fetch_book_success(mocker):
	# First response: metadata
	mock_metadata_resp = mocker.Mock()
	mock_metadata_resp.raise_for_status.return_value = None
	mock_metadata_resp.json.return_value = {
		"formats": {"text/plain; charset=utf-8": "http://example.com/book.txt"}
	}

	# Mock cached book check to return False
	mocker.patch("text_fetching.fetcher.book_is_cached", return_value=False)
	fetcher = Fetcher()

	# Second response: actual book text
	mock_text_resp = mocker.Mock()
	mock_text_resp.raise_for_status.return_value = None
	mock_text_resp.text = "This is the book content."

	mock_get = mocker.patch(
		"text_fetching.fetcher.requests.get",
		side_effect=[mock_metadata_resp, mock_text_resp],
	)
	book_text = fetcher.fetch_random_book_text()
	assert book_text is not None
	assert book_text == format_text("This is the book content.")
	assert isinstance(book_text, str)
	assert mock_get.call_count == 2


def test_fetch_book_cached(mocker):
	# Mock cached book check to return True
	# Mock get_cached_book to return specific text

	mocker.patch("text_fetching.fetcher.book_is_cached", return_value=True)
	mocker.patch(
		"text_fetching.fetcher.get_cached_book", return_value="Cached book content."
	)

	fetcher = Fetcher()

	# Mock requests.get to ensure it's not called
	mock_get = mocker.patch("text_fetching.fetcher.requests.get")
	book_text = fetcher.fetch_random_book_text()
	assert book_text is not None
	assert book_text == "Cached book content."
	assert isinstance(book_text, str)
	assert mock_get.call_count == 0  # Ensure no HTTP requests were made


def test_fetch_book_no_format(mocker):
	mocker.patch("text_fetching.fetcher.book_is_cached", return_value=False)
	fetcher = Fetcher()
	# Mock the metadata response without suitable text formats
	mock_metadata_resp = mocker.Mock()
	mock_metadata_resp.raise_for_status.return_value = None
	mock_metadata_resp.json.return_value = {
		"formats": {"application/pdf": "http://example.com/book.pdf"}
	}

	mock_get = mocker.patch(
		"text_fetching.fetcher.requests.get",
		return_value=mock_metadata_resp,
	)
	with pytest.raises(RuntimeError) as excinfo:
		fetcher.fetch_random_book_text()
	assert "No suitable text format found" in str(excinfo.value)
	assert mock_get.call_count == 1


def test_fetch_book_request_exception(mocker):
	from requests import RequestException, Request, Response

	mocker.patch("text_fetching.fetcher.book_is_cached", return_value=False)
	fetcher = Fetcher()
	# Mock requests.get to raise a RequestException
	mock_get = mocker.patch(
		"text_fetching.fetcher.requests.get",
		side_effect=RequestException(
			"Network Error", request=Request(), response=Response()
		),
	)
	with pytest.raises(RuntimeError) as excinfo:
		fetcher.fetch_random_book_text()
	assert "Error fetching book data: Network Error" in str(excinfo.value)
	assert mock_get.call_count == 1


def test_fetch_book_invalid_id(mocker):
	mocker.patch("text_fetching.fetcher.book_is_cached", return_value=False)
	fetcher = Fetcher()
	# Mock requests.get to raise a RequestException for invalid book ID
	mock_get = mocker.patch(
		"text_fetching.fetcher.requests.get",
		side_effect=requests.RequestException("404 Client Error: Not Found for url"),
	)
	with pytest.raises(RuntimeError) as excinfo:
		fetcher.fetch_random_book_text()
	assert "Error fetching book data: 404 Client Error: Not Found for url" in str(
		excinfo.value
	)
	assert mock_get.call_count == 1


def test_fetch_book_empty_response(mocker):
	# Mock the metadata response with empty formats
	mock_metadata_resp = mocker.Mock()
	mock_metadata_resp.raise_for_status.return_value = None
	mock_metadata_resp.json.return_value = {"formats": {}}

	mocker.patch("text_fetching.fetcher.book_is_cached", return_value=False)
	fetcher = Fetcher()

	mock_get = mocker.patch(
		"text_fetching.fetcher.requests.get",
		return_value=mock_metadata_resp,
	)
	with pytest.raises(RuntimeError) as excinfo:
		fetcher.fetch_random_book_text()
	assert "No suitable text format found" in str(excinfo.value)
	assert mock_get.call_count == 1


def test_book_slice_min_greater_than_max(long_text):
	fetcher = Fetcher()
	with pytest.raises(ValueError) as excinfo:
		fetcher.get_random_book_slice(book_text=long_text, min_len=200, max_len=100)
	assert (
		"min_len and max_len must be positive integers with min_len <= max_len"
		in str(excinfo.value)
	)


def test_book_slice_negative_lengths(long_text):
	fetcher = Fetcher()
	with pytest.raises(ValueError) as excinfo:
		fetcher.get_random_book_slice(book_text=long_text, min_len=-50, max_len=100)
	assert "Parameter 'min_len' cannot be negative, but received -50." in str(
		excinfo.value
	)
	with pytest.raises(ValueError) as excinfo:
		fetcher.get_random_book_slice(book_text=long_text, min_len=50, max_len=-100)
	assert "Parameter 'max_len' cannot be negative, but received -100." in str(
		excinfo.value
	)


def test_book_slice_length_smaller_than_max(long_text):
	fetcher = Fetcher()
	with pytest.raises(ValueError) as excinfo:
		fetcher.get_random_book_slice(book_text=long_text, min_len=50, max_len=20000)
	assert "book_text is shorter than the specified max_len" in str(excinfo.value)


def test_fetch_book_validation(mocker):
	# First response: metadata
	mock_metadata_resp = mocker.Mock()
	mock_metadata_resp.raise_for_status.return_value = None
	mock_metadata_resp.json.return_value = {
		"formats": {"text/plain; charset=utf-8": "http://example.com/book.txt"}
	}

	# Mock cached book check to return False
	mocker.patch("text_fetching.fetcher.book_is_cached", return_value=False)
	fetcher = Fetcher(True)

	# Second response: actual book text
	mock_text_resp = mocker.Mock()
	mock_text_resp.raise_for_status.return_value = None
	mock_text_resp.text = "This is the book content."

	mock_get = mocker.patch(
		"text_fetching.fetcher.requests.get",
		side_effect=[mock_metadata_resp, mock_text_resp],
	)
	book_text = fetcher.fetch_random_book_text()
	assert book_text is not None
	assert book_text == format_text("This is the book content.")
	assert isinstance(book_text, str)
	assert mock_get.call_count == 2
	assert fetcher.book_id in fetcher.BOOK_IDS_VALIDATION
	assert fetcher.book_id not in fetcher.BOOK_IDS
	assert (
		mock_get.call_args_list[0][0][0]
		== f"https://gutendex.com/books/{fetcher.book_id}"
	)


def test_load_books(mocker):
	# Mock the metadata response with empty formats
	# Mock is_cached to return False
	mocker.patch("text_fetching.fetcher.book_is_cached", return_value=False)

	mock_metadata_resp = mocker.Mock()
	mock_metadata_resp.raise_for_status.return_value = None
	mock_metadata_resp.json.return_value = {
		"formats": {"text/plain; charset=utf-8": "http://example.com/book.txt"}
	}

	# Mock the text response
	mock_text_resp = mocker.Mock()
	mock_text_resp.raise_for_status.return_value = None
	mock_text_resp.text = "This is the book content. It should have a certain length."

	mock_get = mocker.patch(
		"text_fetching.fetcher.requests.get",
		side_effect=itertools.cycle([mock_metadata_resp, mock_text_resp]),
	)
	fetcher = Fetcher()
	fetcher.load_books()
	assert fetcher.book_id in fetcher.BOOK_IDS_VALIDATION
	assert fetcher.book_id not in fetcher.BOOK_IDS
	assert (
		mock_get.call_count
		== (len(fetcher.BOOK_IDS_VALIDATION) + len(fetcher.BOOK_IDS)) * 2
	)
	assert (
		mock_get.call_args_list[-2][0][0]
		== f"https://gutendex.com/books/{fetcher.book_id}"
	)
	assert mock_get.call_args_list[-1][0][0] == "http://example.com/book.txt"
