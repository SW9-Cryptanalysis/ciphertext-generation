import pytest
import json
from dataclasses import dataclass

from cipher_generation.cipher_manager import CipherManager
from dataset_stats import DatasetStatsAggregator


@pytest.fixture
def base_config():
	"""Provide a standard configuration dictionary for manager initialization."""
	return {
		"train": {"count": 70, "folder_id": "train_folder"},
		"val": {"count": 30, "folder_id": "val_folder"},
		"metadata": {"folder_id": "metadata_folder", "count": 0},
	}


@pytest.fixture
def mock_mp_manager(mocker):
	"""Patch multiprocessing.Manager to inject standard mocker.Mock queues."""
	mock_manager_cls = mocker.patch("multiprocessing.Manager")
	mock_manager_inst = mock_manager_cls.return_value

	mock_job_queue = mocker.Mock()
	mock_result_queue = mocker.Mock()
	mock_stats_queue = mocker.Mock()

	mock_manager_inst.Queue.side_effect = [
		mock_job_queue,
		mock_result_queue,
		mock_stats_queue,
	]

	return mock_manager_inst, mock_job_queue, mock_result_queue, mock_stats_queue


class StreamSimulator:
	"""A helper to simulate different iterable behaviors for execution testing."""

	def __init__(self, mode: str) -> None:
		"""Initialize the simulator with a specific failure or success mode."""
		self.mode = mode

	def __iter__(self):
		"""Yield items or raise exceptions based on the simulated mode."""
		if self.mode == "normal":
			yield ("train", {"text": "A"})
			yield ("train", {"text": "B"})
			yield ("val", {"text": "C"})
		elif self.mode == "exception":
			raise Exception("Stream Failure")
		elif self.mode == "interrupt":
			raise KeyboardInterrupt()


@dataclass
class ExecuteCase:
	"""Defines the parameters for testing various execution stream outcomes.

	Attributes:
		id (str): The test identifier.
		stream_mode (str): The mode passed to the StreamSimulator.
		expected_log_level (str): The log method expected to be triggered (e.g., info, error).
		expected_log_snippet (str): The text snippet expected within the triggered log.
	"""

	id: str
	stream_mode: str
	expected_log_level: str
	expected_log_snippet: str


execute_cases = [
	ExecuteCase(
		id="success",
		stream_mode="normal",
		expected_log_level="info",
		expected_log_snippet="Stream finished. Fed 3 items.",
	),
	ExecuteCase(
		id="exception",
		stream_mode="exception",
		expected_log_level="error",
		expected_log_snippet="Stream error: Stream Failure",
	),
	ExecuteCase(
		id="interrupt",
		stream_mode="interrupt",
		expected_log_level="warning",
		expected_log_snippet="Job interrupted! Stopping...",
	),
]


class TestCipherManagerInitialization:
	"""Tests covering object initialization and CPU limit logic."""

	def test_initialization(self, mocker, mock_mp_manager, base_config):
		"""Verify the manager sets up attributes and queues correctly."""
		_, mock_job_q, mock_result_q, mock_stats_q = mock_mp_manager
		mocker.patch("os.cpu_count", return_value=6)

		manager = CipherManager(config=base_config, text_stream_source=[])

		assert manager.split_folders == {
			"train": "train_folder",
			"val": "val_folder",
			"metadata": "metadata_folder",
		}
		assert manager.total_count == 100
		assert manager.num_workers == 4

		assert manager.job_queue == mock_job_q
		assert manager.result_queue == mock_result_q
		assert manager.stats_queue == mock_stats_q
		assert isinstance(manager.master_stats, DatasetStatsAggregator)

	def test_initialization_low_cpu(self, mocker, mock_mp_manager, base_config):
		"""Verify the manager falls back to 1 worker if CPU count is extremely low."""
		mocker.patch("os.cpu_count", return_value=2)
		manager = CipherManager(base_config, [])
		assert manager.num_workers == 1


class TestCipherManagerExecution:
	"""Tests covering the execution loop, queue pushing, and logging intervals."""

	@pytest.mark.parametrize("case", execute_cases, ids=lambda c: c.id)
	def test_execute_outcomes(
		self, mocker, mock_mp_manager, base_config, case: ExecuteCase
	):
		"""Verify routing, process orchestration, and handled failures across stream states."""
		_, mock_job_q, mock_result_q, _ = mock_mp_manager

		mock_log = mocker.patch("cipher_generation.cipher_manager.log")
		mocker.patch("os.cpu_count", return_value=4)

		mock_uploader_cls = mocker.patch(
			"cipher_generation.cipher_manager.DriveUploader"
		)
		mock_producer_cls = mocker.patch(
			"cipher_generation.cipher_manager.CipherProducer"
		)

		manager = CipherManager(base_config, StreamSimulator(case.stream_mode))

		mocker.patch.object(
			manager.stats_queue, "get", return_value=DatasetStatsAggregator()
		)

		manager.execute()

		log_method = getattr(mock_log, case.expected_log_level)
		log_found = any(
			case.expected_log_snippet in str(call) for call in log_method.call_args_list
		)
		assert log_found, (
			f"Expected to find '{case.expected_log_snippet}' in {case.expected_log_level} logs."
		)

		assert mock_producer_cls.call_count == 2

		mock_job_q.put.assert_any_call("STOP")
		mock_result_q.put.assert_any_call("STOP")

		mock_uploader_cls.assert_called_once()
		_, kwargs = mock_uploader_cls.call_args
		assert kwargs["upload_queue"] == mock_result_q

	def test_execute_logging_progress(self, mocker, mock_mp_manager):
		"""Verify that progress is logged dynamically at the configured interval."""
		mock_log = mocker.patch("cipher_generation.cipher_manager.log")

		mock_stream = [("train", {"text": "A"}) for _ in range(11)]

		manager = CipherManager(
			{"train": {"folder_id": "dummy", "count": 11}}, mock_stream
		)
		manager._logging_interval = 10

		mocker.patch("cipher_generation.cipher_manager.DriveUploader")
		mocker.patch("cipher_generation.cipher_manager.CipherProducer")
		mocker.patch.object(
			manager.stats_queue, "get", return_value=DatasetStatsAggregator()
		)

		manager.execute()

		mock_log.info.assert_any_call("Fed 10 texts to workers...")

	def test_feeder_stream_respects_total_count(self, mocker, mock_mp_manager):
		"""Verify the feeder stops pulling from the iterable once the target is reached."""
		_, mock_job_q, _, _ = mock_mp_manager

		large_stream = [("train", {"text": f"text_{i}"}) for i in range(10)]
		test_config = {
			"train": {"folder_id": "dummy", "count": 3},
			"metadata": {"folder_id": "dummy", "count": 0},
		}

		manager = CipherManager(test_config, large_stream)
		mock_log = mocker.patch("cipher_generation.cipher_manager.log")

		items_fed = manager._feeder_stream()

		assert items_fed == 3
		assert mock_job_q.put.call_count == 3
		mock_log.info.assert_any_call("Target of 3 reached. Stopping feeder.")


class TestCipherManagerPeakUpload:
	"""Tests covering the final metadata payload generation."""

	def test_manager_queues_peak_value_metadata(self, mocker, mock_mp_manager):
		"""Verify the global stats are properly formatted into a 4-part tuple for the new Uploader."""
		_, _, mock_result_q, _ = mock_mp_manager

		mocker.patch("cipher_generation.cipher_manager.DriveUploader")
		mocker.patch("cipher_generation.cipher_manager.CipherProducer")

		dummy_config = {"train": {"folder_id": "dummy_folder_abc", "count": 1}}
		dummy_stream = [("train", {"text": "hello", "source_id": "1"})]

		manager = CipherManager(
			config=dummy_config, text_stream_source=dummy_stream, num_workers=1
		)

		expected_peak = 2501
		mocker.patch.object(
			DatasetStatsAggregator,
			"global_max_homophones",
			new_callable=mocker.PropertyMock,
			return_value=expected_peak,
		)

		mocker.patch.object(
			manager.stats_queue, "get", return_value=DatasetStatsAggregator()
		)

		manager.execute()

		put_calls = mock_result_q.put.call_args_list
		metadata_payload = put_calls[-2][0][0]

		assert len(metadata_payload) == 4
		split_name, filename, file_bytes, cipher_count = metadata_payload

		assert split_name == "metadata"
		assert filename == "metadata.json"
		assert cipher_count == 0

		payload = json.loads(file_bytes.decode("utf-8"))
		assert payload["max_symbol_id"] == expected_peak
