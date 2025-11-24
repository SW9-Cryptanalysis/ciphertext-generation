import os
from utils.logging import get_colored_logger
from drive.upload_manager import CipherManager

log = get_colored_logger("gen_training")

if __name__ == "__main__":
	folder_id = os.getenv("FOLDER_ID")

	if not folder_id:
		raise OSError(
			"FOLDER_ID environment variable not set. Please set it before running.",
		)

	manager = CipherManager(folder_id=folder_id)

	try:
		manager.execute()
	except Exception as e:
		log.critical(
			f"A critical error occurred in the main process: {e}",
			exc_info=True,
		)
