import pytest
import multiprocessing as mp


@pytest.fixture()
def sample_text():
	return (
		"thisisatestplaintextthatneedstobeencrypteditisjustarandomstringoflowercaselettersthatshouldworkfineanditislong"
		"enoughtotestthecipherwiththelengthshouldbeoverfourhundredcharactersmaybeevenfivehundredduetothistweneedtoensure"
		"thecipherworksasexpectedandcanhandlelargerinputswithoutanyissuesandthatthistextisextremelylongsoitcanbeusedtotest"
		"theperformanceoftheciphergenerationprocess"
	)


@pytest.fixture()
def valid_text_stream(sample_text):
	"""Returns a valid TextStream dictionary for HomophonicCipher."""
	return {
		"text": sample_text,
		"source_id": "book_123",
		"source_name": "Test Book",
		"length": len(sample_text),
	}


@pytest.fixture
def queue_factory():
    """Returns a factory function that creates fresh queues."""
    manager = mp.Manager()
    queues = []

    def _create_queue():
        q = manager.Queue()
        queues.append(q)
        return q

    return _create_queue


@pytest.fixture
def mock_tracker(mocker):
	"""Provides a mock tracker object for CipherProducer."""
	tracker = mocker.Mock()
	tracker.value = 0
	tracker.lock = mocker.MagicMock()
	return tracker, tracker.lock
