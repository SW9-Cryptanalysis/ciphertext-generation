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
		
		# Setup input data
		sample_item = {
			"text": "sample text", 
			"source_id": "123", 
			"source_name": "Book", 
			"length": 11
		}
		input_q.put(sample_item)
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

		last_filename, last_bytes = items_in_queue[-1]
		expected_pid = os.getpid()

		# Filename format: c_{len}_{source_id}_{difficulty}_{pid}.json
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
		
		# Add two items: one that fails, one that stops
		input_q.put({"text": "fail", "source_id": "1"})
		input_q.put("STOP")

		mock_log = mocker.patch("drive.cipher_producer.log")

		# Mock generate_cipher to return None (failure)
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

		# Queue should be empty because the failed item is skipped
		assert output_q.empty()
		
		# We don't assert specific log calls for the loop since the Producer 
		# just continues on None, but we verify it finished gracefully.
		mock_log.info.assert_any_call("TestProducer finished generation.")
		
	def test_run_handles_queue_empty_and_retries(self, mocker):
		# We mock the input queue to simulate a timeout (Empty) followed by a valid STOP
		mock_input_q = mocker.Mock()
		mock_output_q = mocker.Mock()
		
		# Side effect: First call raises Empty, second returns "STOP"
		mock_input_q.get.side_effect = [queue.Empty, "STOP"]
		
		producer = CipherProducer(
			input_queue=mock_input_q, 
			output_queue=mock_output_q, 
			name="TestProducer"
		)
		
		producer.run()
		
		# Assert get was called twice (retried after Empty)
		assert mock_input_q.get.call_count == 2

	def test_run_handles_unexpected_loop_exception(self, mocker):
		# We mock the queue to raise a generic Exception, then STOP
		mock_input_q = mocker.Mock()
		mock_output_q = mocker.Mock()
		mock_log = mocker.patch("drive.cipher_producer.log")
		
		# Side effect: First call crashes, second stops
		mock_input_q.get.side_effect = [Exception("Queue connection lost"), "STOP"]
		
		producer = CipherProducer(
			input_queue=mock_input_q, 
			output_queue=mock_output_q, 
			name="TestProducer"
		)
		
		producer.run()
		
		# Verify the error was logged
		mock_log.error.assert_called()
		assert "Queue connection lost" in mock_log.error.call_args[0][0]
		# Verify it didn't crash the process (it called get a second time)
		assert mock_input_q.get.call_count == 2


class TestGenerateCipherLogic:
	def test_generate_cipher_success(self, mocker):
		# We pass mocks for queues since we only test the method
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

		# New logic passes the entire item/text to the cipher
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

		# The new implementation catches exceptions and returns None
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

		# Mock HomophonicCipher to raise a generic Exception (not ValueError)
		mocker.patch(
			"drive.cipher_producer.HomophonicCipher",
			side_effect=Exception("Critical system failure"),
		)

		result = producer.generate_cipher(sample_item)

		assert result is None
		mock_log.error.assert_called()
		# Ensure it hit the "Unexpected cipher generation error" block
		log_msg = mock_log.error.call_args[0][0]
		assert "Unexpected cipher generation error" in log_msg
		assert "Critical system failure" in log_msg
