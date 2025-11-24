import multiprocessing as mp
from multiprocessing.queues import Queue as MPQueue
from utils.drive import create_cipher_json
from utils.logging import get_colored_logger
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from text_fetching.fetcher import Fetcher
import os
from typing import Any

log = get_colored_logger("cipher_producer")


class CipherProducer(mp.Process):
	"""A multiprocessing process for generating ciphers.

	Attributes:
		queue (MPQueue[Any]): The queue to add ciphers to.
		start_idx (int): The start index for the cipher generation.
		total_to_generate (int): The total number of ciphers to generate.

	Methods:
		run(): Execute the cipher generation process.

	"""

	MIN_LEN = 400
	MAX_LEN = 1000

	def __init__(
		self,
		queue: MPQueue[Any],
		start_and_total: tuple[int, int],
		*args: Any,
		**kwargs: Any,
	) -> None:
		"""Initialize the CipherProducer with a queue and start and total.

		Args:
			queue (MPQueue[Any]): The queue to add ciphers to.
			start_and_total (tuple[int, int]): A tuple containing the start and total
				indices for the cipher generation.
			*args: Additional positional arguments.
			**kwargs: Additional keyword arguments.

		"""
		super().__init__(*args, **kwargs)
		self.start_idx, self.total_to_generate = start_and_total
		self.queue = queue

	def run(self) -> None:
		"""Execute the cipher generation process.

		This method continuously generates ciphers and adds them to the queue.
		It handles errors and retries for cipher generation.

		Raises:
			Exception: If any error occurs during the execution.

		"""
		try:
			self.fetcher = Fetcher()
		except Exception as e:
			log.critical(f"Error creating Fetcher: {e}")
			return

		process_name = self.name

		for i in range(self.start_idx, self.start_idx + self.total_to_generate):
			try:
				cipher = self.generate_cipher()
				_, file_bytes = create_cipher_json(cipher)

				filename = (
					f"c_{len(cipher.plaintext)}_"
					f"{cipher.difficulty}_{i}_{os.getpid()}.json"
				)

				self.queue.put((filename, file_bytes))

			except Exception as e:
				log.error(f"Producer {process_name} failed on cipher {i}: {e}")

		log.info(f"{process_name} finished generation.")

	def generate_cipher(self) -> SubstitutionCipher:
		"""Generate a cipher from a random book slice and save it to a JSON file.

		Args:
			min_len (int): The minimum length of the text slice.
			max_len (int): The maximum length of the text slice.
			difficulty (int | None): The difficulty level for the cipher (4-30).
				If None, a random difficulty will be chosen.

		"""
		fetcher = Fetcher()
		book_text = fetcher.fetch_random_book_text()
		sliced_text = fetcher.get_random_book_slice(
			book_text,
			self.MIN_LEN,
			self.MAX_LEN,
		)

		try:
			cipher = HomophonicCipher(sliced_text)
			cipher.generate_difficulty()
			cipher.generate_key()
			cipher.encipher()
		except ValueError as e:
			log.error(f"Error generating cipher for book id: {self.fetcher.book_id}")
			raise e

		return cipher
