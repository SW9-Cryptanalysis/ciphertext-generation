import os
import re
import pytest
import tqdm
from cipher_generation.cipher_manager import CipherManager
from encipherment.cipher import HomophonicCipher
from cipher_generation.cipher_producer import CipherProducer, ProducerConfig
from cipher_generation.drive_uploader import DriveUploader, DriveUploaderConfig


@pytest.fixture
def mock_pbar(mocker):
	"""Provide a standard mocked tqdm context manager."""
	mock_pbar = mocker.MagicMock(spec=tqdm.tqdm)
	mock_pbar.__enter__.return_value = mock_pbar
	return mock_pbar


@pytest.fixture
def mock_cipher(mocker):
	"""Provide a standard mocked HomophonicCipher."""
	mock_cipher = mocker.MagicMock(spec=HomophonicCipher)
	mock_cipher.__json__.return_value = {"mock_key": "mock_value"}
	mock_cipher.plaintext = "abc"
	mock_cipher.num_symbols = 3
	mock_cipher.difficulty = 1
	mock_cipher.genres = ["Fiction"]
	return mock_cipher


def test_end_to_end_pipeline_sync(mocker, tmp_path, mock_pbar, mock_cipher):
	"""Verify the pipeline logic by executing methods sequentially in one process.

	This approach bypasses multiprocessing 'spawn' isolation and pickling errors
	while ensuring the entire data flow from feeder to uploader is validated.
	"""

	mock_lock = mocker.MagicMock()
	mock_lock.__enter__.return_value = mock_lock

	mock_tqdm_uploader = mocker.patch(
		"cipher_generation.drive_uploader.tqdm", return_value=mock_pbar
	)
	mock_tqdm_uploader.get_lock.return_value = mock_lock
	mocker.patch("tqdm.tqdm.set_lock")

	mocker.patch("cipher_generation.drive_uploader.authenticate_drive_terminal")
	mock_upload = mocker.patch(
		"cipher_generation.drive_uploader.upload_to_drive", return_value="fake_id"
	)

	mocker.patch(
		"cipher_generation.cipher_producer.HomophonicCipher", return_value=mock_cipher
	)

	original_join = os.path.join

	def mock_join(*args):
		if args[0] == "temp_ciphers":
			path = tmp_path / "temp_ciphers"
			path.mkdir(exist_ok=True)
			return str(path / args[1])
		return original_join(*args)

	mocker.patch("os.path.join", side_effect=mock_join)

	tiny_config = {
		"train": {"count": 1, "folder_id": "mock_folder"},
		"metadata": {"folder_id": "mock_meta", "count": 0},
	}

	def create_mock_text_stream(raw_text: str) -> dict:
		clean_text = re.sub(r"[^a-z]", "", raw_text.lower())
		return {
			"text": clean_text,
			"text_with_boundaries": raw_text.lower().replace(" ", "_"),
			"source_id": "123",
			"source_name": "Mock Book",
			"length": len(clean_text),
			"genres": ["Fiction"],
		}

	tiny_stream = [("train", create_mock_text_stream("First text"))]

	manager = CipherManager(
		config=tiny_config, text_stream_source=tiny_stream, num_workers=1
	)

	manager._feeder_stream(mocker.Mock())
	manager.job_queue.put("STOP")

	config = ProducerConfig(
		input_queue=manager.job_queue,
		output_queue=manager.result_queue,
		stats_queue=manager.stats_queue,
		batch_size=100,
		temp_dir=tmp_path / "temp_ciphers",
	)

	worker = CipherProducer(
		config=config,
		name="TestWorker",
	)
	worker.run()

	manager._upload_metadata()
	manager.result_queue.put("STOP")

	uploader_config = DriveUploaderConfig(
		split_folders=manager.split_folders,
		total_ciphers=manager.total_count,
		tqdm_lock=mocker.Mock(),
	)
	uploader = DriveUploader(upload_queue=manager.result_queue, config=uploader_config)
	uploader.run()

	assert mock_upload.call_count == 2
