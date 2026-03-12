import multiprocessing as mp
import os
import queue
import json
import zipfile
from typing import Any, TypedDict
from dataclasses import dataclass
from multiprocessing.queues import Queue as MPQueue

from utils.logging import get_logger_tqdm
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from utils.text_splits import TextStream
from dataset_stats import DatasetStatsAggregator
from pathlib import Path

log = get_logger_tqdm("CipherProducer", 20)


class FileInfo(TypedDict):
	"""A typed dictionary for tracking open file handles and paths."""

	handle: Any
	filepath: Path
 
@dataclass
class ProducerConfig:
	"""A dataclass to store the configuration for the CipherProducer."""

	batch_size: int
	input_queue: MPQueue[Any]
	output_queue: MPQueue[Any]
	stats_queue: MPQueue[Any]
	temp_dir: Path


@dataclass
class BatchInfo:
	"""A dataclass to store the current batch information."""

	batch_indices: dict[str, int]
	files: dict[str, FileInfo]
	current_counts: dict[str, int]


class CipherProducer(mp.Process):
	"""A multiprocessing process for generating and streaming ciphers to disk."""

	def __init__(
		self,
		config: ProducerConfig,
		*args: Any,
		**kwargs: Any,
	) -> None:
		"""Initialize the CipherProducer.

		Args:
			queues (tuple[MPQueue[Any], MPQueue[Any], MPQueue[Any]]): The queues
				to use for communication.
			batch_size (int, optional): The batch size to use. Defaults to 10000.
			*args: Additional arguments to pass to the parent class.
			**kwargs: Additional keyword arguments to pass to the parent class.

		"""
		super().__init__(*args, **kwargs)
		self.input_queue = config.input_queue
		self.output_queue = config.output_queue
		self.stats_queue = config.stats_queue

		self.batch_size = config.batch_size
		self.temp_dir = config.temp_dir

	def run(self) -> None:
		"""Execute the cipher generation process loop."""
		stats = DatasetStatsAggregator()
		process_name = self.name

		os.makedirs(self.temp_dir, exist_ok=True)

		batch_indices: dict[str, int] = {"train": 0, "val": 0, "test": 0}
		current_counts: dict[str, int] = {"train": 0, "val": 0, "test": 0}
		files = dict[str, FileInfo]()

		batch_info = BatchInfo(batch_indices, files, current_counts)

		log.info(f"{process_name} started.")

		while True:
			try:
				item = self.input_queue.get(timeout=5)

				if item == "STOP":
					self._cleanup_all(
						batch_info,
						stats,
					)
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

				self._write_and_batch_cipher(split, cipher, batch_info)

			except queue.Empty:
				continue
			except Exception as e:
				log.error(f"Producer {process_name} failed: {e}")

		log.info(f"{process_name} finished generation.")

	def _write_and_batch_cipher(
		self,
		split: str,
		cipher: SubstitutionCipher,
		batch_info: BatchInfo,
	) -> None:
		"""Write the cipher to disk and zip the batch if the limit is reached."""
		if split not in batch_info.files:
			self._open_new_batch_file(split, batch_info)

		cipher_str = json.dumps(cipher.__json__())
		batch_info.files[split]["handle"].write(cipher_str + "\n")
		batch_info.current_counts[split] += 1

		if batch_info.current_counts[split] >= self.batch_size and split == "train":
			self._close_and_zip_batch(
				split,
				batch_info=batch_info,
			)
			batch_info.current_counts[split] = 0
			batch_info.batch_indices[split] += 1
			del batch_info.files[split]

	def _open_new_batch_file(
		self,
		split: str,
		batch_info: BatchInfo,
	) -> None:
		"""Open a new raw JSONL file for streaming."""
		filename = (
			f"raw_batch_{split}_{os.getpid()}_{batch_info.batch_indices[split]}.jsonl"
		)
		filepath = self.temp_dir / filename

		batch_info.files[split] = {
			"handle": open(filepath, "w", encoding="utf-8"),  # noqa: SIM115
			"filepath": filepath,
		}

	def _close_and_zip_batch(
		self,
		split: str,
		batch_info: BatchInfo,
	) -> None:
		"""Close the current JSONL file, zip it, queue it, and delete the raw file."""
		batch_info.files[split]["handle"].close()

		filepath = batch_info.files[split]["filepath"]

		archive_name = (
			f"batch_{split}_{os.getpid()}_{batch_info.batch_indices[split]}.zip"
		)
		zip_filepath = self.temp_dir / archive_name

		with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zf:
			zf.write(filepath, arcname=filepath.name)

		os.remove(filepath)

		self.output_queue.put(
			(split, zip_filepath, archive_name, batch_info.current_counts[split]),
		)

	def _cleanup_all(
		self,
		batch_info: BatchInfo,
		stats: DatasetStatsAggregator,
	) -> None:
		"""Flush any open files, zip them, and send final stats."""
		for split in list(batch_info.files.keys()):
			if batch_info.current_counts[split] > 0:
				if split in ["val", "test"]:
					batch_info.files[split]["handle"].close()
					self.output_queue.put(
						(
							"MERGE",
							split,
							batch_info.files[split]["filepath"],
							batch_info.current_counts[split],
						),
					)
				else:  # <--- THIS IS THE CRITICAL FIX
					self._close_and_zip_batch(
						split,
						batch_info,
					)

		self.stats_queue.put(stats)

	def generate_cipher(self, text: TextStream) -> SubstitutionCipher | None:
		"""Generate a cipher from the provided text string.

		Args:
			text (TextStream): The text stream to generate the cipher from.

		Returns:
			SubstitutionCipher | None: The generated cipher, or None if
				an error occurred.

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
