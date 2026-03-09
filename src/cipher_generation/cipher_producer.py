import multiprocessing as mp
import os
import queue
import json
import io
import zipfile
from typing import Any
from multiprocessing.queues import Queue as MPQueue

from utils.logging import get_logger
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from utils.text_splits import TextStream
from dataset_stats import DatasetStatsAggregator

log = get_logger("CipherProducer")


class CipherProducer(mp.Process):
	"""A multiprocessing process for generating ciphers in batched, zipped JSONL format.

	Attributes:
		input_queue (MPQueue[Any]): Queue containing tuples of (split, text_data).
		output_queue (MPQueue[Any]): Queue to send tuples of
			(split, archive_name, compressed_bytes, cipher_count).
		stats_queue (MPQueue[Any]): Queue to send aggregate dataset statistics.
		batch_size (int): The number of ciphers to accumulate before emitting a file.

	"""

	def __init__(
		self,
		queues: tuple[MPQueue[Any], MPQueue[Any], MPQueue[Any]],
		batch_size: int = 10000,
		*args: Any,
		**kwargs: Any,
	) -> None:
		"""Initialize the CipherProducer."""
		super().__init__(*args, **kwargs)
		self.input_queue, self.output_queue, self.stats_queue = queues
		self.batch_size = batch_size

	def run(self) -> None:
		"""Execute the cipher generation process loop."""
		stats = DatasetStatsAggregator()
		process_name = self.name
		batch_buffer: list[str] = []
		batch_index = 0

		log.info(f"{process_name} started.")

		while True:
			try:
				item = self.input_queue.get(timeout=5)

				if item == "STOP":
					self._cleanup(batch_buffer, batch_index, stats)
					log.info(f"{process_name} received STOP signal.")
					break

				split, text_obj = item
				cipher = self.generate_cipher(text_obj)

				if cipher is None:
					continue

				stats.record(
					split=split,
					length=len(cipher.plaintext),
					homophones=cipher.num_symbols,
					difficulty=cipher.difficulty or 0,
					genres=cipher.genres,
				)

				cipher_str = json.dumps(cipher.__json__())
				batch_buffer.append(cipher_str)

				if len(batch_buffer) >= self.batch_size:
					self._flush_batch(batch_buffer, split, batch_index)
					batch_buffer.clear()
					batch_index += 1

			except queue.Empty:
				continue
			except Exception as e:
				log.error(f"Producer {process_name} failed: {e}")

		log.info(f"{process_name} finished generation.")

	def _cleanup(
		self,
		batch_buffer: list[str],
		batch_index: int,
		stats: DatasetStatsAggregator,
	) -> None:
		"""Flush any remaining ciphers and send the final stats.

		Args:
			batch_buffer (list[str]): The list of cipher JSON strings in the current batch.
			batch_index (int): The current batch index.
			stats (DatasetStatsAggregator): The current dataset statistics.
		"""
		if batch_buffer:
			self._flush_batch(batch_buffer, "final", batch_index)

		self.stats_queue.put(stats)

	def _flush_batch(
		self,
		batch_buffer: list[str],
		split: str,
		batch_index: int,
	) -> None:
		"""Convert accumulated JSON strings into zipped JSONL byte stream and queue it.

		Args:
			batch_buffer (list[str]): List of single-line JSON strings.
			split (str): The dataset split identifier.
			batch_index (int): An incrementing integer to ensure unique filenames.

		"""
		jsonl_content = "\n".join(batch_buffer) + "\n"
		raw_bytes = jsonl_content.encode("utf-8")

		zip_buffer = io.BytesIO()
		internal_filename = f"batch_{split}_{os.getpid()}_{batch_index}.jsonl"

		with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
			zf.writestr(internal_filename, raw_bytes)

		compressed_bytes = zip_buffer.getvalue()
		archive_name = f"{internal_filename}.zip"
		cipher_count = len(batch_buffer)

		self.output_queue.put((split, archive_name, compressed_bytes, cipher_count))

	def generate_cipher(self, text: TextStream) -> SubstitutionCipher | None:
		"""Generate a cipher from the provided text string.

		Args:
			text (TextStream): Source text to generate a cipher from.

		Returns:
			SubstitutionCipher | None: The generated cipher, or None if an error occurred.
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
