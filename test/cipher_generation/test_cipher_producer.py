import pytest
import queue
import os
from dataclasses import dataclass

from encipherment.cipher import HomophonicCipher
from cipher_generation.cipher_producer import CipherProducer, ProducerConfig


@pytest.fixture
def valid_text_stream():
	"""Provide a standardized mock text stream dictionary."""
	return {"text": "mock_text", "source_id": "1"}


@pytest.fixture
def mock_cipher(mocker):
	"""Mock a SubstitutionCipher with a valid __json__ return value."""
	mock = mocker.Mock()
	mock.plaintext = "a" * 10
	mock.difficulty = 5
	mock.num_symbols = 3
	mock.genres = ["Sci-Fi"]
	mock.__json__ = mocker.Mock(return_value={"mock_key": "mock_value"})
	return mock


@pytest.fixture
def producer(mocker, tmp_path):
	"""Provide a standard CipherProducer configured with a small batch size of 2.

	Uses pytest's tmp_path to prevent writing actual files to the project
	directory during testing.
	"""
	mock_input_queue = mocker.Mock()
	mock_output_queue = mocker.Mock()
	mock_stats_queue = mocker.Mock()

	config = ProducerConfig(
		input_queue=mock_input_queue,
		output_queue=mock_output_queue,
		stats_queue=mock_stats_queue,
		batch_size=2,
		temp_dir=tmp_path / "temp_ciphers",
	)

	p = CipherProducer(
		config=config,
		name="TestProducer",
	)
	# Redirect file operations to the isolated test directory
	p.temp_dir = tmp_path / "temp_ciphers"
	return p


@dataclass
class CipherErrorCase:
	"""Defines the parameters for testing various cipher generation failures.

	Attributes:
		id (str): The test case identifier.
		exception (Exception): The exception raised during generation.
		expected_log (str): The expected error log message.
	"""

	id: str
	exception: Exception
	expected_log: str


cipher_error_cases = [
	CipherErrorCase(
		id="value_error",
		exception=ValueError("Invalid cipher setup"),
		expected_log="Error generating cipher: Invalid cipher setup",
	),
	CipherErrorCase(
		id="unexpected_exception",
		exception=Exception("Critical system failure"),
		expected_log="Unexpected cipher generation error: Critical system failure",
	),
]


class TestCipherProducerRunLoop:
	"""Tests covering the batching loop, disk writing, and cleanup logic."""

	def test_successful_train_batch_zip(
		self,
		mocker,
		producer,
		valid_text_stream,
		mock_cipher,
	):
		"""Verify the producer streams to disk and zips exactly at the batch size."""
		producer.input_queue.get.side_effect = [
			("train", valid_text_stream),
			("train", valid_text_stream),
			"STOP",
		]

		mocker.patch.object(producer, "generate_cipher", return_value=mock_cipher)

		producer.run()

		# Output queue should receive the zipped train file
		assert producer.output_queue.put.call_count == 1

		call_args = producer.output_queue.put.call_args[0][0]
		split, zip_filepath, archive_name, cipher_count = call_args

		assert split == "train"
		assert archive_name.startswith("batch_train_")
		assert archive_name.endswith(".zip")
		assert cipher_count == 2

		# Verify the zip file exists on disk and the raw file was deleted
		assert os.path.exists(zip_filepath)
		assert not os.path.exists(zip_filepath.with_suffix(".jsonl"))

	def test_cleanup_orphan_train_batch(
		self,
		mocker,
		producer,
		valid_text_stream,
		mock_cipher,
	):
		"""Verify that STOP forces a zip of an incomplete train batch."""
		producer.input_queue.get.side_effect = [("train", valid_text_stream), "STOP"]
		mocker.patch.object(producer, "generate_cipher", return_value=mock_cipher)

		producer.run()

		assert producer.output_queue.put.call_count == 1
		call_args = producer.output_queue.put.call_args[0][0]
		split, zip_filepath, archive_name, cipher_count = call_args

		assert split == "train"
		assert archive_name.endswith(".zip")
		assert cipher_count == 1
		assert os.path.exists(zip_filepath)

	def test_cleanup_val_test_merge_signal(
		self,
		mocker,
		producer,
		valid_text_stream,
		mock_cipher,
	):
		"""Verify that val and test splits close cleanly and send the MERGE signal."""
		producer.input_queue.get.side_effect = [
			("val", valid_text_stream),
			("test", valid_text_stream),
			"STOP",
		]
		mocker.patch.object(producer, "generate_cipher", return_value=mock_cipher)

		producer.run()

		# Should put two MERGE signals into the output queue (one for val, one for test)
		assert producer.output_queue.put.call_count == 2

		val_call_args = producer.output_queue.put.call_args_list[0][0][0]
		signal, split, filepath, count = val_call_args

		assert signal == "MERGE"
		assert split == "val"
		assert filepath.with_suffix(".jsonl")
		assert count == 1

		# Ensure the raw JSONL file is left intact for the Uploader to merge
		assert os.path.exists(filepath)

	def test_empty_queue_timeout(self, producer):
		"""Verify the producer survives queue timeouts and continues listening."""
		producer.input_queue.get.side_effect = [queue.Empty, queue.Empty, "STOP"]

		producer.run()

		assert producer.input_queue.get.call_count == 3

	def test_unexpected_queue_exception(self, mocker, producer):
		"""Verify the producer logs unexpected queue failures and continues listening."""
		mock_log = mocker.patch("cipher_generation.cipher_producer.log")
		producer.input_queue.get.side_effect = [Exception("Queue disconnect"), "STOP"]

		producer.run()

		mock_log.error.assert_called_once()
		assert "Queue disconnect" in mock_log.error.call_args[0][0]
		assert producer.input_queue.get.call_count == 2

	def test_run_skips_invalid_cipher(self, mocker, producer, valid_text_stream):
		"""Verify the loop skips to the next item if cipher generation returns None."""
		producer.input_queue.get.side_effect = [("train", valid_text_stream), "STOP"]
		mocker.patch.object(producer, "generate_cipher", return_value=None)

		producer.run()

		assert producer.input_queue.get.call_count == 2
		producer.output_queue.put.assert_not_called()


class TestGenerateCipherLogic:
	"""Tests covering the internal instantiation and error handling of HomophonicCipher."""

	def test_generate_cipher_success(self, mocker, producer, valid_text_stream):
		"""Verify the cipher is instantiated, generated, and enciphered correctly."""
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

	@pytest.mark.parametrize("case", cipher_error_cases, ids=lambda c: c.id)
	def test_generate_cipher_errors(
		self, mocker, producer, valid_text_stream, case: CipherErrorCase
	):
		"""Verify that cipher generation failures are caught and logged gracefully."""
		mock_log = mocker.patch("cipher_generation.cipher_producer.log")

		mocker.patch(
			"cipher_generation.cipher_producer.HomophonicCipher",
			side_effect=case.exception,
		)

		result = producer.generate_cipher(valid_text_stream)

		assert result is None
		mock_log.error.assert_called_once()
		assert case.expected_log in mock_log.error.call_args[0][0]
