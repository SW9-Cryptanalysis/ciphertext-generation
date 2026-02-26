import os
import dotenv
import random
from itertools import islice

from typing import Iterator, Iterable
from typing_extensions import TypedDict

from datasets import load_dataset
from datasets.iterable_dataset import IterableDataset

from utils.formatting import format_text, clean_spaces
from utils.constants import BOOK_IDS_VALIDATION, TOTAL_BOOKS, DATASET_NAME

dotenv.load_dotenv()


class BookMetadata(TypedDict):
	"""A book metadata object.

	A book metadata object contains the title, author, year, genre,
		and length of a book.
	"""

	title: str
	author: str
	year: int
	genre: str
	length: int


class Book(TypedDict):
	"""A book object.

	A book object contains the ID, metadata, and text of a book.
	"""

	id: str
	metadata: BookMetadata
	text: str


class TextStream(TypedDict):
	"""A text stream object.

	A text stream object contains the text, source ID, source name, and length of
	"""

	text: str
	text_with_boundaries: str
	source_id: str
	source_name: str
	length: int


def find_boundaries(
	raw_text: str,
	start_raw_idx: int,
	target_length: int,
) -> tuple[int, int]:
	"""Find the boundaries of a target in the raw text.

	This function finds the boundaries of a target in the raw text by searching
	for the first space character within a window of 200 characters before the
	start index and the next space character within a window of 200 characters
	after the end index.

	Args:
		raw_text (str): The raw text to search in.
		start_raw_idx (int): The start index to search from.
		target_length (int): The target length of the text within the boundaries.

	Returns:
		tuple[int, int]: The start and end indices of the target within the raw text.

	"""
	search_window = 200

	lookback_limit = max(0, start_raw_idx - search_window)
	first_space = raw_text.rfind(" ", lookback_limit, start_raw_idx)

	start_idx = first_space + 1 if first_space != -1 else start_raw_idx

	end_raw_idx = start_idx + target_length
	lookahead_limit = end_raw_idx + search_window

	end_idx = raw_text.find(" ", end_raw_idx, lookahead_limit)

	if end_idx == -1:
		end_idx = end_raw_idx

	return start_idx, end_idx


def randomize_stream(stream: IterableDataset) -> IterableDataset:
	"""Randomize the order of the stream."""
	return stream.shuffle(seed=42, buffer_size=100)


def find_spaceless_target_index(spaced_text: str, target_len: int) -> int:
	"""Find the index in a spaced string that corresponds to a spaceless length.

	Args:
		spaced_text (str): The text containing spaces.
		target_len (int): The target number of non-space characters.

	Returns:
		int: The index in the spaced text corresponding to the target length.

	"""
	non_space_count = 0

	for i, char in enumerate(spaced_text):
		if char.strip():
			non_space_count += 1
		if non_space_count == target_len:
			return i

	return len(spaced_text)


def extract_random_chunk(
	text: str,
	zone_start: int,
	zone_size: int,
	len_bounds: tuple[int, int],
) -> tuple[str, str]:
	"""Extract a random chunk of text dynamically while preserving word boundaries.

	The chunk is aligned to word boundaries and has a random length between the
	provided min and max length bounds. The chunk is also returned with spaces
	replaced with underscores.

	Args:
		text (str): The input text to extract the chunk from.
		zone_start (int): The start index of the zone to extract the chunk from.
		zone_size (int): The size of the zone to extract the chunk from.
		len_bounds (tuple[int, int]): The minimum and maximum length bounds.

	Returns:
		tuple[str, str]: A tuple containing the cleaned chunk of text both with
			spaces replaced with underscores and the spaces removed.

	"""
	min_len, max_len = len_bounds
	target_len = random.randint(min_len + 50, max_len - 50)

	max_start = max(0, zone_size - target_len)
	raw_start = zone_start + random.randint(0, max_start)

	spaced_window = ""
	raw_end = min(len(text), raw_start + (target_len * 2))

	while True:
		raw_window = text[raw_start:raw_end]
		spaced_window = format_text(raw_window)

		if len(clean_spaces(spaced_window)) >= target_len + 200 or raw_end >= len(text):
			break

		raw_end = min(len(text), raw_end + target_len)

	if len(clean_spaces(spaced_window)) < min_len:
		return clean_spaces(spaced_window).strip(), spaced_window.strip().replace(
			" ", "_",
		)

	spaced_target_len = find_spaceless_target_index(spaced_window, target_len)
	start_idx, end_idx = find_boundaries(spaced_window, 0, spaced_target_len)

	final_chunk = spaced_window[start_idx:end_idx]

	unbounded_text = clean_spaces(final_chunk).strip()
	bounded_text = final_chunk.strip().replace(" ", "_")

	return unbounded_text, bounded_text


def get_split(idx: int) -> str:
	"""Get the split for a given index.

	The split is determined by the index modulo 100 with a split of
	98% for the training set, 1% for the validation set, and 1% for the test set.

	Args:
		idx (int): The index to get the split for.

	Returns:
		str: The split for the index.

	"""
	if idx % 100 == 0:
		return "val"
	elif idx % 100 == 1:
		return "test"
	else:
		return "train"


def get_book_chunks(
	text: str,
	actual_take: int,
	len_bounds: tuple[int, int],
) -> Iterator[tuple[str, str]]:
	"""Extract a random chunk of text from the provided book text.

	The chunk is aligned to word boundaries and has a random length between the
	provided min and max length bounds.

	Args:
		text (str): The entire text of the book.
		actual_take (int): The number of chunks to extract.
		len_bounds (tuple[int, int]): The minimum and maximum length bounds for the
			chunks.

	Yields:
		Iterator[tuple[str, str]]: An iterator of text chunks with the clean text
			with spaces replaced with underscores and the spaces removed.

	"""
	zone_size = len(text) // actual_take

	for i in range(actual_take):
		chunk, bounded_chunk = extract_random_chunk(
			text,
			i * zone_size,
			zone_size,
			len_bounds,
		)

		chunk_len = len(chunk)

		if len_bounds[0] - 0.05 * len_bounds[0] <= chunk_len <= len_bounds[1]:
			yield chunk, bounded_chunk


def validate_targets(targets: dict[str, int]) -> None:
	"""Validate the targets dictionary.

	Args:
		targets (dict[str, int]): The targets dictionary to validate.

	Raises:
		ValueError: If any of the targets are not valid.

	"""
	required_keys = {"train", "val", "test"}
	if set(targets.keys()) != required_keys:
		raise ValueError(
			f"total_samples_map must contain exactly keys: {required_keys}",
		)


def get_actual_take(split: str, debts: dict[str, float], capacity: int) -> int:
	"""Get the actual take for a given split.

	Args:
		split (str): The split to get the actual take for.
		debts (dict[str, float]): The debts dictionary.
		capacity (int): The capacity of the split.

	Returns:
		int: The actual take for the split.

	"""
	actual_take = max(min(int(debts[split]), capacity), 1) if capacity > 0 else 0
	return actual_take


def get_usable_text(raw_text: str, len_bounds: tuple[int, int]) -> str:
	"""Get the usable text from the raw text.

	Args:
		raw_text (str): The raw text to get the usable text from.
		len_bounds (tuple[int, int]): The minimum and maximum length bounds for the
			text.

	Returns:
		str: The usable text.

	"""
	total_len = len(raw_text)
	start_trim = min(int(total_len * 0.02), 10000)
	end_trim = min(int(total_len * 0.01), 5000)
	if total_len < len_bounds[1] * 3:
		usable_text = raw_text
	else:
		usable_text = raw_text[start_trim : total_len - end_trim]
	return usable_text


def text_streams_generator(
	stream: Iterable,
	total_samples_map: dict[str, int],  # e.g. {"train": 1000, "val": 15, "test": 15}
	len_bounds: tuple[int, int],
) -> Iterator[tuple[str, TextStream]]:
	"""Generate a stream of text chunks from the provided dataset.

	Each chunk is aligned to word boundaries and has a random length between the
	provided min and max length bounds. The stream is split into 3 buckets:
	train, val, test. Each bucket is filled with chunks until it is full.

	Args:
		stream (IterableDataset): The dataset to extract the text chunks from.
		total_samples_map (dict[str, int]): A dictionary mapping each bucket to the
			total number of chunks to generate.
		len_bounds (tuple[int, int]): The minimum and maximum length bounds for
			the chunks.

	Yields:
		Iterator[tuple[str, TextStream]]: An iterator of text chunks.

	"""
	validate_targets(total_samples_map)
	means = {
		"val": total_samples_map["val"] / (TOTAL_BOOKS * 0.01),
		"test": total_samples_map["test"] / (TOTAL_BOOKS * 0.01),
		"train": total_samples_map["train"] / (TOTAL_BOOKS * 0.98),
	}

	debts = {"train": 0.0, "val": 0.0, "test": 0.0}
	counts = {"train": 0, "val": 0, "test": 0}

	for idx, book in enumerate(stream):
		if all(counts[k] >= total_samples_map[k] for k in total_samples_map):
			break

		if str(book["id"]) in BOOK_IDS_VALIDATION:
			continue
		split = get_split(idx)

		if counts[split] >= total_samples_map[split]:
			continue

		raw_text = book["text"]
		usable_text = get_usable_text(raw_text, len_bounds)

		safe_capacity_req = int(len_bounds[1] * 1.5)
		capacity = len(usable_text) // safe_capacity_req

		debts[split] += means[split]

		actual_take = get_actual_take(split, debts, capacity)

		if actual_take == 0:
			continue

		take_limit = min(actual_take, total_samples_map[split] - counts[split])

		for chunk, bounded_chunk in islice(
			get_book_chunks(usable_text, actual_take, len_bounds),
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
				},
			)
			counts[split] += 1

		debts[split] -= actual_take


def get_text_stream(
	targets: dict[str, int] | None = None,
	len_bounds: tuple[int, int] = (4000, 10000),
) -> Iterator[tuple[str, TextStream]]:
	"""Get a stream of text chunks from the dataset.

	Returns:
		Iterator[tuple[str, TextStream]]: An iterator of text chunks with a string
			identifier for the split and the TextStream object.

	"""
	if targets is None:
		targets = {
			"train": 1_000_000,
			"val": 10000,
			"test": 10000,
		}

	full_stream = randomize_stream(
		load_dataset(
			DATASET_NAME,
			split="train",
			streaming=True,
			token=os.environ["HF_TOKEN"],
		),
	)

	text_stream = text_streams_generator(full_stream, targets, len_bounds=len_bounds)

	return text_stream
