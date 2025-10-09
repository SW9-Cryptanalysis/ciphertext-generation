from .homophones import extract_homophones, get_homophones
from .frequency import frequencies
import random
from collections import Counter
import re
from utils.constants import MIN_DIFFICULTY, MAX_DIFFICULTY


class Cipher:
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

	PLAINTEXT_PATTERN = re.compile(r"^[a-z]+$")

	def __init__(self, plaintext: str, difficulty: int | None = None) -> None:
		"""Initialize the Cipher object with the given plaintext.

		Args:
			plaintext (str): The lowercase plaintext to be encrypted with no
				punctuation or spaces.
			difficulty (int | None): The difficulty level of the cipher (4-20). If None,
				a random difficulty will be generated.

		"""
		self.plaintext = self._validate_plaintext(plaintext)
		if not difficulty and difficulty != 0:
			self.difficulty = self.generate_difficulty()
		else:
			self.difficulty = self._validate_difficulty(difficulty)
		self.key = self.generate_key()
		self.ciphertext = self.encipher()
		self.recurrence_encoding = self._generate_recurrence_encoding()

	def _validate_plaintext(self, plaintext: str) -> str:
		"""Validate the plaintext to ensure it contains only lowercase letters.

		Args:
				plaintext (str): The plaintext to validate.

		Returns:
				str: The validated plaintext.

		Raises:
				ValueError: If the plaintext contains invalid characters.

		"""
		if not isinstance(plaintext, str):
			raise ValueError("Plaintext must be a string.")
		if not plaintext:
			raise ValueError("Plaintext must be a non-empty string.")
		if not self.PLAINTEXT_PATTERN.match(plaintext):
			raise ValueError(
				"Plaintext must contain only lowercase letters with no punctuation"
				" or spaces.",
			)
		return plaintext

	def _validate_difficulty(self, difficulty: int) -> int:
		"""Validate the difficulty level to ensure it is between 4 and 20.

		Args:
				difficulty (int): The difficulty level to validate.

		Returns:
				int: The validated difficulty level.

		Raises:
				ValueError: If the difficulty level is not between 4 and 10.

		"""
		if not isinstance(difficulty, int):
			raise ValueError("Difficulty must be an integer.")
		if difficulty < MIN_DIFFICULTY or difficulty > MAX_DIFFICULTY:
			raise ValueError(
				f"Difficulty must be between {MIN_DIFFICULTY} and {MAX_DIFFICULTY}.",
			)
		return difficulty

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
		return " ".join(ciphertext_numbers)

	def generate_difficulty(self) -> int:
		"""Generate a difficulty level for the cipher.

		Difficulty is based on the average occurrences of each homophone,
		and ranges from 4-10, with 4 being the most difficult.

		Returns:
						int: Difficulty level (4-10)

		"""
		return random.randint(MIN_DIFFICULTY, MAX_DIFFICULTY)

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
		return f'''Cipher(Plaintext: "{self.plaintext}"
			Difficulty: {self.difficulty}
			Key: {self.key}
			Ciphertext: "{self.ciphertext}"
			Recurrence Encoding: "{self.recurrence_encoding}")
			'''
