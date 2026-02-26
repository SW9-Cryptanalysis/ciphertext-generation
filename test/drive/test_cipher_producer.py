import pytest
import os
import queue
from drive.cipher_producer import CipherProducer
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from fetching.text_splits import TextStream
from dataclasses import dataclass
import multiprocessing as mp

class MockCipher(SubstitutionCipher):
	"""Mock object to simulate a fully generated cipher."""

	def __init__(self, *args, **kwargs):
		self.plaintext = "a" * 500
		self.difficulty = 10
		self.num_symbols = 3

	def generate_key(self):
		self.key = {"a": ["1"], "b": ["2"], "c": ["3"]}
		return self.key

	def encipher(self):
		self.ciphertext = "1 2 3"
		self.num_symbols = 3
		return self.ciphertext


@pytest.fixture
def mock_cipher_data():
	"""Provides mock bytes and json data returned by create_cipher_json."""
	mock_json = '{"key": "value"}'
	mock_bytes = mock_json.encode("utf-8")
	return mock_json, mock_bytes


@dataclass
class ProducerContext:
	queue: mp.Queue
	tracker: tuple
	cipher_data: tuple


@pytest.fixture
def producer_ctx(queue_factory, mock_tracker, mock_cipher_data):
	"""Bundles producer mocks to keep test signatures small."""
	return ProducerContext(queue_factory(), mock_tracker, mock_cipher_data)


@pytest.fixture
def mock_producer(queue_factory, mock_tracker):
	"""Provides a mock CipherProducer object for testing."""
	return CipherProducer((queue_factory(), queue_factory()), mock_tracker, name="TestProducer")


class TestCipherProducerRun:
	def test_successful_run(self, mocker, producer_ctx, valid_text_stream):
		input_q, output_q = producer_ctx.queue, producer_ctx.queue

		input_q.put(("train", valid_text_stream))
		input_q.put("STOP")

		mock_cipher_return = MockCipher()

		mock_generate_cipher = mocker.patch.object(
			CipherProducer, "generate_cipher", return_value=mock_cipher_return
		)

		mock_create_json = mocker.patch(
			"drive.cipher_producer.create_cipher_json",
			return_value=producer_ctx.cipher_data,
		)

		producer = CipherProducer(
			queues=(input_q, output_q),
			tracker=producer_ctx.tracker,
			name="TestProducer",
		)

		producer.run()

		mock_generate_cipher.assert_called_once_with(valid_text_stream)
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
		assert last_bytes == producer_ctx.cipher_data[1]

	def test_stop_signal(self, queue_factory, mock_tracker, caplog):
		input_q, output_q = queue_factory(), queue_factory()
		input_q.put("STOP")

		producer = CipherProducer(
			queues=(input_q, output_q), tracker=mock_tracker, name="TestProducer"
		)

		producer.run()

		assert output_q.empty()

	def test_generation_runtime_failure(self, mocker, queue_factory, mock_tracker):
		input_q, output_q = queue_factory(), queue_factory()

		input_q.put(("val", {"text": "fail", "source_id": "1"}))
		input_q.put("STOP")

		mock_log = mocker.patch("drive.cipher_producer.log")

		mocker.patch.object(CipherProducer, "generate_cipher", return_value=None)

		producer = CipherProducer(
			queues=(input_q, output_q), tracker=mock_tracker, name="TestProducer"
		)

		producer.run()

		assert output_q.empty()
		mock_log.info.assert_any_call("TestProducer finished generation.")

	def test_run_handles_queue_empty_and_retries(self, mocker, mock_tracker):
		mock_input_q = mocker.Mock()
		mock_output_q = mocker.Mock()

		mock_input_q.get.side_effect = [queue.Empty, "STOP"]

		producer = CipherProducer(
			queues=(mock_input_q, mock_output_q),
			tracker=mock_tracker,
			name="TestProducer",
		)

		producer.run()

		assert mock_input_q.get.call_count == 2

	def test_run_handles_unexpected_loop_exception(self, mocker, mock_tracker):
		mock_input_q = mocker.Mock()
		mock_output_q = mocker.Mock()
		mock_log = mocker.patch("drive.cipher_producer.log")

		mock_input_q.get.side_effect = [Exception("Queue connection lost"), "STOP"]

		producer = CipherProducer(
			queues=(mock_input_q, mock_output_q),
			tracker=mock_tracker,
			name="TestProducer",
		)

		producer.run()

		mock_log.error.assert_called()
		assert "Queue connection lost" in mock_log.error.call_args[0][0]
		assert mock_input_q.get.call_count == 2


class TestUpdateMaxSymbolId:
	def test_update_when_new_id_is_greater(self, mock_tracker, queue_factory):
		val_proxy, lock = mock_tracker
		val_proxy.value = 5  # Initial state

		producer = CipherProducer(
			queues=(queue_factory(), queue_factory()), tracker=mock_tracker, name="TestProducer"
		)

		producer._update_max_symbol_id(10)

		# The value should be updated to 10
		assert val_proxy.value == 10
		# Verify the lock was actually acquired
		lock.__enter__.assert_called_once()

	def test_ignore_when_new_id_is_lesser_or_equal(self, mock_tracker, queue_factory):
		val_proxy, lock = mock_tracker
		val_proxy.value = 20  # Initial state is high

		producer = CipherProducer(
			queues=(queue_factory(), queue_factory()), tracker=mock_tracker, name="TestProducer"
		)

		# Try a lesser value
		producer._update_max_symbol_id(10)
		assert val_proxy.value == 20

		# Try an equal value
		producer._update_max_symbol_id(20)
		assert val_proxy.value == 20

		# Lock should still be acquired both times to check the value safely
		assert lock.__enter__.call_count == 2

	def test_early_return_if_tracker_or_lock_is_none(self, queue_factory, mock_tracker):
		_, lock = mock_tracker

		producer = CipherProducer(
			queues=(queue_factory(), queue_factory()),
			tracker=(None, lock),  # type: ignore
			name="TestProducerNoTracker",
		)

		producer._update_max_symbol_id(10)

		# Lock should never be acquired because of the early return
		lock.__enter__.assert_not_called()

	def test_early_return_if_lock_is_none(self, mock_tracker, queue_factory):
		val_proxy, _ = mock_tracker
		val_proxy.value = 5

		producer = CipherProducer(
			queues=(queue_factory(), queue_factory()),
			tracker=(val_proxy, None),  # type: ignore
			name="TestProducerNoLock",
		)

		producer._update_max_symbol_id(10)

		# Value should remain unchanged because of the early return
		assert val_proxy.value == 5


class TestGenerateCipherLogic:
	def test_generate_cipher_success(self, mocker, mock_producer, valid_text_stream):
		producer = mock_producer

		mock_cipher_instance = mocker.Mock(spec=HomophonicCipher)
		mocked_homophonic_cipher = mocker.patch(
			"drive.cipher_producer.HomophonicCipher", return_value=mock_cipher_instance
		)

		cipher = producer.generate_cipher(valid_text_stream)

		mocked_homophonic_cipher.assert_called_once_with(valid_text_stream)

		mock_cipher_instance.generate_key.assert_called_once()
		mock_cipher_instance.encipher.assert_called_once()

		assert cipher == mock_cipher_instance

	def test_generate_cipher_errors(self, mocker, mock_producer, valid_text_stream):
		producer = mock_producer

		mock_log = mocker.patch("drive.cipher_producer.log")

		mocker.patch(
			"drive.cipher_producer.HomophonicCipher",
			side_effect=ValueError("Invalid cipher setup"),
		)

		result = producer.generate_cipher(valid_text_stream)

		assert result is None
		mock_log.error.assert_called()
		assert "Error generating cipher" in mock_log.error.call_args[0][0]

	def test_generate_cipher_unexpected_exception(self, mocker, mock_producer, valid_text_stream):
		producer = mock_producer

		mock_log = mocker.patch("drive.cipher_producer.log")

		mocker.patch(
			"drive.cipher_producer.HomophonicCipher",
			side_effect=Exception("Critical system failure"),
		)

		result = producer.generate_cipher(valid_text_stream)

		assert result is None
		mock_log.error.assert_called()
		log_msg = mock_log.error.call_args[0][0]
		assert "Unexpected cipher generation error" in log_msg
		assert "Critical system failure" in log_msg
