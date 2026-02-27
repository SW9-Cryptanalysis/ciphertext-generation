from utils.constants import DEFAULT_TAXONOMY

class TaxonomyMapper:
	"""Handles the transformation of raw bookshelves into a standardized genre taxonomy."""

	def __init__(
		self,
		taxonomy: dict[str, list[str]] | None = None,
		unmapped_log_file: str = "data/unmapped_bookshelves.txt",
	) -> None:
		"""Initialize the TaxonomyMapper with a custom taxonomy or the default one.

		Args:
			taxonomy (dict[str, list[str]] | None, optional): The custom taxonomy to use. Defaults to None.
			unmapped_log_file (str, optional): The file to log unmapped bookshelves to. Defaults to "data/unmapped_bookshelves.txt".
		"""
		self.taxonomy = taxonomy or DEFAULT_TAXONOMY
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
			for target_genre, keywords in self.taxonomy.items():
				if self._match_shelf(shelf, keywords):
					matched_genres.add(target_genre)

		return list(matched_genres)

	def _match_shelf(self, shelf: str, keywords: list[str]) -> bool:
		"""Check if a shelf matches any of the provided keywords."""
		for keyword in keywords:
			if keyword.lower() in shelf.lower():
				return True
		return False

	def log_unmapped(self, raw_shelves: list[str]) -> None:
		"""Log unmapped bookshelves to a file.

		Args:
			raw_shelves (list[str]): The list of raw bookshelves to log.
		"""
		with open(self.unmapped_log_file, "a", encoding="utf-8") as f:
			f.write(f"{raw_shelves}\n")
