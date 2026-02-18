import multiprocessing as mp
import os
import queue  # Standard queue for Empty exception
from typing import Any
from multiprocessing.queues import Queue as MPQueue

from utils.drive import create_cipher_json
from utils.logging import get_colored_logger
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from fetching.text_splits import TextStream

# Note: Fetcher import removed as it is no longer needed in the Producer

log = get_colored_logger("cipher_producer")


class CipherProducer(mp.Process):
	"""A multiprocessing process for generating ciphers from a shared input queue.

	Attributes:
		input_queue (MPQueue[Any]): Queue containing raw text data dicts.
		output_queue (MPQueue[Any]): Queue to send finished cipher JSONs/bytes to.

	"""

	def __init__(
		self,
		input_queue: MPQueue[Any],
		output_queue: MPQueue[Any],
		*args: Any,
		**kwargs: Any,
	) -> None:
		"""Initialize the CipherProducer.

		Args:
			input_queue (MPQueue): Queue to receive text chunks from.
			output_queue (MPQueue): Queue to send results to.
			*args: Additional arguments.
			**kwargs: Additional keyword arguments.

		"""
		super().__init__(*args, **kwargs)
		self.input_queue = input_queue
		self.output_queue = output_queue

	def run(self) -> None:
		"""Execute the cipher generation process loop."""
		process_name = self.name
		log.info(f"{process_name} started.")

		while True:
			try:
				item = self.input_queue.get(timeout=5)

				if item == "STOP":
					log.info(f"{process_name} received STOP signal.")
					break

				cipher = self.generate_cipher(item)

				if cipher is None:
					continue

				_, file_bytes = create_cipher_json(cipher)

				filename = (
					f"c_{len(cipher.plaintext)}_{item["source_id"]}_"
					f"{cipher.difficulty}_{os.getpid()}.json"
				)

				# Send to Uploader
				self.output_queue.put((filename, file_bytes))

			except queue.Empty:
				continue
			except Exception as e:
				log.error(f"Producer {process_name} failed: {e}")

		log.info(f"{process_name} finished generation.")

	def generate_cipher(self, text: TextStream) -> SubstitutionCipher | None:
		"""Generate a cipher from the provided text string.

		Args:
			text (TextStream): The text chunk with metadata to encrypt.

		"""
		try:
			# We assume 'text' is already the correct length/slice
			# because the generator handled MIN/MAX_LEN bounds.
			cipher = HomophonicCipher(text)

			# Use random difficulty if that is the logic
			cipher.generate_difficulty()
			cipher.generate_key()
			cipher.encipher()

			return cipher

		except ValueError as e:
			log.error(f"Error generating cipher: {e}")
			return None
		except Exception as e:
			log.error(f"Unexpected cipher generation error: {e}")
			return None
