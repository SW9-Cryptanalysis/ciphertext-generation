import pytest
import os
import multiprocessing as mp
from drive.cipher_producer import CipherProducer
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
import queue


class MockCipher(SubstitutionCipher):
	"""Mock object to simulate a fully generated cipher."""

	def __init__(self, *args, **kwargs):
		self.plaintext = "a" * 500
		self.difficulty = 10

	def generate_key(self):
		self.key = {"a": ["1"], "b": ["2"], "c": ["3"]}

		return self.key

	def encipher(self):
		self.ciphertext = "1 2 3"
		self.recurrence_encoding = "1 2 3"

		return self.ciphertext


@pytest.fixture
def mock_queue():
	"""Provides a thread-safe multiprocessing queue."""
	manager = mp.Manager()
	return manager.Queue()


@pytest.fixture
def mock_cipher_data():
	"""Provides mock bytes and json data returned by create_cipher_json."""
	mock_json = '{"key": "value"}'
	mock_bytes = mock_json.encode("utf-8")
	return mock_json, mock_bytes


class TestCipherProducerRun:
	def test_successful_run(self, mocker, mock_queue, mock_cipher_data):
		total_ciphers = 3

		mock_fetcher_instance = mocker.Mock()
		mock_fetcher_class = mocker.patch(
			"drive.cipher_producer.Fetcher",
			return_value=mock_fetcher_instance
		)

		mock_cipher_return = MockCipher()

		mock_generate_cipher = mocker.patch.object(
			CipherProducer,
			"generate_cipher",
			return_value=mock_cipher_return
		)

		mock_create_json = mocker.patch(
			"drive.cipher_producer.create_cipher_json",
			return_value=mock_cipher_data
		)

		producer = CipherProducer(
			queue=mock_queue,
			start_and_total=(10, total_ciphers),
			name="TestProducer"
		)

		producer.run()

		mock_fetcher_class.assert_called_once()

		assert mock_generate_cipher.call_count == total_ciphers
		assert mock_create_json.call_count == total_ciphers

		items_in_queue = []
		for _ in range(total_ciphers):
			try:
				items_in_queue.append(mock_queue.get(timeout=0.1))
			except queue.Empty:
				pytest.fail("Queue was empty before receiving all expected ciphers.")

		assert len(items_in_queue) == total_ciphers

		last_filename, last_bytes = items_in_queue[-1]
		expected_pid = os.getpid()

		assert f"_{12}_{expected_pid}.json" in last_filename
		assert last_bytes == mock_cipher_data[1]

	def test_fetcher_initialization_failure(self, mocker, mock_queue, caplog):
		mock_log = mocker.patch("drive.cipher_producer.log")
		mocker.patch(
			"drive.cipher_producer.Fetcher",
			side_effect=Exception("Fetcher init error"),
		)

		mock_generate_cipher = mocker.patch.object(
			CipherProducer,
			"generate_cipher",
			side_effect=Exception("Cipher generation failed mid-loop"),
		)

		producer = CipherProducer(
			queue=mock_queue, start_and_total=(0, 10), name="TestProducer"
		)

		producer.run()

		mock_log.critical.assert_called_once()
		mock_generate_cipher.assert_not_called()
		assert mock_queue.empty()

	def test_generation_runtime_failure(self, mocker, mock_queue, caplog):
		total_ciphers = 3

		mock_log = mocker.patch("drive.cipher_producer.log")
		mocker.patch("drive.cipher_producer.Fetcher")

		mocker.patch.object(
			CipherProducer,
			"generate_cipher",
			side_effect=[
				MockCipher(),
				Exception("Cipher generation failed mid-loop"),
				MockCipher(),
			],
		)

		mock_generate_cipher = mocker.patch.object(
			CipherProducer,
			"generate_cipher",
			side_effect=[
				MockCipher(),
				Exception("Cipher generation failed mid-loop")
			]
		)

		producer = CipherProducer(
			queue=mock_queue, start_and_total=(0, total_ciphers), name="TestProducer"
		)

		producer.run()

		mock_log.error.assert_called_with("Producer TestProducer failed on cipher 2: ")
		assert mock_generate_cipher.call_count == total_ciphers
		assert mock_queue.qsize() == 0
		mock_log.info.assert_called_with("TestProducer finished generation.")


class TestGenerateCipherLogic:
	def test_generate_cipher_success(self, mocker):
		producer = mocker.MagicMock(spec=CipherProducer)

		mock_fetch_text = mocker.patch(
			"drive.cipher_producer.Fetcher.fetch_random_book_text",
			return_value="a" * 1000
		)
		mock_get_slice = mocker.patch(
			"drive.cipher_producer.Fetcher.get_random_book_slice",
			return_value="testslice"
		)

		mock_cipher_instance = mocker.Mock(spec=HomophonicCipher)
		mocked_homophonic_cipher = mocker.patch(
			"drive.cipher_producer.HomophonicCipher", return_value=mock_cipher_instance
		)

		cipher = CipherProducer.generate_cipher(producer)

		mocked_homophonic_cipher.assert_called_once_with("testslice")
		mock_fetch_text.assert_called_once()
		mock_get_slice.assert_called_once()
		assert isinstance(cipher, HomophonicCipher)

	def test_generate_cipher_value_error(self, mocker, caplog):
		producer = mocker.MagicMock(spec=CipherProducer)
		producer.MIN_LEN = 400
		producer.MAX_LEN = 1000

		mock_fetcher = mocker.Mock()
		mock_fetcher.fetch_random_book_text.return_value = "a" * 1000
		mock_fetcher.get_random_book_slice.return_value = "testslice"
		mock_fetcher.book_id = "test_book_123"
		producer.fetcher = mock_fetcher

		mock_log = mocker.patch("drive.cipher_producer.log")

		mocker.patch(
			"drive.cipher_producer.HomophonicCipher",
			side_effect=ValueError("Invalid cipher setup"),
		)

		with pytest.raises(ValueError):
			CipherProducer.generate_cipher(producer)

		mock_log.error.assert_called_with("Error generating cipher for book id: test_book_123")
