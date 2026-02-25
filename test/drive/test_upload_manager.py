import pytest
from unittest.mock import call
from drive.cipher_manager import CipherManager
import json


@pytest.fixture
def base_config():
	return {
		"train": {"count": 70, "folder_id": "train_folder"},
		"val": {"count": 30, "folder_id": "val_folder"},
		"metadata": {"folder_id": "metadata_folder", "count": 0},
	}


class TestCipherManager:
	@pytest.fixture
	def mock_mp_manager(self, mocker, mock_queue, mock_tracker):
		"""
		Patches mp.Manager so CipherManager doesn't spin up real processes,
		but injects the shared conftest fixtures for standard queue/tracker behavior.
		"""
		mock_manager_cls = mocker.patch("multiprocessing.Manager")
		mock_manager_inst = mock_manager_cls.return_value

		# Use the conftest tracker for the max_symbol_id
		tracker_mock, _ = mock_tracker
		mock_manager_inst.Value.return_value = tracker_mock

		# Use two instances of the conftest mock_queue
		mock_job_queue = mocker.MagicMock(wraps=mock_queue)
		mock_result_queue = mocker.MagicMock(wraps=mock_queue)

		# Ensure we can assert calls on them later
		mock_manager_inst.Queue.side_effect = [mock_job_queue, mock_result_queue]

		return mock_manager_inst, mock_job_queue, mock_result_queue

	def test_initialization(self, mocker, mock_mp_manager, base_config):
		_, mock_job_q, mock_result_q = mock_mp_manager

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

	def test_initialization_low_cpu(self, mocker, mock_mp_manager, base_config):
		mocker.patch("os.cpu_count", return_value=2)
		manager = CipherManager(base_config, [])
		assert manager.num_workers == 1

	def test_execute_flow(self, mocker, mock_mp_manager, base_config):
		_, mock_job_q, mock_result_q = mock_mp_manager

		mocker.patch("drive.drive_uploader.BatchState")

		mock_stream = [
			("train", {"text": "A"}),
			("train", {"text": "B"}),
			("val", {"text": "C"}),
		]

		mock_uploader_cls = mocker.patch("drive.cipher_manager.DriveUploader")
		mock_uploader = mock_uploader_cls.return_value

		mock_producer_cls = mocker.patch("drive.cipher_manager.CipherProducer")
		mock_producer = mock_producer_cls.return_value

		mocker.patch("os.cpu_count", return_value=4)

		manager = CipherManager(base_config, mock_stream)
		manager.execute()

		mock_uploader_cls.assert_called_once()
		mock_uploader.start.assert_called_once()

		assert mock_producer_cls.call_count == 2
		assert mock_producer.start.call_count == 2

		expected_calls = [
			call(("train", {"text": "A"})),
			call(("train", {"text": "B"})),
			call(("val", {"text": "C"})),
			call("STOP"),
			call("STOP"),
		]
		mock_job_q.put.assert_has_calls(expected_calls, any_order=False)

		assert mock_producer.join.call_count == 2
		assert mock_result_q.put.call_count == 2

		mock_result_q.put.assert_has_calls(
			[
				call(("metadata", "metadata.json", b'{"max_symbol_id": 0}')),
				call("STOP"),
			],
			any_order=False,
		)

		mock_uploader.join.assert_called_once()

	def test_execute_handles_stream_exception(
		self, mocker, mock_mp_manager, base_config
	):
		_, mock_job_q, mock_result_q = mock_mp_manager
		mock_log = mocker.patch("drive.cipher_manager.log")

		mock_stream = mocker.MagicMock()
		mock_stream.__iter__.side_effect = Exception("Stream Failure")

		mocker.patch("os.cpu_count", return_value=3)
		mocker.patch("drive.cipher_manager.DriveUploader")
		mocker.patch("drive.cipher_manager.CipherProducer")

		manager = CipherManager(base_config, mock_stream)
		manager.execute()

		mock_log.error.assert_called_once()
		assert "Stream Failure" in str(mock_log.error.call_args)

		mock_job_q.put.assert_called_with("STOP")
		mock_result_q.put.assert_called_with("STOP")

	def test_execute_logging_progress(self, mocker, mock_mp_manager):
		"""Line 95: Triggers the progress log every 1000 items."""
		_, mock_job_q, _ = mock_mp_manager
		mock_log = mocker.patch("drive.cipher_manager.log")

		# Create a stream of 1001 items to trigger the log at 1000
		mock_stream = [("train", {"text": "A"}) for _ in range(1001)]

		manager = CipherManager(
			{"train": {"folder_id": "train_folder", "count": 1001}}, mock_stream
		)

		mocker.patch("drive.cipher_manager.DriveUploader.start")
		mocker.patch("drive.cipher_manager.DriveUploader.join")
		mocker.patch("drive.cipher_manager.CipherProducer.start")
		mocker.patch("drive.cipher_manager.CipherProducer.join")

		manager.execute()

		mock_log.info.assert_any_call("Fed 1000 texts to workers...")

	def test_execute_keyboard_interrupt(self, mocker, mock_mp_manager, base_config):
		"""Line 98: Triggers the KeyboardInterrupt warning block."""
		_, mock_job_q, _ = mock_mp_manager
		mock_log = mocker.patch("drive.cipher_manager.log")

		mock_stream = mocker.MagicMock()
		mock_stream.__iter__.side_effect = KeyboardInterrupt()

		manager = CipherManager(base_config, mock_stream)

		mocker.patch("drive.cipher_manager.DriveUploader")
		mocker.patch("drive.cipher_manager.CipherProducer")

		manager.execute()

		mock_log.warning.assert_called_with("Job interrupted! Stopping...")
		assert mock_job_q.put.called
  
	def test_feeder_stream_respects_total_count(self, mocker, mock_mp_manager):
			_, mock_job_q, _ = mock_mp_manager

			# Stream of 10 items
			large_stream = [("train", {"text": f"text_{i}"}) for i in range(10)]

			# Config requesting exactly 3 items
			test_config = {
				"train": {"folder_id": "dummy", "count": 3},
				"metadata": {"folder_id": "dummy", "count": 0}
			}
			
			manager = CipherManager(test_config, large_stream)
			mock_log = mocker.patch("drive.cipher_manager.log")
			
			items_fed = manager._feeder_stream()
			
			assert items_fed == 3
			assert mock_job_q.put.call_count == 3
			mock_log.info.assert_any_call("Target of 3 reached. Stopping feeder.")


class TestCipherManagerPeakUpload:
	def test_manager_queues_peak_value_metadata(self, mocker):
		"""Verifies the max_symbol_id is formatted and queued before the sentinel."""

		mocker.patch("drive.cipher_manager.DriveUploader")
		mocker.patch("drive.cipher_manager.CipherProducer")

		dummy_config = {"train": {"folder_id": "dummy_folder_abc", "count": 1}}
		dummy_stream = [
			(
				"train",
				{"text": "hello", "source_id": "1", "source_name": "x", "length": 5},
			)
		]

		manager = CipherManager(
			config=dummy_config, text_stream_source=dummy_stream, num_workers=1
		)

		# 4. Simulate the workers finding a high homophone count
		expected_peak = 2501
		manager.max_symbol_id.value = expected_peak

		manager.execute()

		queued_items = []
		while not manager.result_queue.empty():
			queued_items.append(manager.result_queue.get())

		assert queued_items[-1] == CipherManager.SENTINEL

		metadata_task = queued_items[-2]
		split_name, filename, file_bytes = metadata_task

		assert split_name == "metadata"
		assert filename == "metadata.json"

		payload = json.loads(file_bytes.decode("utf-8"))
		assert payload["max_symbol_id"] == expected_peak
