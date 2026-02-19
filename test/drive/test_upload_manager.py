import pytest
from unittest.mock import call, MagicMock
from drive.cipher_manager import CipherManager


@pytest.fixture
def base_config():
	return {
		"train": {
			"count": 70,
			"folder_id": "train_folder"
		},
		"val": {
			"count": 30,
			"folder_id": "val_folder"
		}
	}


class TestCipherManager:
	
	@pytest.fixture
	def mock_mp_manager(self, mocker):
		mock_manager_cls = mocker.patch("multiprocessing.Manager")
		mock_manager_inst = mock_manager_cls.return_value
		
		mock_job_queue = MagicMock(name="job_queue")
		mock_result_queue = MagicMock(name="result_queue")
		
		mock_manager_inst.Queue.side_effect = [mock_job_queue, mock_result_queue]
		
		return mock_manager_inst, mock_job_queue, mock_result_queue

	def test_initialization(self, mocker, mock_mp_manager, base_config):
		_, mock_job_q, mock_result_q = mock_mp_manager
		
		mocker.patch("os.cpu_count", return_value=6)

		dummy_stream = []
		manager = CipherManager(
			config=base_config,
			text_stream_source=dummy_stream
		)

		assert manager.split_folders == {"train": "train_folder", "val": "val_folder"}
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
			("val",   {"text": "C"})
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
		
		mock_result_q.put.assert_called_once_with("STOP")
		
		mock_uploader.join.assert_called_once()

	def test_execute_handles_stream_exception(self, mocker, mock_mp_manager, base_config):
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

	def test_execute_with_empty_stream(self, mocker, mock_mp_manager, base_config):
		_, mock_job_q, mock_result_q = mock_mp_manager
		
		mock_stream = []
		
		mocker.patch("os.cpu_count", return_value=3)
		mocker.patch("drive.cipher_manager.DriveUploader")
		mocker.patch("drive.cipher_manager.CipherProducer")

		# Set total count to 0 dynamically for this specific test
		empty_config = {"train": {"count": 0, "folder_id": "test"}}
		manager = CipherManager(empty_config, mock_stream)
		manager.execute()

		assert mock_job_q.put.call_count == 1
		mock_job_q.put.assert_called_once_with("STOP")