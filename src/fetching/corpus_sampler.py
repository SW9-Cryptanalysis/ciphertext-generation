from typing import Iterator, Iterable
from itertools import islice

from utils.constants import BOOK_IDS_VALIDATION, TOTAL_BOOKS
from utils.text_splits import (
	get_split,
	get_book_chunks,
	get_actual_take,
	get_usable_text,
	TextStream,
)

from utils.validators import validate_targets
from parameter_validator import parameter_validator



class CorpusSampler:
	"""Manages the stateful extraction of texts across dataset splits."""

	@parameter_validator(targets=validate_targets)
	def __init__(
		self,
		targets: dict[str, int],
		len_bounds: tuple[int, int],
		genre_map: dict[str, list[str]],
	) -> None:
		"""Initialize the CorpusSampler.

		Args:
			targets (dict[str, int]): The target number of samples for each split.
			len_bounds (tuple[int, int]): The minimum and maximum length bounds.
			genre_map (dict[str, list[str]]): The genre map to use for filtering.

		"""
		self.targets = targets
		self.len_bounds = len_bounds
		self.genre_map = genre_map

		# State tracked across the entire stream
		self.counts = {"train": 0, "val": 0, "test": 0}
		self.debts = {"train": 0.0, "val": 0.0, "test": 0.0}
		self.means = {
			"val": targets["val"] / (TOTAL_BOOKS * 0.01),
			"test": targets["test"] / (TOTAL_BOOKS * 0.01),
			"train": targets["train"] / (TOTAL_BOOKS * 0.98),
		}

	def is_complete(self) -> bool:
		"""Check if all target quotas have been met."""
		return all(self.counts[k] >= self.targets[k] for k in self.targets)

	def generate_stream(self, stream: Iterable) -> Iterator[tuple[str, TextStream]]:
		"""Yield chunks until all targets are met."""
		for idx, book in enumerate(stream):
			if self.is_complete():
				break

			book_id = str(book.get("id", ""))
			if book_id in BOOK_IDS_VALIDATION:
				continue

			split = get_split(idx)
			if self.counts[split] >= self.targets[split]:
				continue

			yield from self._process_book(book, split)

	def _process_book(self, book: dict, split: str) -> Iterator[tuple[str, TextStream]]:
		"""Handle the extraction and debt calculation for a single book."""
		raw_text = book["text"]
		usable_text = get_usable_text(raw_text, self.len_bounds)

		safe_capacity_req = int(self.len_bounds[1] * 1.5)
		capacity = len(usable_text) // safe_capacity_req

		self.debts[split] += self.means[split]
		actual_take = get_actual_take(split, self.debts, capacity)

		if actual_take == 0:
			return

		take_limit = min(actual_take, self.targets[split] - self.counts[split])

		for chunk, bounded_chunk in islice(
			get_book_chunks(usable_text, actual_take, self.len_bounds),
			take_limit,
		):
			yield (
				split,
				{
					"text": chunk,
					"text_with_boundaries": bounded_chunk,
					"source_id": book.get("id", "unknown"),
					"source_name": book.get("metadata", {}).get("title", "unknown"),
					"length": len(chunk),
					"genres": self.genre_map.get(str(book.get("id")), []),
				},
			)
			self.counts[split] += 1

		self.debts[split] -= actual_take
