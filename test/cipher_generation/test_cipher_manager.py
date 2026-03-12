import pytest
import json
import os
from dataclasses import dataclass
from unittest.mock import MagicMock
from pathlib import Path

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
    """Patch multiprocessing.Queue and RLock to inject mocks."""
    mock_queue_cls = mocker.patch("multiprocessing.Queue")

    mock_job_queue = mocker.Mock()
    mock_result_queue = mocker.Mock()
    mock_stats_queue = mocker.Mock()

    mock_queue_cls.side_effect = [
        mock_job_queue,
        mock_result_queue,
        mock_stats_queue,
    ]
    
    mocker.patch("multiprocessing.RLock", return_value=mocker.Mock())

    return mock_queue_cls, mock_job_queue, mock_result_queue, mock_stats_queue


class StreamSimulator:
    """A helper to simulate different iterable behaviors for execution testing."""

    def __init__(self, mode: str) -> None:
        self.mode = mode

    def __iter__(self):
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

    def test_initialization(self, mocker, mock_mp_manager, base_config):
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
        mocker.patch("os.cpu_count", return_value=2)
        manager = CipherManager(base_config, [])
        assert manager.num_workers == 1


class TestCipherManagerExecution:

    @pytest.mark.parametrize("case", execute_cases, ids=lambda c: c.id)
    def test_execute_outcomes(
        self, mocker, mock_mp_manager, base_config, case: ExecuteCase
    ):
        _, mock_job_q, mock_result_q, _ = mock_mp_manager

        mock_log = mocker.patch("cipher_generation.cipher_manager.log")
        mocker.patch("os.cpu_count", return_value=4)

        mock_uploader_cls = mocker.patch("cipher_generation.cipher_manager.DriveUploader")
        mock_producer_cls = mocker.patch("cipher_generation.cipher_manager.CipherProducer")
        
        # FIX: Patch the global tqdm class
        mock_pbar = MagicMock()
        mock_pbar.__enter__.return_value = mock_pbar
        mocker.patch("tqdm.tqdm", return_value=mock_pbar)

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
        assert "tqdm_lock" in kwargs["config"].__dict__

    def test_execute_logging_progress(self, mocker, mock_mp_manager):
        mock_log = mocker.patch("cipher_generation.cipher_manager.log")
        
        # FIX: Patch the global tqdm class
        mock_pbar = MagicMock()
        mock_pbar.__enter__.return_value = mock_pbar
        mocker.patch("tqdm.tqdm", return_value=mock_pbar)

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
        mock_log.debug.assert_any_call("Crossed 10 texts milestone...")

    def test_feeder_stream_respects_total_count(self, mocker, mock_mp_manager):
        _, mock_job_q, _, _ = mock_mp_manager

        large_stream = [("train", {"text": f"text_{i}"}) for i in range(10)]
        test_config = {
            "train": {"folder_id": "dummy", "count": 3},
            "metadata": {"folder_id": "dummy", "count": 0},
        }

        manager = CipherManager(test_config, large_stream)
        mock_log = mocker.patch("cipher_generation.cipher_manager.log")
        
        # FIX: Patch the global tqdm class
        mock_pbar = MagicMock()
        mock_pbar.__enter__.return_value = mock_pbar
        mocker.patch("tqdm.tqdm", return_value=mock_pbar)

        mock_lock = mocker.Mock()
        items_fed = manager._feeder_stream(mock_lock)

        assert items_fed == 3
        assert mock_job_q.put.call_count == 3
        mock_log.info.assert_any_call("Target of 3 reached. Stopping feeder.")


class TestCipherManagerPeakUpload:

    def test_manager_writes_and_queues_metadata(self, mocker, mock_mp_manager, tmp_path):
        _, _, mock_result_q, _ = mock_mp_manager

        mocker.patch("cipher_generation.cipher_manager.DriveUploader")
        mocker.patch("cipher_generation.cipher_manager.CipherProducer")
        
        # FIX: Patch the global tqdm class
        mock_pbar = MagicMock()
        mock_pbar.__enter__.return_value = mock_pbar
        mocker.patch("tqdm.tqdm", return_value=mock_pbar)
        
        original_join = os.path.join
        def mock_join(*args):
            if args[0] == "temp_ciphers":
                return str(tmp_path / args[1])
            return original_join(*args)
            
        mocker.patch("os.path.join", side_effect=mock_join)

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
        split_name, filepath, filename, cipher_count = metadata_payload

        assert split_name == "metadata"
        assert filename == Path("metadata.json")
        assert cipher_count == 0

        assert os.path.exists(filepath)
        
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
            
        assert payload["max_symbol_id"] == expected_peak