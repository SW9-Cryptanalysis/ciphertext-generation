import os
import multiprocessing as mp
from utils.logging import get_colored_logger
from drive.cipher_producer import CipherProducer
from drive.drive_uploader import DriveUploader, DriveUploaderConfig


log = get_colored_logger("cipher_manager")


class CipherManager:
	"""Orchestrates the parallel Producer-Consumer architecture for cipher generation.

	Attributes:
		TOTAL_CIPHERS (int): The total number of ciphers to generate.
		SENTINEL (str): A sentinel value to signal the Consumer to finish.
		folder_id (str): The ID of the folder to upload the ciphers to.
		num_producers (int): The number of producer processes to use.
		manager (mp.Manager): A manager for the Queue shared between processes.
		queue (mp.Queue): A Queue shared between processes for communication.

	Methods:
		execute(): Execute the cipher generation and upload process.

	"""

	# Class constants for configuration
	TOTAL_CIPHERS: int = 2_000_000
	SENTINEL: str = "STOP"

	def __init__(self, folder_id: str) -> None:
		"""Initialize the CipherManager with a folder ID.

		Args:
			folder_id (str): The ID of the folder to upload the ciphers to.

		"""
		self.folder_id = folder_id
		# Determine number of worker processes based on available cores
		self.num_producers = os.cpu_count() or 4

		# Use a Manager to create a Queue that can be safely shared between processes
		self.manager = mp.Manager()
		self.queue = self.manager.Queue()

	def _divide_workload(self) -> list[tuple[int, int]]:
		"""Calculate the start index and total count for each producer.

		Returns:
			list[tuple[int, int]]: A list of tuples containing the start
				index and total count for each producer.

		"""
		ciphers_per_producer = self.TOTAL_CIPHERS // self.num_producers

		workload = []
		current_start = 0

		for i in range(self.num_producers):
			count = ciphers_per_producer

			# The last worker handles any remainder
			if i == self.num_producers - 1:
				count = self.TOTAL_CIPHERS - current_start

			if count > 0:
				workload.append((current_start, count))
				current_start += count

		return workload

	def execute(self) -> None:
		"""Execute the cipher generation and upload process.

		This method starts the Consumer (I/O-Bound) and Producer (CPU-Bound) processes.
		It then waits for the Producers to finish and signals the Consumer to finish.
		The Consumer then waits for the final batch upload to complete and exits.

		Raises:
			Exception: If any error occurs during the execution.

		"""
		log.info(f"Starting cipher generation job. Total ciphers: {self.TOTAL_CIPHERS}")
		log.info(f"Using {self.num_producers} CPU producer processes.")

		consumer_process = DriveUploader(
			queue=self.queue,  # type: ignore
			config=DriveUploaderConfig(
				folder_id=self.folder_id,
				total_ciphers=self.TOTAL_CIPHERS,
			),
			name="Uploader-Consumer",
		)
		consumer_process.start()
		log.info(f"Consumer process started: {consumer_process.name}")

		workload = self._divide_workload()
		producer_pool = []

		for i, (start, count) in enumerate(workload):
			p = CipherProducer(
				queue=self.queue,  # type: ignore
				start_and_total=(start, count),
				name=f"Generator-Producer-{i + 1}",
			)
			producer_pool.append(p)
			p.start()

		log.info(
			f"Started {len(producer_pool)} Producer processes."
			"Generation in progress...",
		)

		# --- 3. Wait for Producers to finish ---
		for p in producer_pool:
			p.join()

		log.info("All Producers have finished generating ciphers.")

		# --- 4. Signal the Consumer to finish ---
		# Send a sentinel for every producer that finished. The consumer will check
		# for these to confirm all expected data is received before exiting its loop.
		for _ in range(len(producer_pool)):
			self.queue.put(self.SENTINEL)

		# --- 5. Wait for the Consumer to finish ---
		# This blocks until the consumer has uploaded the final batch and exited.
		consumer_process.join()

		log.info("✅ All processes complete. Job finished successfully.")
