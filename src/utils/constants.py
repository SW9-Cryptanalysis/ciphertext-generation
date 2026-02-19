"""Constants for the cipher generation."""

MIN_DIFFICULTY = 4
MAX_DIFFICULTY = 30
MIN_PLAINTEXT_LENGTH = 4000
MAX_PLAINTEXT_LENGTH = 6000
NUM_CIPHERS = 100000
ALPHABET = "abcdefghijklmnopqrstuvwxyz"

BATCH_SIZE = 10000

DIFFICULTIES = [5, 10, 15, 20, 25, 30]
LENGTHS = [400, 800, 4000, 6000, 10000]

BOOK_IDS_VALIDATION = [
	"7241",  # Fables of La Fontaine
	"6593",  # History of Tom Jones, a Foundling
	"1342",  # Pride and Prejudice
	"1661",  # The Adventures of Sherlock Holmes
	"15399",  # The Interesting Narrative of the Life of Olaudah Equiano...
	"1998",  # Thus Spake Zarathustra
	"3207",  # Leviathan
	"120",  # Treasure Island
	"2160",  # The Expedition of Humphry Clinker
	"2542",  # A Doll's House
	"84",  # Frankenstein
	"7370",  # Second Treatise of Government
	"12",  # Through the Looking-Glass
	"2852",  # The Hound of the Baskervilles
	"76",  # The Adventures of Huckleberry Finn
	"2148",  # The Works of Edgar Allan Poe - Volume 2
	"1952",  # The Yellow Wallpaper
	"1259",  # Twenty Years After
	"394",  # Cranford
	"76939",  # The laws of contrast of color
	"829",  # Gulliver's Travels into Several Remote Nations of the World
	"60976",  # Rip Van Winkle
	"26184",  # Simple Sabotage Field Manual
	"2814",  # Dubliners
	"36034",  # White Nights and Other Stories
]

TOTAL_BOOKS = 55_454
DATASET_NAME = "common-pile/project_gutenberg_filtered"
