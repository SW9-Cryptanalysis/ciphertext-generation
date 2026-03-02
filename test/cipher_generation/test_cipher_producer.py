import pytest
import os
import queue
import multiprocessing as mp
from dataclasses import dataclass

from cipher_generation.cipher_producer import CipherProducer
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from dataset_stats import DatasetStatsAggregator


class MockCipher(SubstitutionCipher):
	def __init__(self, *args, **kwargs):
		self.plaintext = "a" * 500
		self.difficulty = 10
		self.num_symbols = 3
		self.genres = ["Sci-Fi & Fantasy"]

	def generate_key(self):
		self.key = {"a": ["1"], "b": ["2"], "c": ["3"]}
		return self.key

	def encipher(self):
		self.ciphertext = "1 2 3"
		self.num_symbols = 3
		return self.ciphertext


@pytest.fixture
def mock_cipher_data():
	mock_json = '{"key": "value"}'
	mock_bytes = mock_json.encode("utf-8")
	return mock_json, mock_bytes


@dataclass
class ProducerContext:
	input_q: mp.Queue
	output_q: mp.Queue
	stats_q: mp.Queue
	cipher_data: tuple


@pytest.fixture
def producer_ctx(queue_factory, mock_cipher_data):
	return ProducerContext(
		queue_factory(), queue_factory(), queue_factory(), mock_cipher_data
	)


@pytest.fixture
def mock_producer(queue_factory):
	return CipherProducer(
		queues=(queue_factory(), queue_factory(), queue_factory()), name="TestProducer"
	)


class TestCipherProducerRun:
	def test_successful_run(self, mocker, producer_ctx, valid_text_stream):
		input_q = producer_ctx.input_q
		output_q = producer_ctx.output_q
		stats_q = producer_ctx.stats_q

		input_q.put(("train", valid_text_stream))
		input_q.put("STOP")

		mock_cipher_return = MockCipher()

		mock_generate_cipher = mocker.patch.object(
			CipherProducer, "generate_cipher", return_value=mock_cipher_return
		)

		mock_create_json = mocker.patch(
			"cipher_generation.cipher_producer.create_cipher_json",
			return_value=producer_ctx.cipher_data,
		)

		producer = CipherProducer(
			queues=(input_q, output_q, stats_q),
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

		try:
			stats_obj = stats_q.get(timeout=0.1)
			assert isinstance(stats_obj, DatasetStatsAggregator)
			assert stats_obj.splits["train"].total_count == 1
		except queue.Empty:
			pytest.fail("Stats queue was empty before receiving aggregator.")

	def test_stop_signal(self, queue_factory, caplog):
		input_q, output_q, stats_q = queue_factory(), queue_factory(), queue_factory()
		input_q.put("STOP")

		producer = CipherProducer(
			queues=(input_q, output_q, stats_q), name="TestProducer"
		)

		producer.run()

		assert output_q.empty()
		assert not stats_q.empty()

	def test_generation_runtime_failure(self, mocker, queue_factory):
		input_q, output_q, stats_q = queue_factory(), queue_factory(), queue_factory()

		input_q.put(("val", {"text": "fail", "source_id": "1"}))
		input_q.put("STOP")

		mock_log = mocker.patch("cipher_generation.cipher_producer.log")

		mocker.patch.object(CipherProducer, "generate_cipher", return_value=None)

		producer = CipherProducer(
			queues=(input_q, output_q, stats_q), name="TestProducer"
		)

		producer.run()

		assert output_q.empty()
		mock_log.info.assert_any_call("TestProducer finished generation.")

	def test_run_handles_queue_empty_and_retries(self, mocker):
		mock_input_q = mocker.Mock()
		mock_output_q = mocker.Mock()
		mock_stats_q = mocker.Mock()

		mock_input_q.get.side_effect = [queue.Empty, "STOP"]

		producer = CipherProducer(
			queues=(mock_input_q, mock_output_q, mock_stats_q),
			name="TestProducer",
		)

		producer.run()

		assert mock_input_q.get.call_count == 2
		mock_stats_q.put.assert_called_once()

	def test_run_handles_unexpected_loop_exception(self, mocker):
		mock_input_q = mocker.Mock()
		mock_output_q = mocker.Mock()
		mock_stats_q = mocker.Mock()
		mock_log = mocker.patch("cipher_generation.cipher_producer.log")

		mock_input_q.get.side_effect = [Exception("Queue connection lost"), "STOP"]

		producer = CipherProducer(
			queues=(mock_input_q, mock_output_q, mock_stats_q),
			name="TestProducer",
		)

		producer.run()

		mock_log.error.assert_called()
		assert "Queue connection lost" in mock_log.error.call_args[0][0]
		assert mock_input_q.get.call_count == 2
		mock_stats_q.put.assert_called_once()


class TestGenerateCipherLogic:
	def test_generate_cipher_success(self, mocker, mock_producer, valid_text_stream):
		producer = mock_producer

		mock_cipher_instance = mocker.Mock(spec=HomophonicCipher)
		mocked_homophonic_cipher = mocker.patch(
			"cipher_generation.cipher_producer.HomophonicCipher",
			return_value=mock_cipher_instance,
		)

		cipher = producer.generate_cipher(valid_text_stream)

		mocked_homophonic_cipher.assert_called_once_with(valid_text_stream)

		mock_cipher_instance.generate_key.assert_called_once()
		mock_cipher_instance.encipher.assert_called_once()

		assert cipher == mock_cipher_instance

	def test_generate_cipher_errors(self, mocker, mock_producer, valid_text_stream):
		producer = mock_producer

		mock_log = mocker.patch("cipher_generation.cipher_producer.log")

		mocker.patch(
			"cipher_generation.cipher_producer.HomophonicCipher",
			side_effect=ValueError("Invalid cipher setup"),
		)

		result = producer.generate_cipher(valid_text_stream)

		assert result is None
		mock_log.error.assert_called()
		assert "Error generating cipher" in mock_log.error.call_args[0][0]

	def test_generate_cipher_unexpected_exception(
		self, mocker, mock_producer, valid_text_stream
	):
		producer = mock_producer

		mock_log = mocker.patch("cipher_generation.cipher_producer.log")

		mocker.patch(
			"cipher_generation.cipher_producer.HomophonicCipher",
			side_effect=Exception("Critical system failure"),
		)

		result = producer.generate_cipher(valid_text_stream)

		assert result is None
		mock_log.error.assert_called()
		log_msg = mock_log.error.call_args[0][0]
		assert "Unexpected cipher generation error" in log_msg
		assert "Critical system failure" in log_msg
