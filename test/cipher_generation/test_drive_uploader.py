import pytest
import queue
from dataclasses import dataclass
from multiprocessing.queues import Queue as MPQueue

from cipher_generation.drive_uploader import DriveUploader, DriveUploaderConfig, Item

MOCK_SPLIT_FOLDERS = {
	"train": "mock_train_123",
	"val": "mock_val_123",
	"metadata": "mock_metadata_123",
}
SENTINEL = "STOP"


@pytest.fixture
def mock_queue(mocker):
	"""Provide a mock multiprocessing queue."""
	return mocker.Mock(spec=MPQueue)


@pytest.fixture
def uploader_config():
	"""Provide a default uploader configuration."""
	return DriveUploaderConfig(split_folders=MOCK_SPLIT_FOLDERS, total_ciphers=20000)


@pytest.fixture
def uploader(mock_queue, uploader_config):
	"""Provide an initialized DriveUploader instance."""
	return DriveUploader(mock_queue, uploader_config, name="TestUploader")


class TestDriveUploaderInitialization:
	"""Tests covering object initialization and state."""

	def test_initialization(self, uploader):
		"""Verify the uploader initializes with the correct configuration."""
		assert uploader.split_folders == MOCK_SPLIT_FOLDERS
		assert uploader.total_ciphers == 20000
		assert uploader.uploaded_count == 0

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


class TestDriveUploaderRunLoop:
	"""Tests covering the main execution loop and queue pulling."""

	def test_successful_run_loop(self, mocker, uploader, mock_queue):
		"""Verify the run loop properly pulls items, unpacks them, and uploads them."""
		mocker.patch.object(uploader, "_authenticate_service", return_value=True)
		mock_upload = mocker.patch.object(uploader, "_upload_file")

		mock_queue.get.side_effect = [
			("train", "batch_train_1.zip", b"bytes1", 10000),
			("val", "batch_val_1.zip", b"bytes2", 2000),
			SENTINEL,
		]

		mocker.patch("cipher_generation.drive_uploader.tqdm")

		uploader.run()

		assert mock_upload.call_count == 2

		first_call_args = mock_upload.call_args_list[0][0]
		uploaded_item = first_call_args[0]
		assert uploaded_item.split == "train"
		assert uploaded_item.filename == "batch_train_1.zip"
		assert uploaded_item.cipher_count == 10000

	def test_empty_queue_timeout(self, mocker, uploader, mock_queue):
		"""Verify the uploader handles empty queue timeouts gracefully without crashing."""
		mocker.patch.object(uploader, "_authenticate_service", return_value=True)
		mock_upload = mocker.patch.object(uploader, "_upload_file")

		mock_queue.get.side_effect = [
			queue.Empty,
			("metadata", "meta.json", b"bytes", 1),
			queue.Empty,
			SENTINEL,
		]

		mocker.patch("cipher_generation.drive_uploader.tqdm")

		uploader.run()

		assert mock_queue.get.call_count == 4
		assert mock_upload.call_count == 1

	def test_authentication_failure(self, mocker, uploader, mock_queue):
		"""Verify the uploader aborts if Google Drive authentication fails."""
		mocker.patch(
			"cipher_generation.drive_uploader.authenticate_drive_terminal",
			side_effect=Exception("Auth failed"),
		)
		mock_log = mocker.patch("cipher_generation.drive_uploader.log")

		uploader.run()

		mock_log.critical.assert_called_once_with(
			"TestUploader: Error authenticating drive service: Auth failed",
			exc_info=True,
		)
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


upload_test_cases = [
	UploadTestCase(
		id="success",
		split="train",
		expected_folder_id="mock_train_123",
		api_return="success_file_id",
		expected_count_increase=10000,
		logs_error=False,
	),
	UploadTestCase(
		id="missing_folder",
		split="unknown_split",
		expected_folder_id=None,
		api_return=None,
		expected_count_increase=0,
		logs_error=True,
	),
	UploadTestCase(
		id="api_rejection",
		split="val",
		expected_folder_id="mock_val_123",
		api_return=None,
		expected_count_increase=0,
		logs_error=True,
	),
]


class TestDriveUploaderUploadHelpers:
	"""Tests covering the interaction with the Google Drive API."""

	@pytest.mark.parametrize("case", upload_test_cases, ids=lambda c: c.id)
	def test_upload_file_outcomes(self, mocker, uploader, case: UploadTestCase):
		"""Verify routing, successful uploads, and handled failures using dataclass test cases."""
		uploader.drive_service = mocker.Mock()
		mock_log = mocker.patch("cipher_generation.drive_uploader.log")
		mock_upload_to_drive = mocker.patch(
			"cipher_generation.drive_uploader.upload_to_drive",
			return_value=case.api_return,
		)
		mock_pbar = mocker.Mock()

		test_item = Item(
			split=case.split,
			filename="test_file.zip",
			file_bytes=b"data",
			cipher_count=10000,
		)

		uploader._upload_file(test_item, mock_pbar)

		assert uploader.uploaded_count == case.expected_count_increase

		if case.expected_count_increase > 0:
			mock_pbar.update.assert_called_once_with(case.expected_count_increase)
			mock_log.info.assert_called_once()
		else:
			mock_pbar.update.assert_not_called()

		if case.logs_error:
			mock_log.error.assert_called_once()

		if case.expected_folder_id:
			mock_upload_to_drive.assert_called_once_with(
				uploader.drive_service,
				b"data",
				"test_file.zip",
				case.expected_folder_id,
			)
		else:
			mock_upload_to_drive.assert_not_called()

	def test_upload_file_unexpected_exception(self, mocker, uploader):
		"""Verify that unexpected API crashes during upload are caught and logged."""
		mock_log = mocker.patch("cipher_generation.drive_uploader.log")
		mocker.patch(
			"cipher_generation.drive_uploader.upload_to_drive",
			side_effect=Exception("Network Timeout"),
		)
		mock_pbar = mocker.Mock()
		test_item = Item(
			split="train",
			filename="crash_test.zip",
			file_bytes=b"data",
			cipher_count=100,
		)

		uploader._upload_file(test_item, mock_pbar)

		mock_log.error.assert_called_once()
		assert (
			"FATAL: Unexpected error uploading crash_test.zip: Network Timeout"
			in mock_log.error.call_args[0][0]
		)
		assert mock_log.error.call_args[1].get("exc_info") is True
		assert uploader.uploaded_count == 0
