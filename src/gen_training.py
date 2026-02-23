import os
from utils.logging import get_colored_logger
from drive.cipher_manager import CipherManager
from fetching.text_splits import get_text_stream

if __name__ == "__main__":
	log = get_colored_logger("gen_training")
	folder_id_train = os.getenv("FOLDER_ID_TRAIN")
	folder_id_val = os.getenv("FOLDER_ID_VAL")
	folder_id_test = os.getenv("FOLDER_ID_TEST")

	folder_id_metadata = os.getenv("FOLDER_ID_METADATA")

	if not folder_id_metadata:
		raise OSError(
			"FOLDER_ID_METADATA environment variable not set. "
			"Please set it before running.",
		)

	if not folder_id_train:
		raise OSError(
			"FOLDER_ID_TRAIN environment variable not set. "
			"Please set it before running.",
		)

	if not folder_id_val:
		raise OSError(
			"FOLDER_ID_VAL environment variable not set. Please set it before running.",
		)
	if not folder_id_test:
		raise OSError(
			"FOLDER_ID_TEST environment variable not set. "
			"Please set it before running.",
		)

	text_stream = get_text_stream()

	config = {
		"train": {"folder_id": folder_id_train, "count": 1_000_000},
		"val": {"folder_id": folder_id_val, "count": 10_000},
		"test": {"folder_id": folder_id_test, "count": 10_000},
		"metadata": {"folder_id": folder_id_metadata, "count": 0},
	}

	manager = CipherManager(
		config=config,
		text_stream_source=text_stream,
	)

	try:
		manager.execute()
	except Exception as e:
		log.critical(
			f"A critical error occurred in the main process: {e}",
			exc_info=True,
		)
