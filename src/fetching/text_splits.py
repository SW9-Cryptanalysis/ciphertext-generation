import os
import dotenv
import random
import re
from itertools import islice

from typing import Iterator, Iterable
from typing_extensions import TypedDict

from datasets import load_dataset
from datasets.iterable_dataset import IterableDataset

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


def clean_whitespace(text: str) -> str:
	"""Remove newlines, tabs, and multiple spaces from the input text.

	Args:
		text (str): The input text.

	Returns:
		str: The text with all unnecessary whitespace removed.

	"""
	# NOTE: Perhaps just remove all whitespace? Depends on num2words #noqa: ERA001
	text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
	text = re.sub(r"\s+", " ", text)
	return text.strip()


def extract_random_chunk(
	text: str,
	zone_start: int,
	zone_size: int,
	len_bounds: tuple[int, int],
) -> str:
	"""Extract a random chunk of text from the provided text.

	The chunk is aligned to word boundaries and has a random length between the
	provided min and max length bounds.

	Args:
		text (str): The input text to extract the chunk from.
		zone_start (int): The start index of the zone to extract the chunk from.
		zone_size (int): The size of the zone to extract the chunk from.
		len_bounds (tuple[int, int]): The minimum and maximum length bounds for the
			chunk.

	Returns:
		str: The extracted chunk of text.

	"""
	min_len, max_len = len_bounds
	target_len = random.randint(min_len, max_len)

	max_start = max(0, zone_size - target_len)
	raw_start = zone_start + random.randint(0, max_start)

	start_idx, end_idx = find_boundaries(text, raw_start, target_len)
	return text[start_idx:end_idx]


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
	book_text: str,
	actual_take: int,
	len_bounds: tuple[int, int],
) -> Iterator[str]:
	"""Extract a random chunk of text from the provided book text.

	The chunk is aligned to word boundaries and has a random length between the
	provided min and max length bounds.

	Args:
		book_text (str): The entire text of the book.
		actual_take (int): The number of chunks to extract.
		len_bounds (tuple[int, int]): The minimum and maximum length bounds for the
			chunks.

	Yields:
		Iterator[str]: An iterator of text chunks.

	"""
	zone_size = len(book_text) // actual_take

	for i in range(actual_take):
		raw_chunk = extract_random_chunk(
			book_text,
			i * zone_size,
			zone_size,
			len_bounds,
		)
		yield clean_whitespace(raw_chunk)


def text_streams_generator(
	stream: Iterable,
	total_samples_map: dict[str, int],  # e.g. {"train": 1000000, "val": 15000}
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
		capacity = len(raw_text) // len_bounds[1]

		debts[split] += means[split]
		actual_take = max(min(int(debts[split]), capacity), 1)

		if actual_take == 0:
			continue

		take_limit = min(actual_take, total_samples_map[split] - counts[split])

		for chunk in islice(
			get_book_chunks(raw_text, actual_take, len_bounds),
			take_limit,
		):
			yield (
				split,
				{
					"text": chunk,
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
