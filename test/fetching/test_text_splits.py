import pytest
import os
import random
from fetching import text_splits
from fetching.text_splits import (
	find_boundaries,
	find_spaceless_target_index,
	extract_random_chunk,
	get_split,
	get_book_chunks,
	get_usable_text,
	get_actual_take,
	validate_targets,
	clean_whitespace,
	text_streams_generator,
	get_text_stream,
	randomize_stream,
)

# --- Fixtures ---


@pytest.fixture
def sample_text():
	return "This is a sample text used for testing boundaries and extraction logic."


@pytest.fixture
def mock_book_stream():
	return [
		{
			"id": "1",
			"text": "Book One content " * 500,
			"metadata": {"title": "Book One"},
		},
		{
			"id": "2",
			"text": "Book Two content " * 500,
			"metadata": {"title": "Book Two"},
		},
		{
			"id": "3",
			"text": "Book Three content " * 500,
			"metadata": {"title": "Book Three"},
		},
	]


# --- Helper Function Tests ---


class TestTextHelpers:
	def test_find_boundaries_standard(self, sample_text):
		start, end = find_boundaries(sample_text, 10, 11)
		assert sample_text[start:end] == "sample text"

	def test_find_spaceless_target_index(self):
		text = "a b c d e"  # Spaced
		assert find_spaceless_target_index(text, 3) == 4
		assert find_spaceless_target_index(text, 10) == len(text)

	def test_get_split(self):
		assert get_split(0) == "val"
		assert get_split(1) == "test"
		assert get_split(2) == "train"
		assert get_split(100) == "val"

	def test_clean_whitespace(self):
		raw = "Line\nBreak\tTab   Multiple  Spaces"
		expected = "Line Break Tab Multiple Spaces"
		assert clean_whitespace(raw) == expected

	def test_clean_whitespace_multiple_regex_spaces(self):
		"""Line 90: Ensure regex replacement of multiple spaces is hit."""
		text = "word    word"
		assert clean_whitespace(text) == "word word"

	def test_validate_targets_valid(self):
		targets = {"train": 100, "val": 10, "test": 10}
		# Should not raise
		validate_targets(targets)

	def test_validate_targets_invalid(self):
		with pytest.raises(ValueError, match="must contain exactly keys"):
			validate_targets({"train": 100})

	def test_get_actual_take_logic(self):
		debts = {"train": 10.5}
		# Capacity is 5, debt is 10.5 -> Should take 5
		assert get_actual_take("train", debts, 5) == 5
		# Capacity is 20, debt is 10.5 -> Should take 10
		assert get_actual_take("train", debts, 20) == 10
		# Capacity is 0 -> Should take 0
		assert get_actual_take("train", debts, 0) == 0

	def test_get_usable_text_trimming(self):
		# 100,000 chars. 2% = 2000, 1% = 1000.
		raw = "A" * 100_000
		usable = get_usable_text(raw, (4000, 10000))
		assert len(usable) == 97_000

	def test_get_usable_text_short_book(self):
		# Book shorter than 3x max_len should not be trimmed
		raw = "Short book content"
		usable = get_usable_text(raw, (4000, 10000))
		assert usable == raw

	def test_randomize_stream(self, mocker):
		mock_stream = mocker.Mock()
		randomize_stream(mock_stream)
		mock_stream.shuffle.assert_called_once_with(seed=42, buffer_size=100)


# --- Core Logic Tests ---


class TestChunkExtraction:
	def test_extract_random_chunk_logic_flow(self, mocker):
		text = "wordone wordtwo wordthree wordfour"
		mocker.patch("random.randint", side_effect=[7, 0, 0, 0])
		mocker.patch("fetching.text_splits.format_text", side_effect=lambda x: x)

		chunk = extract_random_chunk(text, 0, len(text), (5, 15))

		assert " " not in chunk
		assert chunk == "wordone"

	def test_get_book_chunks_filters_length(self, mocker):
		min_bound = 1000
		# 960 is within 5% of 1000 (threshold 950)
		valid_chunk = "a" * 960
		invalid_chunk = "a" * 940

		mocker.patch(
			"fetching.text_splits.extract_random_chunk",
			side_effect=[valid_chunk, invalid_chunk],
		)

		chunks = list(
			get_book_chunks("dummy text", actual_take=2, len_bounds=(min_bound, 2000))
		)

		assert len(chunks) == 1
		assert chunks[0] == valid_chunk

	def test_get_book_chunks_clamping(self, mocker):
		# Test that chunks longer than max_len are clamped
		max_bound = 50
		long_chunk = "a" * 100
		mocker.patch(
			"fetching.text_splits.extract_random_chunk",
			return_value=long_chunk,
		)

		chunks = list(get_book_chunks("text", 1, (10, max_bound)))
		assert len(chunks[0]) == max_bound

	def test_extract_random_chunk_reaches_end_of_text(self, mocker):
		"""Line 175: Test when raw_end >= len(text) breaks the loop."""
		short_text = "This is very short."
		# Mock target_len to be larger than the text
		mocker.patch("random.randint", side_effect=[100, 0, 0])
		mocker.patch("fetching.text_splits.format_text", side_effect=lambda x: x)

		# This should trigger the break in the while loop at Line 175
		chunk = extract_random_chunk(short_text, 0, 10, (5, 150))
		assert len(chunk) > 0

	def test_extract_random_chunk_too_small_returns_immediately(self, mocker):
		"""Line 184: Test return when clean text < min_len."""
		text = "tiny"
		mocker.patch("random.randint", side_effect=[10, 0, 0])
		mocker.patch("fetching.text_splits.format_text", side_effect=lambda x: x)

		# min_len is 5, text is 4 chars
		chunk = extract_random_chunk(text, 0, 5, (5, 15))
		assert chunk == "tiny"


# --- Stream Generator Tests ---


class TestStreamGenerator:
	@pytest.fixture
	def mock_constants(self, mocker):
		mocker.patch("fetching.text_splits.TOTAL_BOOKS", 100)
		mocker.patch("fetching.text_splits.BOOK_IDS_VALIDATION", ["999"])

	def test_text_streams_generator_skips_blacklisted_ids(self, mocker, mock_constants):
		stream = [
			{
				"id": "good_id",
				"text": "valid content " * 1000,
				"metadata": {"title": "Good"},
			},
			{
				"id": "bad_id",
				"text": "invalid content " * 1000,
				"metadata": {"title": "Bad"},
			},
		]
		mocker.patch("fetching.text_splits.BOOK_IDS_VALIDATION", ["bad_id"])
		targets = {"train": 1, "val": 0, "test": 0}
		len_bounds = (500, 1000)
		mocker.patch("fetching.text_splits.get_split", return_value="train")

		results = list(text_streams_generator(stream, targets, len_bounds))

		assert len(results) > 0
		assert all(data["source_id"] == "good_id" for _, data in results)

	def test_text_streams_generator_skips_validation_ids(self, mocker, mock_constants):
		# Force ID '999' into the blacklist (set via mock_constants fixture)
		stream = [
			{"id": "999", "text": "content " * 1000, "metadata": {}},
			{"id": "valid", "text": "content " * 1000, "metadata": {}}
		]
		targets = {"train": 1, "val": 0, "test": 0}
		mocker.patch("fetching.text_splits.get_split", return_value="train")
		
		gen = text_streams_generator(stream, targets, (500, 1000))
		results = list(gen)
		
		# Only 'valid' should produce a result
		assert len(results) == 1
		assert results[0][1]["source_id"] == "valid"

	def test_text_streams_generator_debt_and_take(self, mocker, mock_constants):
		# Ensure that debt carries over and influences actual_take
		stream = [
			{"id": "1", "text": "content " * 2000, "metadata": {"title": "B1"}},
		]
		# Very high target to force high mean/debt
		targets = {"train": 100, "val": 1, "test": 1}
		len_bounds = (500, 1000)
		mocker.patch("fetching.text_splits.get_split", return_value="train")

		results = list(text_streams_generator(stream, targets, len_bounds))
		# It should take as much as capacity allows (usable text len // (max_len * 1.5))
		assert len(results) > 0

	def test_text_streams_generator_capacity_handling(self, mock_constants):
		stream = [{"id": "1", "text": "short", "metadata": {}}]
		targets = {"train": 1, "val": 1, "test": 1}

		gen = text_streams_generator(stream, targets, (4000, 10000))
		assert len(list(gen)) == 0

	def test_text_streams_generator_full_and_zero_capacity(self, mocker, mock_constants):
		# Book 1: Split is full
		# Book 2: Capacity is 0 (usable text too short)
		stream = [
			{"id": "full", "text": "content " * 1000, "metadata": {}},
			{"id": "small", "text": "short", "metadata": {}},
		]
		
		# Mock targets so 'train' is already done
		targets = {"train": 0, "val": 10, "test": 10}
		mocker.patch("fetching.text_splits.get_split", side_effect=["train", "val"])
		
		gen = text_streams_generator(stream, targets, (500, 1000))
		results = list(gen)
		
		# Should be empty because first was skipped (full) and second was skipped (capacity)
		assert len(results) == 0


class TestGetTextStream:
	def test_get_text_stream_integration(self, mocker):
		mocker.patch("fetching.text_splits.load_dataset")
		mocker.patch("fetching.text_splits.randomize_stream")
		mock_gen = mocker.patch("fetching.text_splits.text_streams_generator")
		mocker.patch.dict(os.environ, {"HF_TOKEN": "mock_token"})

		result = get_text_stream(targets={"train": 10, "val": 1, "test": 1})

		assert result == mock_gen.return_value
		mock_gen.assert_called_once()

	def test_get_text_stream_none_targets(self, mocker):
		"""Line 386: Test default targets assignment."""
		mocker.patch("fetching.text_splits.load_dataset")
		mocker.patch("fetching.text_splits.randomize_stream")
		mock_gen = mocker.patch("fetching.text_splits.text_streams_generator")
		mocker.patch.dict(os.environ, {"HF_TOKEN": "mock"})

		get_text_stream(targets=None)

		# Verify the default dict was passed to the generator
		passed_targets = mock_gen.call_args[0][1]
		assert passed_targets == {"train": 1_000_000, "val": 10000, "test": 10000}
