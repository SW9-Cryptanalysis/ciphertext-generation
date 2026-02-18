import pytest
import os
from fetching import text_splits
from fetching.text_splits import (
    find_boundaries,
    clean_whitespace,
    extract_random_chunk,
    get_split,
    get_book_chunks,
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
        {"id": "1", "text": "Book One content " * 500, "metadata": {"title": "Book One"}},
        {"id": "2", "text": "Book Two content " * 500, "metadata": {"title": "Book Two"}},
        {"id": "3", "text": "Book Three content " * 500, "metadata": {"title": "Book Three"}},
    ]

# --- Helper Function Tests ---

class TestTextHelpers:

    def test_find_boundaries_standard(self, sample_text):
        # Target "sample text" (length ~11) starting around index 10
        # raw text: "This is a sample text..."
        # index 10 is 's' in sample.
        start, end = find_boundaries(sample_text, 10, 11)

        # Expectation:
        # Lookback from 10 finds space at 9 (" a "). start -> 10.
        # Target end -> 10 + 11 = 21 ("...text").
        # Lookahead from 21 finds space at 21 (" "). end -> 21.
        assert sample_text[start:end] == "sample text"

    def test_find_boundaries_start_of_string(self):
        text = "Start of string test."
        # No space before index 0
        start, end = find_boundaries(text, 0, 5)
        assert start == 0
        # Finds space after "Start"
        assert text[start:end] == "Start"

    def test_find_boundaries_end_of_string(self):
        text = "Test end of string"
        # Target "string" at the end
        start_raw = text.index("string")
        start, end = find_boundaries(text, start_raw, 6)

        # Should detect no space after and clamp to len(text)
        assert text[start:end] == "string"

    def test_clean_whitespace(self):
        raw = "Line\nBreak\tTab   Multiple  Spaces"
        expected = "Line Break Tab Multiple Spaces"
        assert clean_whitespace(raw) == expected

    def test_clean_whitespace_strip(self):
        raw = "  Leading and trailing  "
        expected = "Leading and trailing"
        assert clean_whitespace(raw) == expected

    def test_get_split(self):
        assert get_split(0) == "val"
        assert get_split(100) == "val"
        assert get_split(1) == "test"
        assert get_split(101) == "test"
        assert get_split(2) == "train"
        assert get_split(99) == "train"

    def test_randomize_stream(self, mocker):
        mock_stream = mocker.Mock()
        randomize_stream(mock_stream)
        mock_stream.shuffle.assert_called_once_with(seed=42, buffer_size=100)


# --- Core Logic Tests ---

class TestChunkExtraction:

    def test_extract_random_chunk(self, mocker, sample_text):
        # Mock random to return specific values
        # 1. randint for target_len: returns 10
        # 2. randint for raw_start: returns 5
        mocker.patch("random.randint", side_effect=[10, 5])

        # We need to verify that find_boundaries is called with expected calculated args
        # zone_size = 50, target_len = 10 -> max_start = 40.
        # raw_start = 5 + 5 (offset) = 10? No, raw_start = zone_start (0) + 5 = 5.

        spy_boundaries = mocker.spy(text_splits, "find_boundaries")

        chunk = extract_random_chunk(sample_text, 0, 50, (5, 20))

        # Check interactions
        spy_boundaries.assert_called_once()
        # Ensure it returns a string slice
        assert isinstance(chunk, str)

    def test_get_book_chunks(self, mocker):
        book_text = "word " * 100
        mocker.patch("fetching.text_splits.extract_random_chunk", return_value="chunk")
        mocker.patch("fetching.text_splits.clean_whitespace", return_value="chunk")

        # Test yielding
        chunks = list(get_book_chunks(book_text, actual_take=3, len_bounds=(10, 20)))

        assert len(chunks) == 3
        assert chunks == ["chunk", "chunk", "chunk"]


class TestStreamGenerator:

    @pytest.fixture
    def mock_constants(self, mocker):
        # Patch constants to make math easy
        # Total books = 100.
        # Val = 1% = 1 book.
        # Test = 1% = 1 book.
        # Train = 98% = 98 books.
        mocker.patch("fetching.text_splits.TOTAL_BOOKS", 100)
        # Mock validation list
        mocker.patch("fetching.text_splits.BOOK_IDS_VALIDATION", ["999"])

    def test_text_streams_generator_skips_blacklisted_ids(self, mocker):
        # 1. Setup: Stream with 1 good book and 1 bad book
        stream = [
            {"id": "good_id", "text": "valid content " * 100, "metadata": {"title": "Good Book"}},
            {"id": "bad_id", "text": "invalid content " * 100, "metadata": {"title": "Bad Book"}},
        ]

        # 2. Mock Constants: Force 'bad_id' into the blacklist
        mocker.patch("fetching.text_splits.BOOK_IDS_VALIDATION", ["bad_id"])

        # 3. Targets: We want 5 chunks from 'train'.
        # If the blacklist fails, we'd get chunks from 'bad_id' too.
        targets = {"train": 10, "val": 0, "test": 0}

        # Force all splits to 'train' to ensure logic hits the blacklist check
        mocker.patch("fetching.text_splits.get_split", return_value="train")

        # 4. Execution
        gen = text_streams_generator(stream, targets, (10, 20))
        results = list(gen)

        # 5. Assertions
        # verify we got results
        assert len(results) > 0

        # Verify EVERY result comes from 'good_id'
        for _, data in results:
            assert data["source_id"] == "good_id"
            assert data["source_id"] != "bad_id"

    def test_text_streams_generator_basic_flow(self, mock_constants, mock_book_stream):
        targets = {"train": 2, "val": 1, "test": 1}
        len_bounds = (10, 20)

        # ID 1 (idx 0) -> Val (0 % 100 == 0)
        # ID 2 (idx 1) -> Test (1 % 100 == 1)
        # ID 3 (idx 2) -> Train (2 % 100 == 2)

        gen = text_streams_generator(mock_book_stream, targets, len_bounds)
        results = list(gen)

        splits = [r[0] for r in results]

        # We expect at least one from each if capacity allows
        assert "val" in splits
        assert "test" in splits
        assert "train" in splits

        # Verify structure
        first_item = results[0][1]
        assert "text" in first_item
        assert "source_id" in first_item
        assert "source_name" in first_item

    def test_text_streams_generator_enforces_keys(self, mock_constants):
        stream = []
        # Missing 'val' and 'test'
        invalid_targets = {"train": 10}

        with pytest.raises(ValueError, match="must contain exactly keys"):
            list(text_streams_generator(stream, invalid_targets, (10, 20)))

        # Extra key 'other'
        invalid_targets_2 = {"train": 10, "val": 10, "test": 10, "other": 5}
        with pytest.raises(ValueError, match="must contain exactly keys"):
            list(text_streams_generator(stream, invalid_targets_2, (10, 20)))

    def test_text_streams_generator_skips_full_buckets(self, mocker, mock_constants):
        # Targets are full for Val, but we feed a Val book (idx 0)
        targets = {"val": 0, "train": 10, "test": 10}
        stream = [{"id": "1", "text": "content", "metadata": {}}]

        gen = text_streams_generator(stream, targets, (10, 20))
        results = list(gen)

        # Should be empty because idx 0 is Val, and Val target is 0
        assert len(results) == 0

    def test_text_streams_generator_global_break(self, mock_constants):
        # All targets satisfied
        targets = {"train": 0, "val": 0, "test": 0}
        stream = [{"id": "1", "text": "content", "metadata": {}}]

        gen = text_streams_generator(stream, targets, (10, 20))
        # Should break immediately
        results = list(gen)
        assert len(results) == 0

    def test_text_streams_generator_capacity_logic(self, mock_constants):
        stream = [{"id": "1", "text": "short", "metadata": {}}]
        targets = {"val": 5, "test": 5, "train": 5}

        gen = text_streams_generator(stream, targets, (100, 200))
        results = list(gen)

        assert len(results) == 0

    def test_text_streams_generator_debt_accounting(self, mocker):
        # 1. Setup: A massive book so 'capacity' doesn't limit us
        # Length 20,000 ensures we can easily take 10+ chunks of size ~20
        stream = [{"id": "1", "text": "long " * 4000, "metadata": {"title": "Test Book"}}]

        targets = {"train": 10, "val": 0, "test": 0}

        # 2. Patch Constants & Logic to force high debt
        # Formula: mean = target / (TOTAL_BOOKS * 0.98)
        # If TOTAL_BOOKS=1 and target=10, mean = 10 / 0.98 ≈ 10.2
        # This guarantees 'actual_take' will be at least 10.
        mocker.patch("fetching.text_splits.TOTAL_BOOKS", 1)
        mocker.patch("fetching.text_splits.BOOK_IDS_VALIDATION", [])

        # Force the first book (idx 0) to be 'train' so we hit the target logic immediately
        mocker.patch("fetching.text_splits.get_split", return_value="train")

        # 3. Execution
        gen = text_streams_generator(stream, targets, (10, 20))
        results = list(gen)

        # 4. Assertions
        # We expected a mean of ~10.2, so we should get at least 10 chunks from this single book.
        assert len(results) >= 10

        # Verify they are all from the same book and split
        for split, data in results:
            assert split == "train"
            assert data["source_id"] == "1"


class TestGetTextStream:

    def test_get_text_stream_defaults(self, mocker):
        # Mock external dependencies
        mocker.patch("fetching.text_splits.load_dataset")
        mock_randomize = mocker.patch("fetching.text_splits.randomize_stream")
        mock_generator = mocker.patch("fetching.text_splits.text_streams_generator")
        mocker.patch.dict(os.environ, {"HF_TOKEN": "mock_token"})

        # Call
        result = get_text_stream()

        # Assert pipeline
        mock_randomize.assert_called_once()
        mock_generator.assert_called_once()
        assert result == mock_generator.return_value

        # Check default targets were passed
        call_args = mock_generator.call_args
        targets_passed = call_args[0][1] # 2nd arg
        assert targets_passed["train"] == 1_000_000

    def test_get_text_stream_custom_targets(self, mocker):
        mocker.patch("fetching.text_splits.load_dataset")
        mocker.patch("fetching.text_splits.randomize_stream")
        mock_generator = mocker.patch("fetching.text_splits.text_streams_generator")
        mocker.patch.dict(os.environ, {"HF_TOKEN": "mock_token"})

        custom_targets = {"train": 50}
        get_text_stream(targets=custom_targets)

        call_args = mock_generator.call_args
        assert call_args[0][1] == custom_targets
