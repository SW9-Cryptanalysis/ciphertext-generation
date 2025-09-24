import pytest

from text_fetching.fetcher import Fetcher

@pytest.fixture
def sample_text_book():
    return (
        """
        I met a traveller from an antique land,
        Who said—“Two vast and trunkless legs of stone
        Stand in the desert. . . ."""
    )

@pytest.fixture
def long_text():
    return 'a' * 10000

@pytest.fixture
def short_text():
    return 'a' * 10

@pytest.fixture
def no_text():
    return None

def test_format_text(sample_text_book):
    fetcher = Fetcher()
    formatted_text = fetcher.format_text(sample_text_book)
    assert formatted_text.isalpha()
    assert formatted_text.islower()
    assert isinstance(formatted_text, str) 
    assert formatted_text == "imetatravellerfromanantiquelandwhosaidtwovastandtrunklesslegsofstonestandinthedesert"

def test_format_notext(no_text):
    fetcher = Fetcher()
    with pytest.raises(ValueError) as excinfo:
        fetcher.format_text(no_text)
    assert(
        "text must a string"
        in str(excinfo.value)
    )
    
def test_slicing_text(long_text):
    fetcher = Fetcher()
    sliced_text = fetcher.get_random_book_slice(book_text=long_text, min_len=100, max_len=5000)
    assert len(sliced_text) <= 5000
    assert len(sliced_text) >= 100
    assert isinstance(sliced_text, str)

def test_slicing_no_text(no_text):
    fetcher = Fetcher()
    with pytest.raises(ValueError) as excinfo:
        fetcher.get_random_book_slice(no_text)
    assert(
        "book_text must be a string"
        in str(excinfo.value)
    )

def test_slicing_short_text(short_text):
    fetcher = Fetcher()
    min_len = 100
    assert len(short_text) < min_len
    with pytest.raises(ValueError) as excinfo:
        fetcher.get_random_book_slice(book_text=short_text, min_len=min_len)
    assert(
        "Length of book_text must be equal to or greater than min_len"
        in str(excinfo.value)
    )

