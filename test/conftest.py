import pytest
import multiprocessing as mp
from dataclasses import dataclass


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
def mock_queue():
	"""Provides thread-safe multiprocessing queues."""
	manager = mp.Manager()
	return manager.Queue()


@pytest.fixture
def mock_tracker(mocker):
	"""Provides a mock tracker object for CipherProducer."""
	tracker = mocker.Mock()
	tracker.value = 0
	tracker.lock = mocker.MagicMock()
	return tracker, tracker.lock
