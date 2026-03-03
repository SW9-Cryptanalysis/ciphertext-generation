from encipherment.cipher import (
	HomophonicCipher,
	SubstitutionCipher,
	MonoalphabeticCipher,
)
from parameter_validator import parameter_validator, strongly_typed
from utils.text_splits import TextStream


def _invert_mappings(mappings: dict[str, list[str]]) -> dict[str, str]:
	"""Invert a plaintext-to-symbols map (P->[C]) into a symbol-to-plaintext map (C->P).

	Args:
		mappings (dict): The plaintext-to-symbols mapping.

	Returns:
		dict: The symbol-to-plaintext mapping.

	Raises:
		ValueError: If a mapping is ambiguous.

	"""
	inv_map = {}
	for char, symbols in mappings.items():
		for symbol in symbols:
			if symbol in inv_map:
				# This indicates a corrupt or invalid mapping
				raise ValueError(
					f"Ambiguous mapping: Symbol '{symbol}' maps to multiple characters",
				)
			inv_map[symbol] = char
	return inv_map


class CipherConverter:
	"""Holds the state of a complete cipher (plaintext, ciphertext, mappings).

	Provides factory methods to construct this state from partial data.

	Attributes:
		plaintext (str): The plaintext to be encrypted with no punctuation
			or spaces.
		ciphertext (str): The corresponding ciphertext with no punctuation or spaces.
		mappings (dict): The plaintext-to-symbols mapping.

	Methods:
		`from_plaintext_and_ciphertext()`: Create a converter by deducing mappings
			from a plaintext and ciphertext.
		`from_ciphertext_and_mappings()`: Create a converter by deducing plaintext
			from a ciphertext and mappings.
		`convert_to_cipher()`: Convert the stored data into a HomophonicCipher object.

	"""

	def __init__(
		self,
		plaintext: str,
		ciphertext: str,
		mappings: dict[str, list[str]] | dict[str, str],
	) -> None:
		"""Initialize the converter with a complete set of data.

		Note: @classmethod factories (e.g., from_plaintext_and_ciphertext)
		can be used to construct this object from partial data.

		Args:
			plaintext (str): The plaintext to convert.
			ciphertext (str): The ciphertext to convert.
			mappings (dict): The mappings to convert.

		Raises:
			ValueError: If the input is invalid.

		"""
		self.plaintext = plaintext
		self.ciphertext = ciphertext
		self.mappings = mappings
		self._cipher: SubstitutionCipher | None = None

	@classmethod
	@parameter_validator(plaintext=strongly_typed, ciphertext=strongly_typed)
	def from_plaintext_and_ciphertext(
		cls,
		plaintext: str,
		ciphertext: str,
	) -> "CipherConverter":
		"""Create a converter by deducing mappings from a plaintext and ciphertext.

		Args:
			plaintext (str): The plaintext to encipher.
			ciphertext (str): The corresponding ciphertext.

		Raises:
			ValueError: If the plaintext and ciphertext lengths do not match.

		Returns:
			CipherConverter: The cipher converter.

		"""
		mappings: dict[str, list[str]] = {}

		if len(plaintext) != len(ciphertext.split()):
			raise ValueError(
				f"Plaintext length ({len(plaintext)}) and "
				f"number of ciphertext symbols ({len(ciphertext.split())})"
				" do not match.",
			)

		for i, char in enumerate(plaintext):
			symbol = ciphertext.split()[i]
			if char not in mappings:
				mappings[char] = [symbol]
				continue
			if symbol not in mappings[char]:
				mappings[char].append(symbol)

		return cls(plaintext, ciphertext, mappings)

	@classmethod
	def from_ciphertext_and_mappings(
		cls,
		ciphertext: str,
		mappings: dict[str, list[str]],
	) -> "CipherConverter":
		"""Create a converter by deducing plaintext from a ciphertext and mappings.

		Args:
			ciphertext (str): The ciphertext to encipher.
			mappings (dict): The plaintext-to-symbols mapping.

		Raises:
			ValueError: If the mappings cannot be deduced.

		Returns:
			CipherConverter: The cipher converter.

		"""
		try:
			inv_map = _invert_mappings(mappings)
		except ValueError as e:
			raise ValueError(f"Invalid mappings provided: {e}") from e

		plaintext_chars = []
		for symbol in ciphertext.split():
			if symbol in inv_map:
				plaintext_chars.append(inv_map[symbol])
			else:
				raise ValueError(
					f"Symbol '{symbol}' not found in mappings.",
					"Ciphertext:",
					ciphertext,
					"Mappings:",
					mappings,
				)

		plaintext = "".join(plaintext_chars)
		return cls(plaintext, ciphertext, mappings)

	def convert_to_cipher(self) -> SubstitutionCipher:
		"""Convert the stored data into a HomophonicCipher object.

		Note: This patches the attributes of a new HomophonicCipher
		instance, which may be brittle if the base class changes.
		"""
		if self._cipher:
			return self._cipher

		text_obj: TextStream = {
			"text": self.plaintext,
			"text_with_boundaries": self.plaintext,
			"source_id": "Unknown",
			"source_name": "Unknown",
			"length": len(self.plaintext),
			"genres": [],
		}

		if self._is_homophonic():
			self._cipher = HomophonicCipher(text_obj, difficulty=4)
		else:
			self._cipher = MonoalphabeticCipher(text_obj)

		self._cipher.ciphertext = self.ciphertext
		self._cipher.key = self.mappings  # type: ignore

		return self._cipher

	def _is_homophonic(self) -> bool:
		"""Check if the cipher is homophonic.

		Returns:
			bool: True if the cipher is homophonic, False if it is monoalphabetic.

		"""
		return any(len(mapping) > 1 for mapping in self.mappings.values())
