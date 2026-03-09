import multiprocessing as mp
import queue
from typing import Any
from multiprocessing.queues import Queue as MPQueue
from utils.logging import get_logger
from dataclasses import dataclass
from utils.drive import (
	authenticate_drive_terminal,
	upload_to_drive,
)
from tqdm import tqdm

log = get_logger("DriveUploader")
SENTINEL = "STOP"


@dataclass
class Item:
	"""A dataclass representing a packaged file ready for upload.

	Attributes:
		split (str): The dataset split identifier.
		filename (str): The destination filename.
		file_bytes (bytes): The raw, compressed file data.
		cipher_count (int): The number of ciphers contained in the file.

	"""

	split: str
	filename: str
	file_bytes: bytes
	cipher_count: int


@dataclass
class DriveUploaderConfig:
	"""A dataclass to store the configuration for the DriveUploader.

	Attributes:
		split_folders (dict[str, str]): A dictionary mapping split names to folder IDs.
		total_ciphers (int): The total number of ciphers to upload across all splits.

	"""

	split_folders: dict[str, str]
	total_ciphers: int


class DriveUploader(mp.Process):
	"""A multiprocessing process for uploading ready-made batch files to Google Drive.

	Attributes:
		queue (MPQueue[Any]): The queue to read finished batch files from.
		split_folders (dict[str, str]): Mappings of splits to Google Drive folder IDs.
		total_ciphers (int): The total number of ciphers to upload.
		drive_service (Any): The authenticated Google Drive service object.
		uploaded_count (int): Tracking the total uploaded items.

	"""

	def __init__(
		self,
		upload_queue: MPQueue[Any],
		config: DriveUploaderConfig,
		*args: Any,
		**kwargs: Any,
	) -> None:
		"""Initialize the DriveUploader with a queue and configuration."""
		super().__init__(*args, **kwargs)
		self.queue = upload_queue
		self.split_folders = config.split_folders
		self.total_ciphers = config.total_ciphers
		self.drive_service = None
		self.uploaded_count = 0

	def run(self) -> None:
		"""Execute the cipher upload process."""
		process_name = self.name
		if not self._authenticate_service():
			return

		with tqdm(total=self.total_ciphers, desc="Total Ciphers Uploaded") as pbar:
			while True:
				try:
					queue_payload = self.queue.get(timeout=5)
				except queue.Empty:
					continue

				if queue_payload == SENTINEL:
					break

				split, filename, file_bytes, cipher_count = queue_payload

				upload_item = Item(
					split=split,
					filename=filename,
					file_bytes=file_bytes,
					cipher_count=cipher_count,
				)

				self._upload_file(upload_item, pbar)

		log.info(
			f"{process_name} finished. Total uploaded: {self.uploaded_count} ciphers.",
		)

	def _authenticate_service(self) -> bool:
		"""Authenticate with the Google Drive service."""
		try:
			self.drive_service = authenticate_drive_terminal()
			return True
		except Exception as e:
			log.critical(
				f"{self.name}: Error authenticating drive service: {e}",
				exc_info=True,
			)
			return False

	def _upload_file(self, item: Item, pbar: tqdm) -> None:
		"""Upload a completed file directly to Google Drive.

		Args:
			item (Item): The packaged upload details including bytes and metadata.
			pbar (tqdm): The progress bar to update.

		"""
		folder_id = self.split_folders.get(item.split)

		if not folder_id:
			log.error(
				f"Cannot upload {item.filename}: No folder ID found for '{item.split}'",
			)
			return

		try:
			file_id = upload_to_drive(
				self.drive_service,
				item.file_bytes,
				item.filename,
				folder_id,
			)

			if file_id:
				self.uploaded_count += item.cipher_count
				pbar.update(item.cipher_count)
				log.info(f"Uploaded {item.filename} to {item.split} folder: {file_id}")
			else:
				log.error(f"FATAL: Failed to upload {item.filename} to {item.split}.")

		except Exception as e:
			log.error(
				f"FATAL: Unexpected error uploading {item.filename}: {e}",
				exc_info=True,
			)
