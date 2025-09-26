import pytest

from text_fetching.fetcher import Fetcher


@pytest.fixture
def sample_text_book():
    return """
		I met a traveller from an antique land,
		Who said—“Two vast and trunkless legs of stone
		Stand in the desert. . . ."""


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
def accented_text():
    return "kožušček François æåø äö êèéêñ"

def test_format_text(sample_text_book):
    fetcher = Fetcher()
    formatted_text = fetcher.format_text(sample_text_book)
    assert formatted_text.isalpha()
    assert formatted_text.islower()
    assert isinstance(formatted_text, str)
    assert (
        formatted_text
        == "imetatravellerfromanantiquelandwhosaidtwovastandtrunklesslegsofstonestandinthedesert"
    )


def test_format_notext(no_text):
    fetcher = Fetcher()
    with pytest.raises(ValueError) as excinfo:
        fetcher.format_text(no_text)
    assert "Argument must be a string" in str(excinfo.value)


def test_format_regional_text(accented_text):
    fetcher = Fetcher()
    formatted_text = fetcher.format_text(accented_text)
    assert(formatted_text == "kozuscekfrancoisaeaoaoeeeen")


def test_slicing_text(long_text):
    fetcher = Fetcher()
    sliced_text = fetcher.get_random_book_slice(
        book_text=long_text, min_len=100, max_len=100
    )
    assert isinstance(sliced_text, str)
    assert len(sliced_text) == 100


def test_slicing_no_text(no_text):
    fetcher = Fetcher()
    with pytest.raises(ValueError) as excinfo:
        fetcher.get_random_book_slice(no_text)
    assert "book_text must be a string" in str(excinfo.value)


def test_slicing_short_text(short_text):
    fetcher = Fetcher()
    min_len = 100
    assert len(short_text) < min_len
    with pytest.raises(ValueError) as excinfo:
        fetcher.get_random_book_slice(book_text=short_text, min_len=min_len)
    assert "Length of book_text must be equal to or greater than min_len" in str(
        excinfo.value
    )


def test_fetch_book_success(mocker):
    fetcher = Fetcher()
    # First response: metadata
    mock_metadata_resp = mocker.Mock()
    mock_metadata_resp.raise_for_status.return_value = None
    mock_metadata_resp.json.return_value = {
        "formats": {"text/plain; charset=utf-8": "http://example.com/book.txt"}
    }

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
    assert book_text == "This is the book content."
    assert isinstance(book_text, str)
    assert mock_get.call_count == 2


def test_fetch_book_no_format(mocker):
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
