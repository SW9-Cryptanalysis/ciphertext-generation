import pytest
import multiprocessing as mp
import io
import zipfile
from typing import Final
from dataclasses import dataclass
from multiprocessing.queues import Queue as MPQueue
from typing import Any
from drive.drive_uploader import DriveUploader, DriveUploaderConfig, BatchState
import queue

BATCH_SIZE: Final[int] = 2
MOCK_FOLDER_ID = "mock_folder_123"
SENTINEL: Final[str] = "STOP"


@pytest.fixture
def mock_queue():
	manager = mp.Manager()
	manager.Queue()
	return manager.Queue()


@pytest.fixture
def uploader_config():
	return DriveUploaderConfig(folder_id=MOCK_FOLDER_ID, total_ciphers=10)


@pytest.fixture
def mock_cipher_item():
	return ("cipher_123_10.json", b"mock_cipher_data_1")


@pytest.fixture
def mock_cipher_item_2():
	return ("cipher_456_10.json", b"mock_cipher_data_2")

@dataclass
class UploaderTestContext:
    queue: MPQueue[Any]
    config: DriveUploaderConfig
    item: tuple[str, bytes]
    item2: tuple[str, bytes]

@pytest.fixture
def ctx(mock_queue, uploader_config, mock_cipher_item, mock_cipher_item_2):
    """Bundles common fixtures into a single context object."""
    return UploaderTestContext(
        queue=mock_queue,
        config=uploader_config,
        item=mock_cipher_item,
        item2=mock_cipher_item_2
    )


class TestDriveUploader:
	def test_initialization(self, mock_queue, uploader_config):
		uploader = DriveUploader(mock_queue, uploader_config, name="Test")
		assert uploader.folder_id == MOCK_FOLDER_ID
		assert uploader.total_ciphers == 10
		assert uploader.uploaded_count == 0

	def test_batch_state_init(self):
		bs = BatchState(batch_num=5)
		assert bs.current_batch_count == 0
		assert bs.batch_num == 5
		assert isinstance(bs.batch_buffer, io.BytesIO)
		assert isinstance(bs.zip_buffer, zipfile.ZipFile)

	def test_successful_full_upload(
		self, mocker, mock_queue, mock_cipher_item, mock_cipher_item_2
	):
		total_to_upload = 2

		local_config = DriveUploaderConfig(
			folder_id=MOCK_FOLDER_ID, total_ciphers=total_to_upload
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

		mock_queue.put(mock_cipher_item)
		mock_queue.put(mock_cipher_item_2)
		mock_queue.put(SENTINEL)

		uploader = DriveUploader(mock_queue, local_config, name="TestUploader")

		uploader.run()

		assert uploader.uploaded_count == total_to_upload
		assert mock_upload_drive.call_count == 1
		mock_pbar.update.assert_called_once_with(BATCH_SIZE)

		uploaded_bytes = mock_upload_drive.call_args[0][1]
		assert len(uploaded_bytes) > 100

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

		uploader.uploaded_count = 10

		queue_mock.get.side_effect = [queue.Empty]

		uploader.run()

		assert uploader.uploaded_count == 10

		assert queue_mock.get.call_count == 2

	def test_upload_failure(
		self,
		mocker,
		ctx: UploaderTestContext,
	):
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
			"FATAL: Batch 1 failed all retries and was skipped."
		)

	def test_partial_final_batch(
		self, mocker, ctx: UploaderTestContext,
	):
		total_exepected = 3
		ctx.config.total_ciphers = total_exepected

		mocker.patch("drive.drive_uploader.BATCH_SIZE", 2)

		mocker.patch(
			"drive.drive_uploader.authenticate_drive_terminal",
			return_value=mocker.Mock(),
		)
		mock_upload_drive = mocker.patch(
			"drive.drive_uploader.upload_to_drive",
			side_effect=["file_id_full", "file_id_final"],
		)
		mock_pbar = mocker.Mock(total=total_exepected)
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

		assert uploader.uploaded_count == total_exepected
		assert mock_upload_drive.call_count == 2
		mock_upload_drive.assert_any_call(
			mocker.ANY, mocker.ANY, "ciphers_batch_1.zip", mocker.ANY
		)
		mock_upload_drive.assert_any_call(
			mocker.ANY, mocker.ANY, "ciphers_batch_final_2.zip", mocker.ANY
		)
		mock_pbar.update.assert_any_call(2)
		mock_pbar.update.assert_any_call(1)

	def test_authentication_failure(
		self, mocker, mock_queue, uploader_config, mock_cipher_item
	):
		mocker.patch(
			"drive.drive_uploader.authenticate_drive_terminal",
			side_effect=Exception("Auth failed"),
		)

		mock_log = mocker.patch("drive.drive_uploader.log")

		mock_queue.put(mock_cipher_item)
		mock_queue.put(SENTINEL)

		uploader = DriveUploader(mock_queue, uploader_config, name="TestUploader")

		uploader.run()

		mock_log.critical.assert_called_once_with(
			"TestUploader: Error authenticating drive service: Auth failed",
			exc_info=True,
		)
		assert uploader.uploaded_count == 0

	def test_upload_batch_helper_success(self, mocker, uploader_config):
		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		uploader.drive_service = mocker.Mock()

		mock_upload = mocker.patch(
			"drive.drive_uploader.upload_to_drive", return_value="file_id_successful"
		)
		mock_pbar = mocker.Mock()

		bs_initial = BatchState(batch_num=3)
		bs_initial.current_batch_count = 5
		bs_initial.batch_buffer.write(b"some_zip_data")

		bs_initial.batch_buffer.seek(0)

		new_bs = uploader._upload_batch(bs_initial, mock_pbar, "test_batch.zip")

		assert new_bs.batch_num == 4
		assert new_bs.current_batch_count == 0

		assert mock_upload.call_count == 1
		mock_pbar.update.assert_called_once_with(5)
		new_bs.zip_buffer.close()

	def test_upload_batch_helper_failure(self, mocker, uploader_config, caplog):
		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		uploader.drive_service = mocker.Mock()
		mock_log = mocker.patch("drive.drive_uploader.log")

		mock_upload = mocker.patch(
			"drive.drive_uploader.upload_to_drive", return_value=""
		)
		mock_pbar = mocker.Mock()

		bs_initial = BatchState(batch_num=5)
		bs_initial.current_batch_count = 10

		new_bs = uploader._upload_batch(bs_initial, mock_pbar, "test_fail.zip")

		assert new_bs.batch_num == 6
		assert new_bs.current_batch_count == 0

		mock_log.critical.assert_called_once_with(
			"FATAL: Batch 5 failed all retries and was skipped."
		)
		assert mock_upload.call_count == 1
		mock_pbar.update.assert_not_called()
		new_bs.zip_buffer.close()

	def test_upload_batch_exception_handling(self, mocker, uploader_config):
		"""Test the exception block in _upload_batch."""
		# Mock ZipFile to prevent ResourceWarning/IO error during test teardown
		mocker.patch("drive.drive_uploader.zipfile.ZipFile")

		uploader = DriveUploader(mocker.Mock(), uploader_config, name="TestUploader")
		uploader.drive_service = mocker.Mock()
		mock_log = mocker.patch("drive.drive_uploader.log")

		mocker.patch(
			"drive.drive_uploader.upload_to_drive",
			side_effect=Exception("Unexpected API Crash")
		)
		mock_pbar = mocker.Mock()

		bs_initial = BatchState(batch_num=7)
		bs_initial.current_batch_count = 5
		bs_initial.batch_buffer.write(b"data")

		new_bs = uploader._upload_batch(bs_initial, mock_pbar, "crash_batch.zip")

		assert new_bs.batch_num == 8
		assert new_bs.current_batch_count == 0

		mock_log.error.assert_called_once_with(
			"FATAL: Unexpected error during upload of Batch 7: Unexpected API Crash",
			exc_info=True,
		)

		mock_pbar.update.assert_not_called()
