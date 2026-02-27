from utils.constants import DEFAULT_TAXONOMY
from pathlib import Path


class TaxonomyMapper:
	"""Handles the transformation of raw bookshelves into a standardized genre taxonomy."""

	def __init__(
		self,
		taxonomy: dict[str, list[str]] | None = None,
		unmapped_log_file: Path = Path("data/unmapped_bookshelves.txt"),
	) -> None:
		"""Initialize the TaxonomyMapper with a custom taxonomy or the default one.

		Args:
			taxonomy (dict[str, list[str]] | None, optional): The custom taxonomy to use. Defaults to None.
			unmapped_log_file (str, optional): The file to log unmapped bookshelves to. Defaults to "data/unmapped_bookshelves.txt".
		"""
		if not taxonomy:
			taxonomy = DEFAULT_TAXONOMY
		self.keyword_to_genre = {}
		for genre, keywords in taxonomy.items():
			for keyword in keywords:
				self.keyword_to_genre[keyword.lower()] = genre
		self.sorted_keywords = sorted(self.keyword_to_genre, key=len, reverse=True)
		self.unmapped_log_file = unmapped_log_file
		self._unmapped_genres = set()

	def extract_mapped_genres(self, raw_shelves: list[str]) -> list[str]:
		"""Map raw Gutendex bookshelves to a predefined strict taxonomy.

		Args:
			raw_shelves (list[str]): The list of raw bookshelves to map.

		Returns:
			list[str]: The list of mapped genres.
		"""
		matched_genres = self._find_genres(raw_shelves)

		if not matched_genres:
			for shelf in raw_shelves:
				self._unmapped_genres.add(shelf)
			return ["Other / Uncategorized"]

		return list(matched_genres)

	def _find_genres(self, raw_shelves: list[str]) -> list[str]:
		"""Find genres for a list of bookshelves."""
		matched_genres = set()

		for shelf in raw_shelves:
			working_shelf = shelf.lower()
			for keyword in self.sorted_keywords:
				if keyword in working_shelf:
					matched_genres.add(self.keyword_to_genre[keyword])
					working_shelf = working_shelf.replace(keyword, "")

		return list(matched_genres)

	def dump_unmapped_to_file(self) -> None:
		"""Dump unmapped bookshelves to a file."""
		with open(self.unmapped_log_file, "w", encoding="utf-8") as f:
			for shelf in self._unmapped_genres:
				f.write(f"{shelf}\n")
