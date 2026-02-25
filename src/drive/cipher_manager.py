import multiprocessing as mp
from utils.logging import get_colored_logger
import os
from typing import Iterable, Any
import json

from drive.drive_uploader import DriveUploader, DriveUploaderConfig
from drive.cipher_producer import CipherProducer

log = get_colored_logger("cipher_manager")


class CipherManager:
	"""Orchestrates the parallel generation using Feeder -> Worker -> Uploader pattern.

	Attributes:
		config (dict[str, dict[str, Any]]): Configuration dictionary mapping splits
			to their folder IDs and target counts.
		text_stream_source (Iterable): The iterable source of text chunks.
		total_count (int): The total number of ciphers to generate across all splits.
		split_folders (dict[str, str]): A mapping of splits to their folder IDs.
		num_workers (int): The number of workers to use.

	Methods:
		execute(): Execute the cipher generation process.

	"""

	SENTINEL = "STOP"

	def __init__(
		self,
		config: dict[str, dict[str, Any]],
		text_stream_source: Iterable,
		num_workers: int | None = None,
	) -> None:
		"""Initialize the CipherManager.

		Args:
			config: Configuration dictionary with count and folder_id per split.
			text_stream_source: Iterator yielding (split, text_data) from the generator.
			num_workers: Number of workers to use. Defaults to None.

		"""
		self.config = config
		self.stream = text_stream_source

		self.total_count = sum(split_data["count"] for split_data in config.values())
		self.split_folders = {
			split: split_data["folder_id"] for split, split_data in config.items()
		}

		self.num_workers = num_workers or max(1, (os.cpu_count() or 4) - 2)

		self.manager = mp.Manager()
		self.job_queue = self.manager.Queue(maxsize=1000)
		self.result_queue = self.manager.Queue()

		self.max_symbol_id = self.manager.Value("i", 0)
		self.max_lock = self.manager.Lock()

	def execute(self) -> None:
		"""Execute the cipher generation process."""
		log.info(
			f"Starting job. Target: {self.total_count} ciphers "
			f"using {self.num_workers} workers.",
		)

		uploader = DriveUploader(
			queue=self.result_queue,  # type: ignore
			config=DriveUploaderConfig(
				split_folders=self.split_folders,
				total_ciphers=self.total_count,
			),
			name="Uploader-Consumer",
		)
		uploader.start()

		workers = []
		for i in range(self.num_workers):
			p = CipherProducer(
				queues=(self.job_queue, self.result_queue),  # type: ignore
				tracker=(self.max_symbol_id, self.max_lock),
				name=f"Worker-{i + 1}",
			)
			workers.append(p)
			p.start()

		log.info("Feeder started. Reading stream and filling queues...")

		count_fed = 0
		try:
			count_fed = self._feeder_stream()

		except KeyboardInterrupt:
			log.warning("Job interrupted! Stopping...")
		except Exception as e:
			log.error(f"Stream error: {e}")
		finally:
			log.info(f"Stream finished. Fed {count_fed} items. Stopping workers...")
			for _ in range(self.num_workers):
				self.job_queue.put(self.SENTINEL)

		for p in workers:
			p.join()

		self._upload_metadata()
		self.result_queue.put(self.SENTINEL)

		uploader.join()

		log.info("=" * 40)
		log.info("JOB COMPLETE")
		log.info(f"Total ciphers fed: {count_fed}")
		log.info(f"Peak homophone ID (Vocab Size): {self.max_symbol_id.value}")
		log.info("=" * 40)

	def _upload_metadata(self) -> None:
		"""Upload the metadata file to Google Drive.

		This method uploads the metadata file to Google Drive, which contains
		the peak homophone ID (Vocab Size) of the generated ciphers.

		"""
		log.info("Uploading metadata file...")
		metadata_filename = "metadata.json"
		metadata_bytes = json.dumps({"max_symbol_id": self.max_symbol_id.value}).encode(
			"utf-8",
		)
		self.result_queue.put(("metadata", metadata_filename, metadata_bytes))

	def _feeder_stream(self) -> int:
		"""Feed the ciphers to the workers using the job queue.

		This method feeds the ciphers to the workers using the job queue. It
		handles routing by split and error handling.

		Raises:
			Exception: If any error occurs during the execution.

		"""
		log.info("Feeding ciphers to workers...")

		count_fed = 0

		for count_fed, (split, text_data) in enumerate(self.stream, start=1):
			self.job_queue.put((split, text_data))

			if count_fed % 1000 == 0:
				log.info(f"Fed {count_fed} texts to workers...")

			if count_fed >= self.total_count:
				log.info(f"Target of {self.total_count} reached. Stopping feeder.")
				break

		return count_fed
