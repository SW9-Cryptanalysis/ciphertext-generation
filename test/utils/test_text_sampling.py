import pytest
from dataclasses import dataclass
from utils.text_sampling import (
    find_boundaries,
    find_spaceless_target_index,
    extract_specific_chunk,
    get_usable_text,
    randomize_stream,
    get_source_genres,
    Book,
)


class TestFindBoundaries:
    def test_find_boundaries_standard(self):
        """Test snapping to spaces on both sides."""
        text = "abc def ghi jkl"

        start, end = find_boundaries(text, 4, 7)
        assert start == 4
        assert end == 11
        assert text[start:end] == "def ghi"

    def test_find_boundaries_no_left_space(self):
        """Test behavior when there is no space before the start index."""
        text = "abcdefghi jkl"
        start, end = find_boundaries(text, 0, 5)
        assert start == 0
        assert end == 9
        assert text[start:end] == "abcdefghi"

    def test_find_boundaries_no_right_space(self):
        """Test behavior when the string ends before a right space is found."""
        text = "abc defghijkl"
        start, end = find_boundaries(text, 4, 9)
        assert start == 4
        assert end == 13
        assert text[start:end] == "defghijkl"


class TestFindSpacelessTargetIndex:
    def test_find_spaceless_target_index_standard(self):
        """Test normal mapping of character counts ignoring spaces."""
        text = "a b c d e"
        assert find_spaceless_target_index(text, 3) == 4

    def test_find_spaceless_target_index_exceeds_length(self):
        """Test safe fallback to string length if target characters aren't reached."""
        text = "a b c d e"
        assert find_spaceless_target_index(text, 10) == len(text)


class TestGetUsableText:
    def test_get_usable_text_trimming(self):
        """Test that long books have their edges trimmed."""
        raw = "A" * 100_000
        usable = get_usable_text(raw, (4000, 10000))

        assert len(usable) == 97_000

    def test_get_usable_text_short_book(self):
        """Test that short books bypass trimming entirely."""
        raw = "Short book content"
        usable = get_usable_text(raw, (4000, 10000))
        assert usable == raw


class TestRandomizeStream:
    def test_randomize_stream(self, mocker):
        """Test that the HuggingFace dataset shuffle method is called."""
        mock_stream = mocker.Mock()
        randomize_stream(mock_stream)
        mock_stream.shuffle.assert_called_once_with(seed=42, buffer_size=100)


class TestExtractSpecificChunk:
    def test_extract_specific_chunk_empty_window(self):
        """Verify extraction fails gracefully if the partition window is empty."""
        result = extract_specific_chunk(
            text="short", target_len=10, start_idx=10, partition_size=50
        )
        assert result is None

    def test_extract_specific_chunk_too_short_after_cleaning(self, mocker):
        """Verify extraction fails if the formatted text lacks sufficient alphabetic characters."""
        mocker.patch("utils.text_sampling.format_text", return_value="a b c")
        mocker.patch("utils.text_sampling.clean_spaces", return_value="abc")

        result = extract_specific_chunk(
            text="dummy text", target_len=10, start_idx=0, partition_size=50
        )
        assert result is None

    def test_extract_specific_chunk_success(self, mocker):
        """Verify that a successful extraction returns both bounded and unbounded text."""

        mocker.patch("utils.text_sampling.format_text", return_value="hello world test")
        mocker.patch(
            "utils.text_sampling.clean_spaces",
            side_effect=lambda x: x.replace(" ", ""),
        )
        mocker.patch("utils.text_sampling.find_spaceless_target_index", return_value=10)

        mocker.patch("utils.text_sampling.find_boundaries", return_value=(0, 11))

        result = extract_specific_chunk(
            text="dummy text", target_len=10, start_idx=0, partition_size=50
        )

        assert result is not None
        unbounded, bounded = result
        assert unbounded == "helloworld"
        assert bounded == "hello_world"

    def test_extract_specific_chunk_empty_boundaries(self, mocker):
        """Verify extraction fails if the final stripped chunks evaluate to empty."""
        mocker.patch("utils.text_sampling.format_text", return_value="hello world")

        mocker.patch("utils.text_sampling.clean_spaces", side_effect=["helloworld", ""])

        mocker.patch("utils.text_sampling.find_spaceless_target_index", return_value=5)
        mocker.patch("utils.text_sampling.find_boundaries", return_value=(0, 5))

        result = extract_specific_chunk(
            text="dummy text", target_len=5, start_idx=0, partition_size=50
        )

        assert result is None


class TestGetSourceGenres:
    @dataclass
    class GetSourceTestCase:
        book: Book
        genre_map: dict[str, list[str]]
        expected_genres: list[str]
        desc: str

    TEST_CASES_GET_SOURCES = [
        GetSourceTestCase(
            book={
                "id": "pg:123",
                "source_type": "project_gutenberg",
                "fallback_genres": ["Fiction"],
                "text": "...",
                "source_name": "Gutenberg",
            },
            genre_map={"123": ["Sci-Fi", "Adventure"]},
            expected_genres=["Sci-Fi", "Adventure"],
            desc="Gutenberg source: ID found in map",
        ),
        GetSourceTestCase(
            book={
                "id": "pg:456",
                "source_type": "project_gutenberg",
                "fallback_genres": ["Classic"],
                "text": "...",
                "source_name": "Gutenberg",
            },
            genre_map={"123": ["Sci-Fi"]},
            expected_genres=["Classic"],
            desc="Gutenberg source: ID NOT in map (uses fallback)",
        ),
        GetSourceTestCase(
            book={
                "id": "other:789",
                "source_type": "local_library",
                "fallback_genres": ["History"],
                "text": "...",
                "source_name": "Local",
            },
            genre_map={"789": ["Biography"]},
            expected_genres=["History"],
            desc="Non-Gutenberg source: ignores map, uses fallback",
        ),
        GetSourceTestCase(
            book={
                "id": "pg:999",
                "source_type": "project_gutenberg",
                "fallback_genres": [],
                "text": "...",
                "source_name": "Gutenberg",
            },
            genre_map={},
            expected_genres=[],
            desc="Gutenberg source: empty map and empty fallback",
        ),
        GetSourceTestCase(
            book={
                "id": "123",
                "source_type": "project_gutenberg",
                "fallback_genres": ["Drama"],
                "text": "...",
                "source_name": "Gutenberg",
            },
            genre_map={"123": ["Drama (Mapped)"]},
            expected_genres=["Drama (Mapped)"],
            desc="Gutenberg source: ID exists without prefix",
        ),
    ]

    @pytest.mark.parametrize("case", TEST_CASES_GET_SOURCES, ids=lambda c: c.desc)
    def test_get_source_genres_returns_fallback(self, case: GetSourceTestCase):
        assert get_source_genres(case.book, case.genre_map) == case.expected_genres
