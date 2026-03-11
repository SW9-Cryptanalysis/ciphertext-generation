import multiprocessing as mp
import os
import queue
import json
import zipfile
from typing import Any, TypedDict
from multiprocessing.queues import Queue as MPQueue

from utils.logging import get_logger_tqdm
from encipherment.cipher import SubstitutionCipher, HomophonicCipher
from utils.text_splits import TextStream
from dataset_stats import DatasetStatsAggregator
from utils.constants import PROJECT_ROOT
from pathlib import Path

log = get_logger_tqdm("CipherProducer", 20)


class FileInfo(TypedDict):
	"""A typed dictionary for tracking open file handles and paths."""

	handle: Any
	filepath: str


class CipherProducer(mp.Process):
	"""A multiprocessing process for generating and streaming ciphers to disk."""

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
		self.temp_dir = Path(PROJECT_ROOT) / "temp_ciphers"

	def run(self) -> None:
		"""Execute the cipher generation process loop."""
		stats = DatasetStatsAggregator()
		process_name = self.name

		os.makedirs(self.temp_dir, exist_ok=True)

		batch_indices: dict[str, int] = {"train": 0, "val": 0, "test": 0}
		current_counts: dict[str, int] = {"train": 0, "val": 0, "test": 0}
		files = dict[str, FileInfo]()

		log.info(f"{process_name} started.")

		while True:
			try:
				item = self.input_queue.get(timeout=5)

				if item == "STOP":
					self._cleanup_all(
						files,
						current_counts,
						batch_indices,
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

				if split not in files:
					self._open_new_batch_file(split, batch_indices, files)

				cipher_str = json.dumps(cipher.__json__())
				files[split]["handle"].write(cipher_str + "\n")
				current_counts[split] += 1

				if current_counts[split] >= self.batch_size and split == "train":
					self._close_and_zip_batch(
						split,
						batch_indices,
						files,
						current_counts[split],
					)
					current_counts[split] = 0
					batch_indices[split] += 1
					del files[split]

			except queue.Empty:
				continue
			except Exception as e:
				log.error(f"Producer {process_name} failed: {e}")

		log.info(f"{process_name} finished generation.")


	def _hanle_cipher(
		self, cipher: SubstitutionCipher, split: str, files: dict[str, FileInfo]
	) -> None:
		"""Handle the generation of a cipher and write it to the appropriate file."""

	def _open_new_batch_file(
		self,
		split: str,
		batch_indices: dict[str, int],
		files: dict[str, Any],
	) -> None:
		"""Open a new raw JSONL file for streaming."""
		filename = f"raw_batch_{split}_{os.getpid()}_{batch_indices[split]}.jsonl"
		filepath = os.path.join(self.temp_dir, filename)

		files[split] = {
			"handle": open(filepath, "w", encoding="utf-8"),
			"filepath": filepath,
		}

	def _close_and_zip_batch(
		self,
		split: str,
		batch_indices: dict[str, int],
		files: dict[str, Any],
		cipher_count: int,
	) -> None:
		"""Close the current JSONL file, zip it, queue it, and delete the raw file."""
		files[split]["handle"].close()

		raw_filepath = files[split]["filepath"]
		internal_filename = os.path.basename(raw_filepath)

		archive_name = f"batch_{split}_{os.getpid()}_{batch_indices[split]}.zip"
		zip_filepath = os.path.join(self.temp_dir, archive_name)

		with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zf:
			zf.write(raw_filepath, arcname=internal_filename)

		os.remove(raw_filepath)

		self.output_queue.put((split, zip_filepath, archive_name, cipher_count))

	def _cleanup_all(
		self,
		files: dict[str, Any],
		current_counts: dict[str, int],
		batch_indices: dict[str, int],
		stats: DatasetStatsAggregator,
	) -> None:
		"""Flush any open files, zip them, and send final stats."""
		for split in list(files.keys()):
			if current_counts[split] > 0:
				if split in ["val", "test"]:
					files[split]["handle"].close()
					self.output_queue.put(
						(
							"MERGE",
							split,
							files[split]["filepath"],
							current_counts[split],
						)
					)
				self._close_and_zip_batch(
					split,
					batch_indices,
					files,
					current_counts[split],
				)

		self.stats_queue.put(stats)

	def generate_cipher(self, text: TextStream) -> SubstitutionCipher | None:
		"""Generate a cipher from the provided text string."""
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
