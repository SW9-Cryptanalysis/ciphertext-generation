import pytest
from unittest.mock import call, MagicMock
import multiprocessing as mp
from drive.cipher_manager import CipherManager

class TestCipherManager:
    def test_initialization(self, mocker):
        mock_manager_cls = mocker.patch("multiprocessing.Manager")
        mock_manager_instance = mock_manager_cls.return_value
        mock_queue = mocker.Mock()
        mock_manager_instance.Queue.return_value = mock_queue

        mocker.patch("os.cpu_count", return_value=4)

        folder_id = "test_folder_id"
        manager = CipherManager(folder_id)

        assert manager.folder_id == folder_id
        assert manager.num_producers == 4
        assert manager.queue == mock_queue
        mock_manager_cls.assert_called_once()
        mock_manager_instance.Queue.assert_called_once()

    def test_divide_workload_even_split(self, mocker):
        mocker.patch("multiprocessing.Manager")
        mocker.patch("os.cpu_count", return_value=4)
        
        manager = CipherManager("id")
        manager.TOTAL_CIPHERS = 100
        
        workload = manager._divide_workload()
        
        assert len(workload) == 4
        assert workload == [(0, 25), (25, 25), (50, 25), (75, 25)]

    def test_divide_workload_uneven_split(self, mocker):
        mocker.patch("multiprocessing.Manager")
        mocker.patch("os.cpu_count", return_value=3)
        
        manager = CipherManager("id")
        manager.TOTAL_CIPHERS = 100
        
        workload = manager._divide_workload()
        
        assert len(workload) == 3
        assert workload == [(0, 33), (33, 33), (66, 34)]

    def test_execute_flow(self, mocker):
        mock_manager_cls = mocker.patch("multiprocessing.Manager")
        mock_queue = mocker.Mock()
        mock_manager_cls.return_value.Queue.return_value = mock_queue

        mock_cpu_count = mocker.patch("os.cpu_count", return_value=2)
        
        mock_consumer_cls = mocker.patch("drive.cipher_manager.DriveUploader")
        mock_consumer = mock_consumer_cls.return_value
        
        mock_producer_cls = mocker.patch("drive.cipher_manager.CipherProducer")
        mock_producer_1 = mocker.Mock()
        mock_producer_2 = mocker.Mock()
        mock_producer_cls.side_effect = [mock_producer_1, mock_producer_2]

        mock_log = mocker.patch("drive.cipher_manager.log")

        manager = CipherManager("test_folder")
        manager.TOTAL_CIPHERS = 100 

        manager.execute()

        mock_consumer_cls.assert_called_once()
        mock_consumer.start.assert_called_once()

        assert mock_producer_cls.call_count == 2
        mock_producer_1.start.assert_called_once()
        mock_producer_2.start.assert_called_once()

        mock_producer_1.join.assert_called_once()
        mock_producer_2.join.assert_called_once()

        assert mock_queue.put.call_count == 2
        mock_queue.put.assert_has_calls([call("STOP"), call("STOP")])

        mock_consumer.join.assert_called_once()

        assert "Starting cipher generation job" in mock_log.info.call_args_list[0][0][0]
        assert "All processes complete" in mock_log.info.call_args_list[-1][0][0]

    def test_execute_with_zero_total_ciphers(self, mocker):
        mocker.patch("multiprocessing.Manager")
        mocker.patch("os.cpu_count", return_value=2)
        mock_consumer_cls = mocker.patch("drive.cipher_manager.DriveUploader")
        mock_producer_cls = mocker.patch("drive.cipher_manager.CipherProducer")
        
        manager = CipherManager("id")
        manager.TOTAL_CIPHERS = 0
        
        manager.execute()
        
        mock_producer_cls.assert_not_called()