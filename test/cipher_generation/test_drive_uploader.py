import pytest
import queue
import zipfile
import os
from dataclasses import dataclass
from multiprocessing.queues import Queue as MPQueue
from pathlib import Path

from cipher_generation.drive_uploader import DriveUploader, DriveUploaderConfig, Item
from cipher_generation.task import UploadTask

MOCK_SPLIT_FOLDERS = {
    "train": "mock_train_123",
    "val": "mock_val_123",
    "test": "mock_test_123",
    "metadata": "mock_metadata_123",
}
SENTINEL = "STOP"


@pytest.fixture
def mock_queue(mocker):
    """Provide a mock multiprocessing queue."""
    return mocker.Mock(spec=MPQueue)


@pytest.fixture
def mock_tqdm_lock(mocker):
    """Provide a mock multiprocessing lock."""
    return mocker.Mock()


@pytest.fixture
def uploader_config(mock_tqdm_lock):
    """Provide a default uploader configuration."""
    return DriveUploaderConfig(
        split_folders=MOCK_SPLIT_FOLDERS,
        total_ciphers=20000,
        tqdm_lock=mock_tqdm_lock,
    )


@pytest.fixture
def uploader(mock_queue, uploader_config):
    """Provide an initialized DriveUploader instance."""
    return DriveUploader(mock_queue, uploader_config, name="TestUploader")


class TestDriveUploaderInitialization:
    """Tests covering object initialization and state."""

    def test_initialization(self, uploader, mock_tqdm_lock):
        """Verify the uploader initializes with the correct configuration."""
        assert uploader.split_folders == MOCK_SPLIT_FOLDERS
        assert uploader.total_ciphers == 20000
        assert uploader.uploaded_count == 0
        assert uploader.tqdm_lock == mock_tqdm_lock

    def test_authenticate_service_success(self, mocker, uploader):
        """Verify successful authentication returns True and sets the drive service."""
        mock_service = mocker.Mock()
        mocker.patch(
            "cipher_generation.drive_uploader.authenticate_drive_terminal",
            return_value=mock_service,
        )

        result = uploader._authenticate_service()

        assert result is True
        assert uploader.drive_service == mock_service

    def test_authenticate_service_failure(self, mocker, uploader):
        """Verify authentication failure catches the exception, logs it, and returns False."""
        mocker.patch(
            "cipher_generation.drive_uploader.authenticate_drive_terminal",
            side_effect=Exception("Network disconnected"),
        )
        mock_log = mocker.patch("cipher_generation.drive_uploader.log")

        result = uploader._authenticate_service()

        assert result is False
        assert uploader.drive_service is None

        mock_log.critical.assert_called_once()
        assert (
            "Error authenticating drive service: Network disconnected"
            in mock_log.critical.call_args[0][0]
        )
        assert mock_log.critical.call_args[1].get("exc_info") is True


class TestDriveUploaderRunLoop:
    """Tests covering the main execution loop, queue pulling, and lock setting."""

    def test_successful_run_loop_and_merge(self, mocker, uploader, mock_queue):
        """Verify normal files upload, val/test files hoard, and SENTINEL triggers merge."""
        mocker.patch.object(uploader, "_authenticate_service", return_value=True)
        mock_upload = mocker.patch.object(uploader, "_upload_file")
        mock_merge = mocker.patch.object(uploader, "_merge_and_upload")

        mock_pbar = mocker.MagicMock()
        mock_pbar.__enter__.return_value = mock_pbar
        mocker.patch("cipher_generation.drive_uploader.tqdm", return_value=mock_pbar)

        mock_tqdm_set_lock = mocker.patch(
            "cipher_generation.drive_uploader.tqdm.set_lock"
        )

        # Inject actual UploadTask dataclasses instead of tuples
        train_task = UploadTask(
            filepath=Path("path/batch_train_1.zip"),
            filename=Path("batch_train_1.zip"),
            cipher_count=10000,
            split="train",
        )
        val_task = UploadTask(
            filepath=Path("path/val_raw.jsonl"),
            filename=Path("val_raw.jsonl"),
            cipher_count=5000,
            split="val",
        )
        test_task = UploadTask(
            filepath=Path("path/test_raw.jsonl"),
            filename=Path("test_raw.jsonl"),
            cipher_count=5000,
            split="test",
        )

        mock_queue.get.side_effect = [train_task, val_task, test_task, SENTINEL]

        uploader.run()

        mock_tqdm_set_lock.assert_called_once_with(uploader.tqdm_lock)

        # Train task should be immediately uploaded
        assert mock_upload.call_count == 1
        uploaded_item = mock_upload.call_args_list[0][0][0]
        assert uploaded_item.split == "train"

        # Val and Test should be hoarded and trigger _merge_and_upload on STOP
        assert mock_merge.call_count == 2
        val_merge_args = mock_merge.call_args_list[0][0]
        test_merge_args = mock_merge.call_args_list[1][0]

        assert val_merge_args[0] == "val"
        assert val_merge_args[1] == [(Path("path/val_raw.jsonl"), 5000)]
        assert test_merge_args[0] == "test"
        assert test_merge_args[1] == [(Path("path/test_raw.jsonl"), 5000)]

    def test_empty_queue_timeout_refreshes_pbar(self, mocker, uploader, mock_queue):
        """Verify empty queues catch the timeout and force a pbar refresh."""
        mocker.patch.object(uploader, "_authenticate_service", return_value=True)
        mock_upload = mocker.patch.object(uploader, "_upload_file")

        mock_pbar = mocker.MagicMock()
        mock_pbar.__enter__.return_value = mock_pbar
        mocker.patch("cipher_generation.drive_uploader.tqdm", return_value=mock_pbar)

        mock_queue.get.side_effect = [
            queue.Empty,
            queue.Empty,
            SENTINEL,
        ]

        uploader.run()

        assert mock_queue.get.call_count == 3
        assert mock_pbar.refresh.call_count == 2
        mock_upload.assert_not_called()

    def test_run_aborts_on_auth_failure(self, mocker, uploader, mock_queue):
        """Verify the run loop immediately returns if authentication fails."""
        mocker.patch.object(uploader, "_authenticate_service", return_value=False)
        mock_tqdm_set_lock = mocker.patch(
            "cipher_generation.drive_uploader.tqdm.set_lock"
        )

        uploader.run()

        mock_tqdm_set_lock.assert_not_called()
        mock_queue.get.assert_not_called()


@dataclass
class UploadTestCase:
    """Defines the parameters for testing various upload outcomes."""

    id: str
    split: str
    expected_folder_id: str | None
    api_return: str | None
    expected_count_increase: int
    logs_error: bool
    expect_file_deleted: bool


upload_test_cases = [
    UploadTestCase(
        id="success",
        split="train",
        expected_folder_id="mock_train_123",
        api_return="success_file_id",
        expected_count_increase=10000,
        logs_error=False,
        expect_file_deleted=True,
    ),
    UploadTestCase(
        id="missing_folder",
        split="unknown_split",
        expected_folder_id=None,
        api_return=None,
        expected_count_increase=0,
        logs_error=True,
        expect_file_deleted=False,
    ),
    UploadTestCase(
        id="api_rejection",
        split="val",
        expected_folder_id="mock_val_123",
        api_return=None,
        expected_count_increase=0,
        logs_error=True,
        expect_file_deleted=False,
    ),
]


class TestDriveUploaderDiskHelpers:
    """Tests covering disk reading, merging, cleaning, and API uploading."""

    @pytest.mark.parametrize("case", upload_test_cases, ids=lambda c: c.id)
    def test_upload_file_outcomes_and_disk_cleanup(
        self, mocker, uploader, tmp_path, case: UploadTestCase
    ):
        """Verify API uploads correctly delete the local file, and failures preserve it."""
        uploader.drive_service = mocker.Mock()
        mock_log = mocker.patch("cipher_generation.drive_uploader.log")
        mock_upload_to_drive = mocker.patch(
            "cipher_generation.drive_uploader.upload_to_drive",
            return_value=case.api_return,
        )
        mock_pbar = mocker.Mock()

        dummy_file = tmp_path / "test_file.zip"
        dummy_file.write_bytes(b"dummy_zip_data")

        test_item = Item(
            split=case.split,
            filepath=str(dummy_file),
            filename="test_file.zip",
            cipher_count=10000,
        )

        uploader._upload_file(test_item, mock_pbar)

        assert uploader.uploaded_count == case.expected_count_increase
        assert dummy_file.exists() != case.expect_file_deleted

        if case.expect_file_deleted:
            mock_upload_to_drive.assert_called_once_with(
                uploader.drive_service,
                b"dummy_zip_data",
                "test_file.zip",
                case.expected_folder_id,
            )

        if case.logs_error:
            mock_log.error.assert_called_once()

    def test_upload_file_unexpected_exception(self, mocker, uploader, tmp_path):
        """Verify API crashes are caught, logged, and the file is NOT deleted."""
        mock_log = mocker.patch("cipher_generation.drive_uploader.log")
        mocker.patch(
            "cipher_generation.drive_uploader.upload_to_drive",
            side_effect=Exception("Network Timeout"),
        )

        dummy_file = tmp_path / "crash_test.zip"
        dummy_file.write_bytes(b"data")

        test_item = Item(
            split="train",
            filepath=str(dummy_file),
            filename="crash_test.zip",
            cipher_count=100,
        )

        uploader._upload_file(test_item, mocker.Mock())

        mock_log.error.assert_called_once()
        assert "FATAL: Unexpected error" in mock_log.error.call_args[0][0]
        assert dummy_file.exists()

    def test_merge_and_upload_logic(self, mocker, uploader, tmp_path):
        """Verify multiple raw files are merged into one zip and then passed to _upload_file."""
        mock_upload = mocker.patch.object(uploader, "_upload_file")

        # --- THE FIX: Use a safe, conditional mock to prevent infinite pathlib recursion ---
        original_join = os.path.join

        def safe_mock_join(*args):
            if args and args[0] == "temp_ciphers":
                return str(tmp_path / args[1])
            return original_join(*args)

        mocker.patch("os.path.join", side_effect=safe_mock_join)

        # Create dummy temp_ciphers directory in our tmp_path to route os.path.join calls safely
        temp_dir = tmp_path / "temp_ciphers"
        temp_dir.mkdir()


        file1 = tmp_path / "raw1.jsonl"
        file1.write_text("cipher1")
        file2 = tmp_path / "raw2.jsonl"
        file2.write_text("cipher2")

        # Pass Path objects directly, mimicking the new hoard logic
        files_to_merge = [(file1, 5), (file2, 10)]

        uploader._merge_and_upload("val", files_to_merge, mocker.Mock())

        assert not file1.exists()
        assert not file2.exists()

        mock_upload.assert_called_once()
        upload_item = mock_upload.call_args[0][0]

        assert upload_item.split == "val"
        assert upload_item.cipher_count == 15
        assert upload_item.filename == "val_final.zip"

        with zipfile.ZipFile(upload_item.filepath, "r") as zf:
            assert "val_merged.jsonl" in zf.namelist()
            with zf.open("val_merged.jsonl") as f:
                content = f.read().decode("utf-8")
                assert "cipher1" in content
                assert "cipher2" in content
