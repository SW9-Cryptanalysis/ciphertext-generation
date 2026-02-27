import pytest
import os
from genre_mapping.taxonomy_mapper import TaxonomyMapper
from pathlib import Path


class TestTaxonomyMapperInit:
	def test_taxonomy_mapper_init(self, mocker):
		"""Test the initialization of the TaxonomyMapper."""
		taxonomy_mapper = TaxonomyMapper()

		assert taxonomy_mapper.keyword_to_genre is not None, (
			"Keyword to genre mapping should be initialized"
		)
		assert taxonomy_mapper.sorted_keywords is not None, (
			"Sorted keywords should be initialized"
		)
		assert taxonomy_mapper.unmapped_log_file == Path(
			"data/unmapped_bookshelves.txt"
		), "Unmapped log file should be set"


class TestTaxonomyMapperExtractMappedGenres:
	@pytest.fixture
	def mapper(self):
		return TaxonomyMapper()

	def test_extract_mapped_genres(
		self, mapper, mock_gutendex_bookshelves, expected_taxonomy_mappings
	):
		"""Test the extraction of mapped genres from the mock_gutendex_bookshelves fixture."""
		book = mock_gutendex_bookshelves[0]

		print(book)
		print(expected_taxonomy_mappings[book["id"]])

		mapped_genres = mapper.extract_mapped_genres(book["bookshelves"])

		assert mapped_genres == expected_taxonomy_mappings[book["id"]], (
			"Genre mappings should match"
		)

	def test_extract_mapped_genres_handles_empty_list(self, mapper, mock_gutendex_bookshelves):
		"""Test the extraction of mapped genres from an empty list."""
		book = mock_gutendex_bookshelves[5]  # No bookshelves

		mapped_genres =  mapper.extract_mapped_genres(book["bookshelves"])

		assert mapped_genres == ["Other / Uncategorized"], "Genre mappings should match"

	def test_extract_mapped_genres_handles_complex_edge_cases(
		self, mapper, mock_gutendex_bookshelves
	):
		"""Test the extraction of mapped genres from complex edge cases."""
		book = mock_gutendex_bookshelves[6]  # Multiple genres

		mapped_genres = mapper.extract_mapped_genres(book["bookshelves"])

		assert set(mapped_genres) == set(["Journalism & Periodicals", "Humor"]), (
			"Genre mappings should match"
		)

	def test_extract_mapped_genres_handles_unknown_categories(
		self, mock_gutendex_bookshelves
	):
		"""Test the extraction of mapped genres from unknown categories."""
		taxonomy_mapper = TaxonomyMapper()
		book = mock_gutendex_bookshelves[3]  # Unknown category

		mapped_genres = taxonomy_mapper.extract_mapped_genres(book["bookshelves"])

		assert mapped_genres == ["Other / Uncategorized"], "Genre mappings should match"


class TestTaxonomyMapperDumpUnmapped:
	def test_dump_unmapped_to_file(
		self, mock_gutendex_bookshelves, tmp_path
	):
		"""Test the logging of unmapped bookshelves from multiple bookshelves."""
		tmp_file = tmp_path / "test_unmapped_bookshelves.txt"
		taxonomy_mapper = TaxonomyMapper(unmapped_log_file=tmp_file)

		for book in mock_gutendex_bookshelves:
			taxonomy_mapper.extract_mapped_genres(book["bookshelves"])

		taxonomy_mapper.dump_unmapped_to_file()

		assert os.path.exists(tmp_path / "test_unmapped_bookshelves.txt"), (
			"Unmapped bookshelves file should exist"
		)

		content = tmp_file.read_text(encoding="utf-8").splitlines()

		assert "Category: 19th Century Basket Weaving" in content
		assert "My Custom Book Club" in content
		assert len(content) == 2
