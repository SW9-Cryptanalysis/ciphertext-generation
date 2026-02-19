import pytest
import os
import multiprocessing as mp
import queue
from drive.cipher_producer import CipherProducer
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from fetching.text_splits import TextStream


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
def mock_queues():
	"""Provides thread-safe multiprocessing queues."""
	manager = mp.Manager()
	return manager.Queue(), manager.Queue()


@pytest.fixture
def mock_cipher_data():
	"""Provides mock bytes and json data returned by create_cipher_json."""
	mock_json = '{"key": "value"}'
	mock_bytes = mock_json.encode("utf-8")
	return mock_json, mock_bytes


class TestCipherProducerRun:
	def test_successful_run(self, mocker, mock_queues, mock_cipher_data):
		input_q, output_q = mock_queues
		
		sample_item = {
			"text": "sample text", 
			"source_id": "123", 
			"source_name": "Book", 
			"length": 11
		}
		input_q.put(("train", sample_item))
		input_q.put("STOP")

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
			input_queue=input_q,
			output_queue=output_q,
			name="TestProducer"
		)

		producer.run()

		mock_generate_cipher.assert_called_once_with(sample_item)
		mock_create_json.assert_called_once_with(mock_cipher_return)

		items_in_queue = []
		try:
			items_in_queue.append(output_q.get(timeout=0.1))
		except queue.Empty:
			pytest.fail("Queue was empty before receiving expected cipher.")

		assert len(items_in_queue) == 1

		last_split, last_filename, last_bytes = items_in_queue[-1]
		expected_pid = os.getpid()

		assert last_split == "train"
		assert f"_{expected_pid}.json" in last_filename
		assert "123" in last_filename
		assert last_bytes == mock_cipher_data[1]

	def test_stop_signal(self, mock_queues, caplog):
		input_q, output_q = mock_queues
		input_q.put("STOP")

		producer = CipherProducer(
			input_queue=input_q,
			output_queue=output_q,
			name="TestProducer"
		)

		producer.run()

		assert output_q.empty()

	def test_generation_runtime_failure(self, mocker, mock_queues, caplog):
		input_q, output_q = mock_queues
		
		input_q.put(("val", {"text": "fail", "source_id": "1"}))
		input_q.put("STOP")

		mock_log = mocker.patch("drive.cipher_producer.log")

		mocker.patch.object(
			CipherProducer,
			"generate_cipher",
			return_value=None
		)

		producer = CipherProducer(
			input_queue=input_q, 
			output_queue=output_q, 
			name="TestProducer"
		)

		producer.run()

		assert output_q.empty()
		mock_log.info.assert_any_call("TestProducer finished generation.")
		
	def test_run_handles_queue_empty_and_retries(self, mocker):
		mock_input_q = mocker.Mock()
		mock_output_q = mocker.Mock()
		
		mock_input_q.get.side_effect = [queue.Empty, "STOP"]
		
		producer = CipherProducer(
			input_queue=mock_input_q, 
			output_queue=mock_output_q, 
			name="TestProducer"
		)
		
		producer.run()
		
		assert mock_input_q.get.call_count == 2

	def test_run_handles_unexpected_loop_exception(self, mocker):
		mock_input_q = mocker.Mock()
		mock_output_q = mocker.Mock()
		mock_log = mocker.patch("drive.cipher_producer.log")
		
		mock_input_q.get.side_effect = [Exception("Queue connection lost"), "STOP"]
		
		producer = CipherProducer(
			input_queue=mock_input_q, 
			output_queue=mock_output_q, 
			name="TestProducer"
		)
		
		producer.run()
		
		mock_log.error.assert_called()
		assert "Queue connection lost" in mock_log.error.call_args[0][0]
		assert mock_input_q.get.call_count == 2


class TestGenerateCipherLogic:
	def test_generate_cipher_success(self, mocker):
		producer = CipherProducer(mocker.Mock(), mocker.Mock(), name="Test")
		
		sample_item: TextStream = {
			"text": "testslice", 
			"source_id": "123", 
			"source_name": "Book", 
			"length": 9
		}

		mock_cipher_instance = mocker.Mock(spec=HomophonicCipher)
		mocked_homophonic_cipher = mocker.patch(
			"drive.cipher_producer.HomophonicCipher", 
			return_value=mock_cipher_instance
		)

		cipher = producer.generate_cipher(sample_item)

		mocked_homophonic_cipher.assert_called_once_with(sample_item)
		
		mock_cipher_instance.generate_difficulty.assert_called_once()
		mock_cipher_instance.generate_key.assert_called_once()
		mock_cipher_instance.encipher.assert_called_once()
		
		assert cipher == mock_cipher_instance

	def test_generate_cipher_value_error(self, mocker, caplog):
		producer = CipherProducer(mocker.Mock(), mocker.Mock(), name="Test")
		
		sample_item: TextStream = {
			"text": "invalid", 
			"source_id": "123",
			"source_name": "Book",
			"length": 9
		}

		mock_log = mocker.patch("drive.cipher_producer.log")

		mocker.patch(
			"drive.cipher_producer.HomophonicCipher",
			side_effect=ValueError("Invalid cipher setup"),
		)

		result = producer.generate_cipher(sample_item)

		assert result is None
		mock_log.error.assert_called()
		assert "Error generating cipher" in mock_log.error.call_args[0][0]

	def test_generate_cipher_unexpected_exception(self, mocker):
		producer = CipherProducer(mocker.Mock(), mocker.Mock(), name="Test")
		sample_item: TextStream = {
			"text": "crash_test", 
			"source_id": "123",
			"source_name": "Book",
			"length": 10
		}

		mock_log = mocker.patch("drive.cipher_producer.log")

		mocker.patch(
			"drive.cipher_producer.HomophonicCipher",
			side_effect=Exception("Critical system failure"),
		)

		result = producer.generate_cipher(sample_item)

		assert result is None
		mock_log.error.assert_called()
		log_msg = mock_log.error.call_args[0][0]
		assert "Unexpected cipher generation error" in log_msg
		assert "Critical system failure" in log_msg