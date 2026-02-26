import multiprocessing as mp
from multiprocessing.queues import Queue as MPQueue
from utils.logging import get_colored_logger
from dataclasses import dataclass
from utils.drive import (
	authenticate_drive_terminal,
	upload_to_drive,
)
from tqdm import tqdm
from typing import Any
from utils.constants import BATCH_SIZE
import queue

import io
import zipfile

log = get_colored_logger("drive_uploader")
SENTINEL = "STOP"


@dataclass
class DriveUploaderConfig:
	"""A dataclass to store the configuration for the DriveUploader.

	Attributes:
		split_folders (dict[str, str]): A dictionary mapping split names to folder IDs.
		total_ciphers (int): The total number of ciphers to upload across all splits.

	"""

	split_folders: dict[str, str]
	total_ciphers: int


@dataclass
class BatchState:
	"""A dataclass to store the state of a batch upload for a specific split.

	Attributes:
		split (str): The split identifier for this batch.
		current_batch_count (int): The number of ciphers in the current batch.
		batch_buffer (io.BytesIO): A buffer for the current batch ZIP file.
		zip_buffer (zipfile.ZipFile): A ZIP file for the current batch.
		batch_num (int): The current batch number.

	"""

	split: str
	current_batch_count: int
	batch_buffer: io.BytesIO
	zip_buffer: zipfile.ZipFile
	batch_num: int

	def __init__(self, split: str, batch_num: int = 1) -> None:
		"""Initialize the BatchState with default values for a given split.

		Args:
			split (str): The split identifier (e.g., 'train', 'val').
			batch_num (int, optional): The batch number. Defaults to 1.

		"""
		self.split = split
		self.current_batch_count = 0
		self.batch_num = batch_num
		self.batch_buffer = io.BytesIO()
		self.zip_buffer = zipfile.ZipFile(
			self.batch_buffer,
			"w",
			zipfile.ZIP_DEFLATED,
			False,
		)


class DriveUploader(mp.Process):
	"""A multiprocessing process for uploading ciphers to Google Drive.

	Attributes:
		queue (MPQueue[Any]): The queue to read ciphers from.
		split_folders (dict[str, str]): Mappings of splits to Google Drive folder IDs.
		total_ciphers (int): The total number of ciphers to upload.
		drive_service (build): The authenticated Google Drive service object.
		batch_states (dict[str, BatchState]): The current batch state for each split.

	Methods:
		run(): Execute the cipher upload process.

	"""

	def __init__(
		self,
		queue: MPQueue[Any],
		config: DriveUploaderConfig,
		*args: Any,
		**kwargs: Any,
	) -> None:
		"""Initialize the DriveUploader with a queue and configuration.

		Args:
			queue (MPQueue[Any]): The queue to read ciphers from.
			config (DriveUploaderConfig): The configuration for the uploader.
			*args: Additional positional arguments.
			**kwargs: Additional keyword arguments.

		"""
		super().__init__(*args, **kwargs)
		self.queue = queue
		self.split_folders = config.split_folders
		self.total_ciphers = config.total_ciphers
		self.drive_service = None
		self.uploaded_count = 0

	def run(self) -> None:
		"""Execute the cipher upload process.

		This method continuously reads ciphers from the queue and uploads them to
		Google Drive in batches. It handles routing by split and error handling.

		Raises:
			Exception: If any error occurs during the execution.

		"""
		self.batch_states = {
			split: BatchState(split)
			for split in self.split_folders
			if split != "metadata"
		}
		process_name = self.name
		if not self._authenticate_service():
			return

		with tqdm(total=self.total_ciphers, desc="Total Ciphers Uploaded") as pbar:
			while True:
				try:
					item = self.queue.get(timeout=5)
				except queue.Empty:
					continue

				if item == SENTINEL:
					self._upload_all_final_batches(pbar)
					break

				split, filename, file_bytes = item
				if split == "metadata":
					self._upload_raw_file(split, filename, file_bytes)
				elif split in self.batch_states:
					self._process_cipher_item(split, filename, file_bytes, pbar)

		log.info(
			f"{process_name} finished. Total uploaded: {self.uploaded_count} files.",
		)

	def _authenticate_service(self) -> bool:
		"""Authenticate with the Google Drive service.

		Returns:
			bool: True if authentication was successful, False otherwise.

		"""
		try:
			self.drive_service = authenticate_drive_terminal()
			return True
		except Exception as e:
			log.critical(
				f"{self.name}: Error authenticating drive service: {e}",
				exc_info=True,
			)
			return False

	def _process_cipher_item(
		self,
		split: str,
		filename: str,
		file_bytes: bytes,
		pbar: tqdm,
	) -> None:
		"""Process a single cipher item, adding it to the corresponding split batch.

		Args:
			split (str): The split routing identifier.
			filename (str): The name of the file to add to the archive.
			file_bytes (bytes): The raw bytes of the file.
			pbar (tqdm): The progress bar to update.

		"""
		bs = self.batch_states[split]

		bs.zip_buffer.writestr(filename, file_bytes)
		bs.current_batch_count += 1

		if bs.current_batch_count >= BATCH_SIZE:
			bs.zip_buffer.close()
			batch_filename = f"{split}_ciphers_batch_{bs.batch_num}.zip"
			self.batch_states[split] = self._upload_batch(bs, pbar, batch_filename)

	def _upload_raw_file(self, split: str, filename: str, file_bytes: bytes) -> None:
		"""Upload a raw file directly to Google Drive without zipping.

		Args:
			split (str): The split identifier (e.g., 'metadata').
			filename (str): The desired filename on Drive.
			file_bytes (bytes): The raw file contents.

		"""
		folder_id = self.split_folders.get(split)
		if not folder_id:
			log.error(
				f"Cannot upload {filename}: No folder ID found for split '{split}'",
			)
			return

		try:
			file_id = upload_to_drive(
				self.drive_service,
				file_bytes,
				filename,
				folder_id,
			)

			if file_id:
				log.info(f"Uploaded raw file {filename} to {split} folder: {file_id}")
			else:
				log.error(f"FATAL: Failed to upload raw file {filename} to {split}.")

		except Exception as e:
			log.error(
				f"FATAL: Unexpected error uploading raw file {filename}: {e}",
				exc_info=True,
			)

	def _upload_all_final_batches(self, pbar: tqdm) -> None:
		"""Upload any remaining partial batches for all configured splits.

		Args:
			pbar (tqdm): The progress bar to update.

		"""
		for split, bs in self.batch_states.items():
			if bs.current_batch_count > 0:
				log.info(
					f"Uploading final partial batch for {split}: "
					f"{bs.current_batch_count} files.",
				)
				bs.zip_buffer.close()
				batch_filename = f"{split}_ciphers_batch_final_{bs.batch_num}.zip"
				self.batch_states[split] = self._upload_batch(bs, pbar, batch_filename)

	def _upload_batch(
		self,
		bs: BatchState,
		pbar: tqdm,
		batch_filename: str,
	) -> BatchState:
		"""Upload a batch of ciphers to Google Drive.

		Args:
			bs (BatchState): The current BatchState object.
			pbar (tqdm): The progress bar to update.
			batch_filename (str): The filename of the batch ZIP file.

		Returns:
			BatchState: A fresh BatchState object for the next iterations.

		"""
		folder_id = self.split_folders[bs.split]

		try:
			file_id = upload_to_drive(
				self.drive_service,
				bs.batch_buffer.getvalue(),
				batch_filename,
				folder_id,
			)

			if file_id:
				self.uploaded_count += bs.current_batch_count
				pbar.update(bs.current_batch_count)
				log.info(
					f"Uploaded {bs.split} Batch {bs.batch_num} to Drive: {file_id}",
				)

				return BatchState(split=bs.split, batch_num=bs.batch_num + 1)
			else:
				log.critical(
					f"FATAL: {bs.split} Batch {bs.batch_num} failed all retries.",
				)
				return BatchState(split=bs.split, batch_num=bs.batch_num + 1)

		except Exception as e:
			log.error(
				f"FATAL: Unexpected error uploading {bs.split} "
				f"Batch {bs.batch_num}: {e}",
				exc_info=True,
			)
			return BatchState(split=bs.split, batch_num=bs.batch_num + 1)
