import os
from utils.logging import get_colored_logger
from drive.cipher_manager import CipherManager
from fetching.text_splits import get_text_stream

if __name__ == "__main__":
	log = get_colored_logger("gen_training")
	folder_id = os.getenv("FOLDER_ID_TRAIN")

	if not folder_id:
		raise OSError(
			"FOLDER_ID environment variable not set. Please set it before running.",
		)

	text_stream = get_text_stream()

	manager = CipherManager(
		folder_id=folder_id, text_stream_source=text_stream, total_count=1_000_000,
	)

	try:
		manager.execute()
	except Exception as e:
		log.critical(
			f"A critical error occurred in the main process: {e}",
			exc_info=True,
		)
