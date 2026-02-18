import pytest
from unittest.mock import call, MagicMock
from drive.cipher_manager import CipherManager

class TestCipherManager:
    
    @pytest.fixture
    def mock_mp_manager(self, mocker):
        """Mocks multiprocessing.Manager and its queues."""
        mock_manager_cls = mocker.patch("multiprocessing.Manager")
        mock_manager_inst = mock_manager_cls.return_value
        
        # Create distinct mocks for job and result queues
        mock_job_queue = MagicMock(name="job_queue")
        mock_result_queue = MagicMock(name="result_queue")
        
        # Side effect to return distinct queues based on order of creation or just return same
        # logic: The class calls Queue(maxsize) first (job), then Queue() (result).
        mock_manager_inst.Queue.side_effect = [mock_job_queue, mock_result_queue]
        
        return mock_manager_inst, mock_job_queue, mock_result_queue

    def test_initialization(self, mocker, mock_mp_manager):
        _, mock_job_q, mock_result_q = mock_mp_manager
        
        # Mock CPU count to test the 'max(1, cpu - 2)' logic
        # Case 1: High CPU count (6) -> expect 4 workers
        mocker.patch("os.cpu_count", return_value=6)

        dummy_stream = []
        manager = CipherManager(
            folder_id="test_folder",
            text_stream_source=dummy_stream,
            total_count=100
        )

        assert manager.folder_id == "test_folder"
        assert manager.total_count == 100
        assert manager.num_workers == 4 # 6 - 2
        
        # Verify queues are assigned
        assert manager.job_queue == mock_job_q
        assert manager.result_queue == mock_result_q

    def test_initialization_low_cpu(self, mocker, mock_mp_manager):
        """Test that we default to at least 1 worker even on low CPU counts."""
        mocker.patch("os.cpu_count", return_value=2) # 2 - 2 = 0, should become 1
        
        manager = CipherManager("id", [], 100)
        assert manager.num_workers == 1

    def test_execute_flow(self, mocker, mock_mp_manager):
        _, mock_job_q, mock_result_q = mock_mp_manager
        
        # 1. Setup Data
        # Stream yields (split, data_dict)
        mock_stream = [
            ("train", {"text": "A"}), 
            ("train", {"text": "B"}),
            ("val",   {"text": "C"})
        ]
        
        # 2. Mock Workers/Uploader
        mock_uploader_cls = mocker.patch("drive.cipher_manager.DriveUploader")
        mock_uploader = mock_uploader_cls.return_value
        
        mock_producer_cls = mocker.patch("drive.cipher_manager.CipherProducer")
        mock_producer = mock_producer_cls.return_value
        
        # Mock CPU to control number of loop iterations
        mocker.patch("os.cpu_count", return_value=4) # Results in 2 workers (4-2)

        # 3. Initialize
        manager = CipherManager("folder", mock_stream, total_count=3)
        
        # 4. Execute
        manager.execute()

        # --- Assertions ---

        # A. Uploader started
        mock_uploader_cls.assert_called_once()
        mock_uploader.start.assert_called_once()

        # B. Workers started (2 workers expected)
        assert mock_producer_cls.call_count == 2
        assert mock_producer.start.call_count == 2

        # C. Feeder Loop (Job Queue)
        # Expect 3 calls for data + 2 calls for Sentinels (STOP)
        # Data put into queue should be the text_dict (index 1 of stream tuple)
        expected_calls = [
            call({"text": "A"}),
            call({"text": "B"}),
            call({"text": "C"}),
            call("STOP"), # For worker 1
            call("STOP"), # For worker 2
        ]
        mock_job_q.put.assert_has_calls(expected_calls, any_order=False)

        # D. Teardown
        # Workers joined
        assert mock_producer.join.call_count == 2
        
        # Result queue gets STOP
        mock_result_q.put.assert_called_once_with("STOP")
        
        # Uploader joined
        mock_uploader.join.assert_called_once()

    def test_execute_handles_stream_exception(self, mocker, mock_mp_manager):
        """Ensure cleanup happens even if the stream crashes."""
        _, mock_job_q, mock_result_q = mock_mp_manager
        mock_log = mocker.patch("drive.cipher_manager.log")

        # FIX: Use MagicMock so __iter__ exists and can be configured
        mock_stream = mocker.MagicMock()
        mock_stream.__iter__.side_effect = Exception("Stream Failure")

        # Mock CPU count to 3 -> 1 worker
        mocker.patch("os.cpu_count", return_value=3)
        
        mocker.patch("drive.cipher_manager.DriveUploader")
        mocker.patch("drive.cipher_manager.CipherProducer")

        manager = CipherManager("folder", mock_stream, 100)
        manager.execute()

        # Assert Error Logged
        mock_log.error.assert_called_once()
        # Verify the exception message is captured
        assert "Stream Failure" in str(mock_log.error.call_args)

        # Assert Cleanup STILL happened
        mock_job_q.put.assert_called_with("STOP")
        mock_result_q.put.assert_called_with("STOP")

    def test_execute_with_empty_stream(self, mocker, mock_mp_manager):
        _, mock_job_q, mock_result_q = mock_mp_manager
        
        # Empty stream
        mock_stream = []
        
        mocker.patch("os.cpu_count", return_value=3) # 1 worker
        mocker.patch("drive.cipher_manager.DriveUploader")
        mocker.patch("drive.cipher_manager.CipherProducer")

        manager = CipherManager("folder", mock_stream, 0)
        manager.execute()

        # Job queue should ONLY receive STOP (no data calls)
        assert mock_job_q.put.call_count == 1
        mock_job_q.put.assert_called_once_with("STOP")