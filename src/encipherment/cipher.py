from .homophones import extract_homophones, get_homophones
from .frequency import frequencies
import random
from collections import Counter
from utils.constants import MIN_DIFFICULTY, MAX_DIFFICULTY
from abc import ABC, abstractmethod
from parameter_validator import parameter_validator, all_of

from utils.validators import (
	in_range,
	strongly_typed_optional,
	lower_case_no_spaces_alpha_string,
)


class SubstitutionCipher(ABC):
	"""A base class for ciphers.

	Attributes:
		plaintext (str): The lowercase plaintext to be encrypted with no punctuation
			or spaces.
		difficulty (int): The difficulty level of the cipher (4-20).
		key (dict): A dictionary mapping each letter to a list of its homophones.
		ciphertext (str): The resulting ciphertext as a string of numbers separated
			by spaces.
		recurrence_encoding (str): A string representing the recurrence encoding of
			the ciphertext.

	Methods:
		generate_key(): Generate a homophonic substitution cipher key based on a
			difficulty level.
		encipher(): Encipher the plaintext using the generated key.
		generate_difficulty(): Generate a difficulty level for the cipher.
		__json__(): Return a JSON-serializable representation of the SubstitutionCipher
			object.
		__str__(): Return a string representation of the SubstitutionCipher object.
		_validate_plaintext(): Validate the plaintext to ensure it contains only
			lowercase letters with no punctuation or spaces.
		_validate_difficulty(): Validate the difficulty level to ensure it is
			between 4 and 20.

	"""

	@abstractmethod
	def __init__(
		self,
		plaintext: str,
		*,
		difficulty: int | None = None,
		cipher_type: str = "homophonic",
	) -> None:  # pragma: no cover
		"""Initialize the Cipher object with the given plaintext."""
		self.plaintext = plaintext
		self.difficulty = difficulty
		self.key = {}
		self.ciphertext = ""
		self.recurrence_encoding = ""
		raise NotImplementedError("This is an abstract base class.")

	def _generate_recurrence_encoding(self) -> str:
		"""Generate recurrence encoding for the ciphertext based on the homophones used.

		Each homophone is represented by a unique symbol, and the encoder gives the next
		number each time a new symbol is encountered.

		Example:
			`83 45 12 123 45 -> 1 2 3 4 2`

		"""
		ciphertext_numbers = self.ciphertext.split()
		recurrence_encoding = []
		encountered_symbols = {}

		for number in ciphertext_numbers:
			if number not in encountered_symbols:
				encountered_symbols[number] = len(encountered_symbols) + 1
			recurrence_encoding.append(str(encountered_symbols[number]))

		return " ".join(recurrence_encoding)

	def __json__(self) -> dict:
		"""Return a JSON-serializable representation of the Cipher object.

		Returns:
			dict: A dictionary containing the Cipher object's attributes.

		"""
		return {
			"plaintext": self.plaintext,
			"difficulty": self.difficulty,
			"key": self.key,
			"ciphertext": self.ciphertext,
			"recurrence_encoding": self.recurrence_encoding,
		}

	def __str__(self) -> str:
		"""Return a string representation of the Cipher object.

		Returns:
			str: A string representation of the Cipher object.

		"""
		class_name = self.__class__.__name__
		return f'''{class_name}(Plaintext: "{self.plaintext}"
			Difficulty: {self.difficulty}
			Key: {self.key}
			Ciphertext: "{self.ciphertext}"
			Recurrence Encoding: "{self.recurrence_encoding}")
			'''

	@abstractmethod
	def generate_key(self) -> dict:  # pragma: no cover
		"""Generate a substitution cipher key."""
		pass

	@abstractmethod
	def encipher(self) -> str:  # pragma: no cover
		"""Encipher the plaintext using the generated key."""
		pass


class HomophonicCipher(SubstitutionCipher):
	"""A class representing a homophonic substitution cipher.

	Attributes:
		plaintext (str): The lowercase plaintext to be encrypted with no punctuation
			or spaces.
		difficulty (int): The difficulty level of the cipher (4-20).
		key (dict): A dictionary mapping each letter to a list of its homophones.
		ciphertext (str): The resulting ciphertext as a string of numbers separated
			by spaces.
		recurrence_encoding (str): A string representing the recurrence encoding of
			the ciphertext.

	Methods:
		generate_key(): Generate a homophonic substitution cipher key based on a
			difficulty level.
		encipher(): Encipher the plaintext using the generated key.
		generate_difficulty(): Generate a difficulty level for the cipher.
		__json__(): Return a JSON-serializable representation of the Cipher object.
		__str__(): Return a string representation of the Cipher object.
		_validate_plaintext(): Validate the plaintext to ensure it contains only
			lowercase letters with no punctuation or spaces.
		_validate_difficulty(): Validate the difficulty level to ensure it is
			between 4 and 20.

	"""

	@parameter_validator(
		plaintext=lower_case_no_spaces_alpha_string,
		difficulty=all_of(
			in_range(MIN_DIFFICULTY, MAX_DIFFICULTY), strongly_typed_optional,
		),
	)
	def __init__(self, plaintext: str, *, difficulty: int | None = None) -> None:
		"""Initialize the Cipher object with the given plaintext.

		Args:
			plaintext (str): The lowercase plaintext to be encrypted with no
				punctuation or spaces.
			difficulty (int | None): The difficulty level of the cipher (4-20). If None,
				a random difficulty will be generated.
			cipher_type (str): The type of cipher to generate
				("homophonic" or "monoalphabetic").

		"""
		self.plaintext = plaintext
		if not difficulty:
			self.difficulty = self.generate_difficulty()
		else:
			self.difficulty = difficulty
		self.key: dict[str, list] = {}
		self.ciphertext: str = ""
		self.recurrence_encoding: str = ""

	def generate_key(self) -> dict:
		"""Generate a homophonic substitution cipher key based on a difficulty level.

		Key is a dictionary mapping each letter to a list of its homophones.
		Each letter is assigned a number of homophones proportional to its frequency in
		English text, with some random noise added to create variability.

		Each homophone is represented by a unique, randomly sampled number from 1
		to the total number of cipher symbols.

		Returns:
			dict: A dictionary mapping each letter to a list of its homophones.

		"""
		cipher_symbols: int = round(len(self.plaintext) / self.difficulty)

		letter_frequencies = frequencies(self.plaintext)

		homophones_dict: dict[str, int] = extract_homophones(
			cipher_symbols,
			letter_frequencies,
		)

		homophone_numbers: list[int] = list(range(1, sum(homophones_dict.values()) + 1))
		random.shuffle(homophone_numbers)
		key: dict[str, list[int]] = {}
		for letter, count in homophones_dict.items():
			key[letter] = homophone_numbers[:count]
			homophone_numbers = homophone_numbers[count:]
		self.key = key
		return key

	def encipher(self) -> str:
		"""Encipher the plaintext using generated homophonic substitution cipher key.

		Returns:
			str: The resulting ciphertext as a string of numbers separated by spaces.

		"""
		counts = Counter(ch for ch in self.plaintext if ch in self.key)

		homophones: dict[str, list[int]] = {}
		ptr: dict[str, int] = {}
		for letter, count in counts.items():
			homophones[letter] = get_homophones(self.key[letter], count)
			ptr[letter] = 0

		ciphertext_numbers: list[str] = []
		for char in self.plaintext:
			ciphertext_numbers.append(str(homophones[char][ptr[char]]))
			ptr[char] += 1
		self.ciphertext = " ".join(ciphertext_numbers)
		self.recurrence_encoding = self._generate_recurrence_encoding()
		return self.ciphertext

	def generate_difficulty(self) -> int:
		"""Generate a difficulty level for the cipher.

		Difficulty is based on the average occurrences of each homophone,
		and ranges from 4-10, with 4 being the most difficult.

		Returns:
						int: Difficulty level (4-10)

		"""
		return random.randint(MIN_DIFFICULTY, MAX_DIFFICULTY)


class MonoalphabeticCipher(SubstitutionCipher):
	"""A monoalphabetic substitution cipher.

	Attributes:
		plaintext (str): The lowercase plaintext to be encrypted with no punctuation
			or spaces.
		difficulty (int): The difficulty level of the cipher (4-20).
		key (dict): A dictionary mapping each letter to a list of its homophones.
		ciphertext (str): The resulting ciphertext as a string of numbers separated
			by spaces.
		recurrence_encoding (str): A string representing the recurrence encoding of
			the ciphertext.

	Methods:
		generate_key(): Generate a homophonic substitution cipher key based on a
			difficulty level.
		encipher(): Encipher the plaintext using the generated key.
		__json__(): Return a JSON-serializable representation of the Cipher object.
		__str__(): Return a string representation of the Cipher object.
		_validate_plaintext(): Validate the plaintext to ensure it contains only
			lowercase letters with no punctuation or spaces.
		_validate_difficulty(): Validate the difficulty level to ensure it is
			between 4 and 20.

	"""

	@parameter_validator(plaintext=lower_case_no_spaces_alpha_string)
	def __init__(self, plaintext: str) -> None:
		"""Initialize the MonoalphabeticCipher with the given plaintext.

		Args:
			plaintext (str): The lowercase plaintext to be encrypted with no
				punctuation or spaces.

		"""
		self.plaintext = plaintext
		self.key = self.generate_key()
		self.difficulty = 1
		self.ciphertext = self.encipher()
		self.recurrence_encoding = self._generate_recurrence_encoding()

	def generate_key(self) -> dict[str, list[int]]:
		"""Generate a random monoalphabetic substitution key.

		Each letter maps to exactly one unique random number.

		Returns:
			dict: A dictionary mapping each letter to a list containing one random
			number.

		"""
		# Create a list of numbers 1-26 and shuffle them randomly
		cipher_numbers = list(range(1, 27))
		random.shuffle(cipher_numbers)

		key = {}
		for i, letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
			key[letter] = [cipher_numbers[i]]

		return key

	def encipher(self) -> str:
		"""Encipher the plaintext using the monoalphabetic substitution key.

		Returns:
			str: The resulting ciphertext as a string of numbers separated by spaces.

		"""
		ciphertext_numbers = []
		for char in self.plaintext:
			if char in self.key:
				ciphertext_numbers.append(
					str(self.key[char][0]),
				)

		return " ".join(ciphertext_numbers)
