import random
from typing import Iterator
from typing_extensions import TypedDict
from datasets.iterable_dataset import IterableDataset

from utils.formatting import format_text, clean_spaces


class TextStream(TypedDict):
	"""A text stream object.

	A text stream object contains the text, source ID, source name, and length.
	"""

	text: str
	text_with_boundaries: str
	source_id: str
	source_name: str
	length: int
	genres: list[str]


def find_boundaries(
	raw_text: str,
	start_raw_idx: int,
	target_length: int,
) -> tuple[int, int]:
	"""Search for the boundaries of a target in the raw text.

	Args:
		raw_text (str): String to search in.
		start_raw_idx (int): Index to start searching from.
		target_length (int): Target length for the boundaries.

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
	"""Randomize the order of the stream.

	Args:
		stream (IterableDataset): The stream to randomize.

	Returns:
		IterableDataset: The randomized stream.

	"""
	return stream.shuffle(seed=42, buffer_size=100)


def find_spaceless_target_index(spaced_text: str, target_len: int) -> int:
	"""Find the index in a spaced string that corresponds to a spaceless length.

	Args:
		spaced_text (str): String to search in.
		target_len (int): Target length for the index.

	Returns:
		int: The index in the spaced string that corresponds to the target length.

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
	"""Extract a random chunk of text dynamically with and without word boundaries.

	Args:
		text (str): The raw text to extract the chunk from.
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
			" ",
			"_",
		)

	spaced_target_len = find_spaceless_target_index(spaced_window, target_len)
	start_idx, end_idx = find_boundaries(spaced_window, 0, spaced_target_len)

	final_chunk = spaced_window[start_idx:end_idx]

	unbounded_text = clean_spaces(final_chunk).strip()
	bounded_text = final_chunk.strip().replace(" ", "_")

	return unbounded_text, bounded_text


def get_split(idx: int) -> str:
	"""Get the split for a given index.

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

	Args:
		text (str): String to extract the chunk from.
		actual_take (int): The number of chunks to extract.
		len_bounds (tuple[int, int]): The minimum and maximum length bounds.

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


def get_actual_take(split: str, debts: dict[str, float], capacity: int) -> int:
	"""Get the actual take for a given split."""
	actual_take = max(min(int(debts[split]), capacity), 1) if capacity > 0 else 0
	return actual_take


def get_usable_text(raw_text: str, len_bounds: tuple[int, int]) -> str:
	"""Get the usable text from the raw text."""
	total_len = len(raw_text)
	start_trim = min(int(total_len * 0.02), 10000)
	end_trim = min(int(total_len * 0.01), 5000)

	if total_len < len_bounds[1] * 3:
		usable_text = raw_text
	else:
		usable_text = raw_text[start_trim : total_len - end_trim]
	return usable_text
