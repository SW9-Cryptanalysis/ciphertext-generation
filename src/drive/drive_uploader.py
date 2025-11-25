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
		folder_id (str): The ID of the folder to upload the ciphers to.
		total_ciphers (int): The total number of ciphers to upload.

	"""

	folder_id: str
	total_ciphers: int


@dataclass
class BatchState:
	"""A dataclass to store the state of a batch upload.

	Attributes:
		current_batch_count (int): The number of ciphers in the current batch.
		batch_buffer (io.BytesIO): A buffer for the current batch ZIP file.
		zip_buffer (zipfile.ZipFile): A ZIP file for the current batch.
		batch_num (int): The current batch number.

	"""

	current_batch_count: int
	batch_buffer: io.BytesIO
	zip_buffer: zipfile.ZipFile
	batch_num: int

	def __init__(self, batch_num: int = 1) -> None:
		"""Initialize the BatchState with default values.

		Args:
			batch_num (int, optional): The batch number. Defaults to 1.

		"""
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
		folder_id (str): The ID of the folder to upload the ciphers to.
		total_ciphers (int): The total number of ciphers to upload.
		drive_service (build): The authenticated Google Drive service object.

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
		self.folder_id = config.folder_id
		self.total_ciphers = config.total_ciphers
		self.drive_service = None
		self.uploaded_count = 0

	def run(self) -> None:
		"""Execute the cipher upload process.

		This method continuously reads ciphers from the queue and uploads them to
		Google Drive in batches. It handles retries and error handling for uploads.

		Raises:
			Exception: If any error occurs during the execution.

		"""
		process_name = self.name
		if not self._authenticate_service():
			return

		bs = BatchState(1)

		with tqdm(total=self.total_ciphers, desc="Total Ciphers Uploaded") as pbar:
			while self.uploaded_count < self.total_ciphers:
				try:
					item = self.queue.get(timeout=5)
				except queue.Empty:
					continue

				if item == SENTINEL:
					break

				bs = self._process_cipher_item(item, bs, pbar)

			if bs.current_batch_count > 0:
				bs = self._upload_final_batch(bs, pbar)

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
		item: tuple[str, bytes],
		bs: BatchState,
		pbar: tqdm,
	) -> BatchState:
		"""Process a single cipher item, adding it to the batch.

		Args:
			item (tuple[str, bytes]): The cipher item containing filename and bytes.
			bs (BatchState): The current BatchState object.
			pbar (tqdm): The progress bar to update.

		Returns:
			BatchState: The updated (or new) BatchState object.

		"""
		filename, file_bytes = item

		bs.zip_buffer.writestr(filename, file_bytes)
		bs.current_batch_count += 1

		if bs.current_batch_count < BATCH_SIZE:
			return bs

		bs.zip_buffer.close()

		batch_filename = f"ciphers_batch_{bs.batch_num}.zip"

		return self._upload_batch(bs, pbar, batch_filename)

	def _upload_final_batch(self, bs: BatchState, pbar: tqdm) -> BatchState:
		"""Upload the final batch of ciphers to Google Drive.

		Args:
			bs (BatchState): The current BatchState object.
			pbar (tqdm): The progress bar to update.

		Returns:
			BatchState: The updated BatchState object.

		"""
		log.info(f"Uploading final partial batch of {bs.current_batch_count} files.")
		bs.zip_buffer.close()

		batch_filename = f"ciphers_batch_final_{bs.batch_num}.zip"

		return self._upload_batch(bs, pbar, batch_filename)

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
			BatchState: The updated BatchState object.

		"""
		try:
			file_id = upload_to_drive(
				self.drive_service,
				bs.batch_buffer.getvalue(),
				batch_filename,
				self.folder_id,
			)

			if file_id:
				self.uploaded_count += bs.current_batch_count
				pbar.update(bs.current_batch_count)
				log.info(f"Uploaded Batch {bs.batch_num} to Drive: {file_id}")

				return BatchState(batch_num=bs.batch_num + 1)
			else:
				log.critical(
					f"FATAL: Batch {bs.batch_num} failed all retries and was skipped.",
				)
				return BatchState(batch_num=bs.batch_num + 1)

		except Exception as e:
			log.error(
				f"FATAL: Unexpected error during upload of Batch {bs.batch_num}: {e}",
				exc_info=True,
			)
			return BatchState(batch_num=bs.batch_num + 1)
