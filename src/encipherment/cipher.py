from .homophones import extract_homophones, get_homophones
from .frequency import frequencies
import random
from collections import Counter
import re


class Cipher:
    def __init__(self, plaintext: str, difficulty: int | None = None) -> None:
        """Initialize the Cipher object with the given plaintext.

        Args:
                plaintext (str): The lowercase plaintext to be encrypted with no punctuation or spaces.
        """

        pattern = re.compile(r"^[a-z]+$")
        if not pattern.match(plaintext):
            raise ValueError(
                "Plaintext must contain only lowercase letters with no punctuation or spaces."
            )
        self.plaintext = plaintext
        if not difficulty:
            self.difficulty = self.generate_difficulty()
        else: 
            self.difficulty = difficulty
        self.key = self.generate_key()
        self.ciphertext = self.encipher()

    def generate_key(self) -> dict:
        """Generate a homophonic substitution cipher key based on the given difficulty level.

        Key is a dictionary mapping each letter to a list of its homophones.
        Each letter is assigned a number of homophones proportional to its frequency in English text,
        with some random noise added to create variability.

        Each homophone is represented by a unique, randomly sampled number from 1 to the total number
        of cipher symbols.

        Returns:
                dict: A dictionary mapping each letter to a list of its homophones.
        """
        cipher_symbols: int = round(len(self.plaintext) / self.difficulty)
        
        letter_frequencies = frequencies(self.plaintext)

        homophones_dict: dict[str, int] = extract_homophones(cipher_symbols, letter_frequencies)

        homophone_numbers: list[int] = list(range(1, sum(homophones_dict.values()) + 1))
        random.shuffle(homophone_numbers)
        key: dict[str, list[int]] = {}
        for letter, count in homophones_dict.items():
            key[letter] = homophone_numbers[:count]
            homophone_numbers = homophone_numbers[count:]
        return key

    def encipher(self) -> str:
        """Encipher the plaintext using the generated homophonic substitution cipher key.

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
        """Generate a difficulty level for the cipher based on the average occurences of each homophone.
                Difficulty levels range from 4-10, with 4 being the most difficult.

        Returns:
                int: Difficulty level (4-10)
        """

        return random.randint(4, 10)

    def __json__(self) -> dict:
        """Return a JSON-serializable representation of the Cipher object.

        Returns:
                dict: A dictionary containing the plaintext, difficulty, key, and ciphertext.
        """
        return {
            "plaintext": self.plaintext,
            "difficulty": self.difficulty,
            "key": self.key,
            "ciphertext": self.ciphertext,
        }

    def __str__(self) -> str:
        """Return a string representation of the Cipher object.

        Returns:
                str: A string containing the plaintext, difficulty, key, and ciphertext.
        """
        return f'Cipher(Plaintext: "{self.plaintext}"\nDifficulty: {self.difficulty}\nKey: {self.key}\nCiphertext: "{self.ciphertext}")'
