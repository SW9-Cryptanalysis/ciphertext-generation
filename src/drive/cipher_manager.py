import multiprocessing as mp
from utils.logging import get_colored_logger
import os
from typing import Iterable

from drive.drive_uploader import DriveUploader, DriveUploaderConfig
from drive.cipher_producer import CipherProducer

log = get_colored_logger("cipher_manager")


class CipherManager:
	"""Orchestrates the parallel generation using Feeder -> Worker -> Uploader pattern.

	Attributes:
		folder_id (str): The folder ID to upload the ciphers to.
		text_stream_source (Iterable): The iterable source of text chunks.
		total_count (int): The total number of ciphers to generate.
		num_workers (int | None, optional): The number of workers to use.
			Defaults to None.

	Methods:
		execute(): Execute the cipher generation process.

	"""

	SENTINEL = "STOP"

	def __init__(
		self,
		folder_id: str,
		text_stream_source: Iterable,
		total_count: int,
		num_workers: int | None = None,
	) -> None:
		"""Initialize the CipherManager.

		Args:
			folder_id: The folder ID to upload the ciphers to.
			text_stream_source: Iterator yielding (split,text_data) from your generator.
			total_count: Total expected ciphers (for progress bars/logging).
			num_workers: Number of workers to use. Defaults to None.

		"""
		self.folder_id = folder_id
		self.stream = text_stream_source
		self.total_count = total_count

		self.num_workers = num_workers or max(1, (os.cpu_count() or 4) - 2)

		self.manager = mp.Manager()
		self.job_queue = self.manager.Queue(maxsize=1000)
		self.result_queue = self.manager.Queue()

	def execute(self) -> None:
		"""Execute the cipher generation process.

		Starts the Feeder -> Workers -> Uploader pattern.
		"""
		log.info(
			f"Starting job. Target: {self.total_count} ciphers"
			" using {self.num_workers} workers.",
		)

		uploader = DriveUploader(
			queue=self.result_queue,  # type: ignore
			config=DriveUploaderConfig(
				folder_id=self.folder_id,
				total_ciphers=self.total_count,
			),
			name="Uploader-Consumer",
		)
		uploader.start()

		workers = []
		for i in range(self.num_workers):
			p = CipherProducer(
				input_queue=self.job_queue,  # type: ignore
				output_queue=self.result_queue,  # type: ignore
				name=f"Worker-{i + 1}",
			)
			workers.append(p)
			p.start()

		log.info("Feeder started. Reading stream and filling queues...")

		count_fed = 0
		try:
			for split, text_data in self.stream:  # noqa B007
				self.job_queue.put(text_data)
				count_fed += 1

				if count_fed % 1000 == 0:
					log.info(f"Fed {count_fed} texts to workers...")

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

		self.result_queue.put(self.SENTINEL)

		uploader.join()
		log.info("✅ Job complete.")
