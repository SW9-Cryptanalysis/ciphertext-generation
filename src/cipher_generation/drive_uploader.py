import multiprocessing as mp
import queue
import os
import zipfile
from typing import Any
from multiprocessing.queues import Queue as MPQueue
from utils.logging import get_logger_tqdm
from dataclasses import dataclass
from utils.drive import (
	authenticate_drive_terminal,
	upload_to_drive,
)
from tqdm import tqdm

log = get_logger_tqdm("DriveUploader", 20)
SENTINEL = "STOP"


@dataclass
class Item:
	"""A dataclass representing a packaged file ready for upload.

	Attributes:
		split (str): The dataset split identifier.
		filepath (str): The local path to the generated file.
		filename (str): The destination filename on Google Drive.
		cipher_count (int): The number of ciphers contained in the file.

	"""

	split: str
	filepath: str
	filename: str
	cipher_count: int


@dataclass
class DriveUploaderConfig:
	"""A dataclass to store the configuration for the DriveUploader."""

	split_folders: dict[str, str]
	total_ciphers: int
	tqdm_lock: Any


class DriveUploader(mp.Process):
	"""A multiprocessing process for uploading files from disk to Google Drive."""

	def __init__(
		self,
		upload_queue: MPQueue[Any],
		config: DriveUploaderConfig,
		*args: Any,
		**kwargs: Any,
	) -> None:
		"""Initialize the DriveUploader.

		Args:
			upload_queue (MPQueue[Any]): The queue to use for communication.
			config (DriveUploaderConfig): The configuration for the uploader.
			*args: Additional arguments to pass to the parent class.
			**kwargs: Additional keyword arguments to pass to the parent class.

		"""
		super().__init__(*args, **kwargs)
		self.queue = upload_queue
		self.split_folders = config.split_folders
		self.total_ciphers = config.total_ciphers
		self.tqdm_lock = config.tqdm_lock
		self.drive_service = None
		self.uploaded_count = 0

	def run(self) -> None:
		"""Execute the cipher upload process."""
		process_name = self.name
		if not self._authenticate_service():
			return

		val_files: list[tuple[str, int]] = []
		test_files: list[tuple[str, int]] = []

		tqdm.set_lock(self.tqdm_lock)

		with tqdm(
			total=self.total_ciphers,
			desc="Total Ciphers Uploaded",
			position=1,
			leave=True,
		) as pbar:
			while True:
				try:
					queue_payload = self.queue.get(timeout=5)
				except queue.Empty:
					pbar.refresh()
					continue

				if queue_payload == SENTINEL:
					# The pipeline is done! Merge and upload the hoarded val/test files
					self._merge_and_upload("val", val_files, pbar)
					self._merge_and_upload("test", test_files, pbar)
					break

				# Catch the MERGE signal from workers
				if queue_payload[0] == "MERGE":
					self._hoard_files(queue_payload, val_files, test_files)
					continue

				split, filepath, filename, cipher_count = queue_payload
				upload_item = Item(
					split=split,
					filepath=filepath,
					filename=filename,
					cipher_count=cipher_count,
				)
				self._upload_file(upload_item, pbar)

		log.info(
			f"{process_name} finished. Total uploaded: {self.uploaded_count} ciphers.",
		)

	def _hoard_files(
		self,
		queue_payload: tuple[str, str, str, int],
		val_files: list[tuple[str, int]],
		test_files: list[tuple[str, int]],
	) -> None:
		"""Extract the filepath and count from a MERGE signal and store it.

		Args:
			queue_payload (tuple[str, str, str, int]): The payload from the queue.
			val_files (list[tuple[str, int]]): The list of val files to hoard.
			test_files (list[tuple[str, int]]): The list of test files to hoard.

		"""
		split, filepath, cipher_count = (
			queue_payload[1],
			queue_payload[2],
			queue_payload[3],
		)
		if split == "val":
			val_files.append((filepath, cipher_count))
		elif split == "test":
			test_files.append((filepath, cipher_count))

	def _merge_and_upload(
		self,
		split: str,
		files: list[tuple[str, int]],
		pbar: tqdm,
	) -> None:
		"""Merge multiple raw JSONL files into a single ZIP archive and upload it."""
		if not files:
			return

		log.info(f"Merging {len(files)} raw files for {split} split...")
		total_count = sum(c for _, c in files)
		archive_name = f"{split}_final.zip"
		zip_filepath = os.path.join("temp_ciphers", archive_name)
		internal_filename = f"{split}_merged.jsonl"

		with (
			zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zf,
			zf.open(
				internal_filename,
				"w",
			) as dest,
		):
			for filepath, _ in files:
				with open(filepath, "rb") as src:
					while True:
						chunk = src.read(1024 * 1024 * 10)
						if not chunk:
							break
						dest.write(chunk)
				os.remove(filepath)

		upload_item = Item(
			split=split,
			filepath=zip_filepath,
			filename=archive_name,
			cipher_count=total_count,
		)
		self._upload_file(upload_item, pbar)

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
		"""Upload a completed file from disk to Google Drive and delete it locally."""
		folder_id = self.split_folders.get(item.split)

		if not folder_id:
			log.error(
				f"Cannot upload {item.filename}: No folder ID found for '{item.split}'",
			)
			return

		try:
			with open(item.filepath, "rb") as f:
				file_bytes = f.read()

			file_id = upload_to_drive(
				self.drive_service,
				file_bytes,
				item.filename,
				folder_id,
			)

			if file_id:
				self.uploaded_count += item.cipher_count
				pbar.update(item.cipher_count)
				log.info(f"Uploaded {item.filename} to {item.split} folder: {file_id}")

				os.remove(item.filepath)
			else:
				log.error(f"FATAL: Failed to upload {item.filename} to {item.split}.")

		except Exception as e:
			log.error(
				f"FATAL: Unexpected error uploading {item.filename}: {e}",
				exc_info=True,
			)
