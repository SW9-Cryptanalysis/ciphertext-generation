import pytest
import io
import queue
from typing import Final, Any
from dataclasses import dataclass
from multiprocessing.queues import Queue as MPQueue

from drive.drive_uploader import DriveUploader, DriveUploaderConfig, BatchState

# --- Constants & Test Data ---
BATCH_SIZE: Final[int] = 2
MOCK_SPLIT_FOLDERS: Final[dict[str, str]] = {
	"train": "mock_train_123",
	"val": "mock_val_123",
	"metadata": "mock_metadata_123",
}
SENTINEL: Final[str] = "STOP"


# --- Shared Fixtures ---
@pytest.fixture(autouse=True)
def silent_zipfile(mocker):
	"""Prevents any real ZipFile from being opened during tests."""
	return mocker.patch("zipfile.ZipFile")


@pytest.fixture
def uploader_config():
	return DriveUploaderConfig(split_folders=MOCK_SPLIT_FOLDERS, total_ciphers=10)


@pytest.fixture
def mock_cipher_item():
	return ("train", "cipher_123_10.json", b"mock_cipher_data_1")


@pytest.fixture
def mock_cipher_item_2():
	return ("train", "cipher_456_10.json", b"mock_cipher_data_2")


@dataclass
class UploaderTestContext:
	queue: MPQueue[Any]
	config: DriveUploaderConfig
	item: tuple[str, str, bytes]
	item2: tuple[str, str, bytes]


@pytest.fixture
def ctx(queue_factory, uploader_config, mock_cipher_item, mock_cipher_item_2):
	"""Bundles common fixtures into a single context object."""
	return UploaderTestContext(
		queue=queue_factory(),
		config=uploader_config,
		item=mock_cipher_item,
		item2=mock_cipher_item_2,
	)


# --- Test Classes ---


class TestDriveUploaderInitialization:
	"""Tests covering object initialization and dataclasses."""

	def test_initialization(self, queue_factory, uploader_config):
		uploader = DriveUploader(queue_factory(), uploader_config, name="Test")
		assert uploader.split_folders == MOCK_SPLIT_FOLDERS
		assert uploader.total_ciphers == 10
		assert uploader.uploaded_count == 0

	def test_batch_state_init(self):
		bs = BatchState(split="val", batch_num=5)
		assert bs.split == "val"
		assert bs.current_batch_count == 0
		assert bs.batch_num == 5
		assert isinstance(bs.batch_buffer, io.BytesIO)


class TestDriveUploaderRunLoop:
	"""Tests covering the main execution loop, queue pulling, and routing."""

	def test_successful_full_upload(
		self, mocker, queue_factory, mock_cipher_item, mock_cipher_item_2
	):
		total_to_upload = 2
		local_config = DriveUploaderConfig(
			split_folders=MOCK_SPLIT_FOLDERS, total_ciphers=total_to_upload
		)

		mocker.patch(
			"drive.drive_uploader.authenticate_drive_terminal",
			return_value=mocker.Mock(),
		)
		mock_upload_drive = mocker.patch(
			"drive.drive_uploader.upload_to_drive",
			side_effect=["file_id_1", "file_id_2"],
		)

		mock_pbar = mocker.Mock(total=total_to_upload)
		mocker.patch(
			"drive.drive_uploader.tqdm",
			return_value=mocker.MagicMock(
				__enter__=lambda self: mock_pbar, __exit__=lambda *args: None
			),
		)

		mock_queue = queue_factory()

		mock_queue.put(mock_cipher_item)
		mock_queue.put(mock_cipher_item_2)
		mock_queue.put(SENTINEL)

		uploader = DriveUploader(mock_queue, local_config, name="TestUploader")
		uploader.run()

		assert uploader.uploaded_count == total_to_upload
		assert mock_upload_drive.call_count == 1
		mock_pbar.update.assert_called_once_with(BATCH_SIZE)

	def test_empty_queue(self, mocker, uploader_config):
		"""Test that the uploader handles empty queues gracefully via timeouts."""
		queue_mock = mocker.Mock()
		queue_mock.get.side_effect = [queue.Empty, SENTINEL]

		mocker.patch(
			"drive.drive_uploader.authenticate_drive_terminal",
			return_value=mocker.Mock(),
		)

		uploader = DriveUploader(queue_mock, uploader_config, name="Test")
		uploader.run()

		assert uploader.uploaded_count == 0
		assert queue_mock.get.call_count == 2

		# Second run
		uploader.uploaded_count = 10
		queue_mock.get.side_effect = [queue.Empty, SENTINEL]
		uploader.run()

		assert uploader.uploaded_count == 10
		assert queue_mock.get.call_count == 4

	def test_authentication_failure(
		self, mocker, queue_factory, uploader_config, mock_cipher_item
	):
		mocker.patch(
			"drive.drive_uploader.authenticate_drive_terminal",
			side_effect=Exception("Auth failed"),
		)
		mock_log = mocker.patch("drive.drive_uploader.log")

		mock_queue = queue_factory()

		mock_queue.put(mock_cipher_item)
		mock_queue.put(SENTINEL)

		uploader = DriveUploader(mock_queue, uploader_config, name="TestUploader")
		uploader.run()

		mock_log.critical.assert_called_once_with(
			"TestUploader: Error authenticating drive service: Auth failed",
			exc_info=True,
		)
		assert uploader.uploaded_count == 0

	def test_metadata_routing_in_run(self, mocker, queue_factory, uploader_config):
		"""Test that the 'metadata' split is routed correctly and not batched."""
		mocker.patch(
			"drive.drive_uploader.authenticate_drive_terminal",
			return_value=mocker.Mock(),
		)
		mock_upload_raw = mocker.patch.object(DriveUploader, "_upload_raw_file")

		mock_queue = queue_factory()
		mock_queue.put(
			("metadata", "metadata_vocab_size.json", b'{"max_symbol_id": 100}')
		)
		mock_queue.put(SENTINEL)

		uploader = DriveUploader(mock_queue, uploader_config, name="TestUploader")
		mocker.patch("drive.drive_uploader.tqdm")

		uploader.run()

		assert "metadata" not in uploader.batch_states
		assert "train" in uploader.batch_states
		mock_upload_raw.assert_called_once_with(
			"metadata", "metadata_vocab_size.json", b'{"max_symbol_id": 100}'
		)


class TestDriveUploaderBatchHelpers:
	"""Tests covering the zipped batch logic and API interactions."""

	def test_upload_failure(self, mocker, ctx: UploaderTestContext):
		mocker.patch(
			"drive.drive_uploader.authenticate_drive_terminal",
			return_value=mocker.Mock(),
		)
		mock_log = mocker.patch("drive.drive_uploader.log")

		ctx.queue.put(ctx.item)
		ctx.queue.put(ctx.item2)
		ctx.queue.put(SENTINEL)

		uploader = DriveUploader(ctx.queue, ctx.config, name="TestUploader")
		uploader.run()

		assert uploader.uploaded_count == 0
		mock_log.critical.assert_called_once_with(
			"FATAL: train Batch 1 failed all retries."
		)

	def test_partial_final_batch(self, mocker, ctx: UploaderTestContext):
		total_expected = 3
		ctx.config.total_ciphers = total_expected
		mocker.patch("drive.drive_uploader.BATCH_SIZE", 2)

		mocker.patch(
			"drive.drive_uploader.authenticate_drive_terminal",
			return_value=mocker.Mock(),
		)
		mock_upload_drive = mocker.patch(
			"drive.drive_uploader.upload_to_drive",
			side_effect=["file_id_full", "file_id_final"],
		)
		mock_pbar = mocker.Mock(total=total_expected)
		mocker.patch(
			"drive.drive_uploader.tqdm",
			return_value=mocker.MagicMock(
				__enter__=lambda self: mock_pbar, __exit__=lambda *args: None
			),
		)

		ctx.queue.put(ctx.item)
		ctx.queue.put(ctx.item2)
		ctx.queue.put(ctx.item)
		ctx.queue.put(SENTINEL)

		uploader = DriveUploader(ctx.queue, ctx.config, name="TestUploader")
		uploader.run()

		assert uploader.uploaded_count == total_expected
		assert mock_upload_drive.call_count == 2
		mock_upload_drive.assert_any_call(
			mocker.ANY, mocker.ANY, "train_ciphers_batch_1.zip", mocker.ANY
		)
		mock_upload_drive.assert_any_call(
			mocker.ANY, mocker.ANY, "train_ciphers_batch_final_2.zip", mocker.ANY
		)
		mock_pbar.update.assert_any_call(2)
		mock_pbar.update.assert_any_call(1)

	def test_upload_batch_helper_success(self, mocker, uploader_config):
		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		uploader.drive_service = mocker.Mock()

		mock_upload = mocker.patch(
			"drive.drive_uploader.upload_to_drive", return_value="file_id_successful"
		)
		mock_pbar = mocker.Mock()

		bs_initial = BatchState(split="train", batch_num=3)
		bs_initial.current_batch_count = 5
		bs_initial.batch_buffer.write(b"some_zip_data")
		bs_initial.batch_buffer.seek(0)

		new_bs = uploader._upload_batch(bs_initial, mock_pbar, "test_batch.zip")

		assert new_bs.split == "train"
		assert new_bs.batch_num == 4
		assert new_bs.current_batch_count == 0
		assert mock_upload.call_count == 1
		mock_pbar.update.assert_called_once_with(5)
		new_bs.zip_buffer.close()

	def test_upload_batch_helper_failure(self, mocker, uploader_config):
		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		uploader.drive_service = mocker.Mock()
		mock_log = mocker.patch("drive.drive_uploader.log")

		mock_upload = mocker.patch(
			"drive.drive_uploader.upload_to_drive", return_value=""
		)
		mock_pbar = mocker.Mock()

		bs_initial = BatchState(split="train", batch_num=5)
		bs_initial.current_batch_count = 10

		new_bs = uploader._upload_batch(bs_initial, mock_pbar, "test_fail.zip")

		assert new_bs.batch_num == 6
		assert new_bs.current_batch_count == 0
		mock_log.critical.assert_called_once_with(
			"FATAL: train Batch 5 failed all retries."
		)
		assert mock_upload.call_count == 1
		mock_pbar.update.assert_not_called()
		new_bs.zip_buffer.close()

	def test_upload_batch_exception_handling(self, mocker, uploader_config):
		mock_bs_class = mocker.patch("drive.drive_uploader.BatchState")
		mock_new_bs = mocker.Mock()
		mock_new_bs.batch_num = 8
		mock_new_bs.current_batch_count = 0
		mock_bs_class.return_value = mock_new_bs

		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		uploader.drive_service = mocker.Mock()
		mock_log = mocker.patch("drive.drive_uploader.log")

		mocker.patch(
			"drive.drive_uploader.upload_to_drive",
			side_effect=Exception("Unexpected API Crash"),
		)
		mock_pbar = mocker.Mock()

		bs_initial = BatchState(split="train", batch_num=7)
		bs_initial.current_batch_count = 5

		new_bs = uploader._upload_batch(bs_initial, mock_pbar, "crash_batch.zip")

		assert new_bs.batch_num == 8
		assert new_bs.current_batch_count == 0
		mock_log.error.assert_called_once_with(
			"FATAL: Unexpected error uploading train Batch 7: Unexpected API Crash",
			exc_info=True,
		)
		mock_pbar.update.assert_not_called()


class TestDriveUploaderRawFileHelpers:
	"""Tests covering the raw file upload logic specifically for metadata."""

	def test_upload_raw_file_success(self, mocker, uploader_config):
		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		uploader.drive_service = mocker.Mock()
		mock_log = mocker.patch("drive.drive_uploader.log")

		mock_upload = mocker.patch(
			"drive.drive_uploader.upload_to_drive", return_value="raw_file_id_1"
		)

		uploader._upload_raw_file("metadata", "meta.json", b"raw_data")

		mock_upload.assert_called_once_with(
			uploader.drive_service, b"raw_data", "meta.json", "mock_metadata_123"
		)
		mock_log.info.assert_called_once_with(
			"Uploaded raw file meta.json to metadata folder: raw_file_id_1"
		)

	def test_upload_raw_file_missing_folder(self, mocker, uploader_config):
		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		mock_log = mocker.patch("drive.drive_uploader.log")
		mock_upload = mocker.patch("drive.drive_uploader.upload_to_drive")

		uploader._upload_raw_file("unknown_split", "meta.json", b"raw_data")

		mock_upload.assert_not_called()
		mock_log.error.assert_called_once_with(
			"Cannot upload meta.json: No folder ID found for split 'unknown_split'"
		)

	def test_upload_raw_file_api_rejection(self, mocker, uploader_config):
		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		uploader.drive_service = mocker.Mock()
		mock_log = mocker.patch("drive.drive_uploader.log")

		mocker.patch("drive.drive_uploader.upload_to_drive", return_value=None)
		uploader._upload_raw_file("metadata", "meta.json", b"raw_data")

		mock_log.error.assert_called_once_with(
			"FATAL: Failed to upload raw file meta.json to metadata."
		)

	def test_upload_raw_file_exception_handling(self, mocker, uploader_config):
		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		uploader.drive_service = mocker.Mock()
		mock_log = mocker.patch("drive.drive_uploader.log")

		mocker.patch(
			"drive.drive_uploader.upload_to_drive",
			side_effect=Exception("Network Timeout"),
		)

		uploader._upload_raw_file("metadata", "meta.json", b"raw_data")

		mock_log.error.assert_called_once_with(
			"FATAL: Unexpected error uploading raw file meta.json: Network Timeout",
			exc_info=True,
		)
