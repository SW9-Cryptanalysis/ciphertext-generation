import os
from utils.logging import get_logger
from cipher_generation.cipher_manager import CipherManager
from fetching.text_splits import get_text_stream
from utils.constants import NUM_TRAINING_CIPHERS, NUM_VALIDATION_CIPHERS, NUM_TEST_CIPHERS

if __name__ == "__main__":
	log = get_logger("TrainingGeneration")
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

	targets = {"train": NUM_TRAINING_CIPHERS, "val": NUM_VALIDATION_CIPHERS, "test": NUM_TEST_CIPHERS}

	text_stream = get_text_stream(targets=targets)

	config = {
		"train": {"folder_id": folder_id_train, "count": NUM_TRAINING_CIPHERS},
		"val": {"folder_id": folder_id_val, "count": NUM_VALIDATION_CIPHERS},
		"test": {"folder_id": folder_id_test, "count": NUM_TEST_CIPHERS},
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
