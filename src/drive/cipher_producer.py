import multiprocessing as mp
import os
import queue
from typing import Any
from multiprocessing.queues import Queue as MPQueue

from multiprocessing.managers import ValueProxy
from threading import Lock

from utils.drive import create_cipher_json
from utils.logging import get_colored_logger
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from fetching.text_splits import TextStream


log = get_colored_logger("cipher_producer")


class CipherProducer(mp.Process):
	"""A multiprocessing process for generating ciphers from a shared input queue.

	Attributes:
		input_queue (MPQueue[Any]): Queue containing tuples of (split, text_data).
		output_queue (MPQueue[Any]): Queue to send tuples of
			(split, filename, file_bytes).
		max_symbol_tracker (tuple[ValueProxy[int], Lock]): A tuple containing a
			ValueProxy object and a Lock object to track the maximum symbol ID.

	"""

	def __init__(
		self,
		queues: tuple[MPQueue[Any], MPQueue[Any]],
		tracker: tuple[ValueProxy[int], Lock],
		*args: Any,
		**kwargs: Any,
	) -> None:
		"""Initialize the CipherProducer.

		Args:
			queues (tuple[MPQueue[Any], MPQueue[Any]]): A tuple containing two queues:
				input_queue and output_queue.
			tracker (tuple[ValueProxy[int], Lock]): A tuple containing a ValueProxy
				object and a Lock object to track the maximum symbol ID.
			*args: Additional arguments.
			**kwargs: Additional keyword arguments.

		"""
		super().__init__(*args, **kwargs)
		self.input_queue, self.output_queue = queues
		self.max_symbol_tracker, self.max_lock = tracker

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

				self._update_max_symbol_id(cipher.num_symbols)

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

	def _update_max_symbol_id(self, symbol_id: int) -> None:
		"""Update the max symbol ID tracker.

		Args:
			symbol_id (int): The new symbol ID to update the tracker with.

		"""
		if self.max_symbol_tracker is None or self.max_lock is None:
			return

		with self.max_lock:
			if symbol_id > self.max_symbol_tracker.value:
				self.max_symbol_tracker.value = symbol_id

	def generate_cipher(self, text: TextStream) -> SubstitutionCipher | None:
		"""Generate a cipher from the provided text string.

		Args:
			text (TextStream): The text chunk with metadata to encrypt.

		"""
		try:
			cipher = HomophonicCipher(text)

			cipher.generate_key()
			cipher.encipher()

			return cipher

		except ValueError as e:
			log.error(f"Error generating cipher: {e}")
			return None
		except Exception as e:
			log.error(f"Unexpected cipher generation error: {e}")
			return None
