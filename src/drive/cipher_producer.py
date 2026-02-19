import multiprocessing as mp
import os
import queue
from typing import Any
from multiprocessing.queues import Queue as MPQueue

from utils.drive import create_cipher_json
from utils.logging import get_colored_logger
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from fetching.text_splits import TextStream


log = get_colored_logger("cipher_producer")


class CipherProducer(mp.Process):
	"""A multiprocessing process for generating ciphers from a shared input queue.

	Attributes:
		input_queue (MPQueue[Any]): Queue containing tuples of (split, text_data).
		output_queue (MPQueue[Any]): Queue to send tuples of (split, filename, file_bytes).

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
			input_queue (MPQueue): Queue to receive split and text chunks from.
			output_queue (MPQueue): Queue to send split, filename, and bytes to.
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

				split, text_obj = item

				cipher = self.generate_cipher(text_obj)

				if cipher is None:
					continue

				_, file_bytes = create_cipher_json(cipher)

				filename = (
					f"c_{len(cipher.plaintext)}_{text_obj['source_id']}_"
					f"{cipher.difficulty}_{os.getpid()}.json"
				)

				self.output_queue.put((split, filename, file_bytes))

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
			cipher = HomophonicCipher(text)

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