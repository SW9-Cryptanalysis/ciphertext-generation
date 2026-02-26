from parameter_validator import validator
from typing import Callable, Any, get_origin, get_args
from types import UnionType
from utils.constants import ALPHABET
from fetching.text_splits import TextStream


def in_range(min_value: int, max_value: int) -> Callable:
	"""Validate that an integer is within a specified range.

	Args:
		min_value (int): The minimum acceptable value (inclusive).
		max_value (int): The maximum acceptable value (inclusive).

	Returns:
		Callable: A validator function that checks if a value is within the range.

	"""

	@validator
	def validate(value: int, name: str) -> None:
		if not isinstance(value, int):
			return
		if not (min_value <= value <= max_value):
			raise ValueError(
				f"Parameter `{name}` must be between {min_value} and {max_value}.",
			)

	return validate


def strongly_typed_optional(value: Any, name: str, type_hint: type) -> None:
	"""Validate that a parameter is either None or of the expected type.

	Returns:
		Callable: A validator function that checks if a value is None or strongly typed.

	"""
	if value is None:
		return
	if not isinstance(value, type_hint):
		if get_origin(type_hint) is UnionType:
			type_names = ", ".join(
				t.__name__ for t in get_args(type_hint) if t is not type(None)
			)
			raise TypeError(
				f"Parameter `{name}` must be of type {type_names}, or None.",
			)
		raise TypeError(
			f"Parameter `{name}` must be of type {type_hint.__name__} or None.",
		)


def lower_case_no_spaces_alpha_string(value: Any, name: str, type_hint: type) -> None:
	"""Validate that a string is lowercase and contains no spaces.

	Args:
		value (Any): The value to validate.
		name (str): The name of the parameter.
		type_hint (Type): The expected type hint.

	Raises:
		TypeError: If the value is not a string.
		ValueError: If the string is not lowercase or contains spaces.

	"""
	if not isinstance(value, str):
		raise TypeError(f"Parameter `{name}` must be of type str.")
	if value.strip() == "":
		raise ValueError(f"Parameter `{name}` must be a non-blank string.")
	if not is_alpha_lowercase_no_spaces(value):
		raise ValueError(
			f"Parameter `{name}` must be a lowercase alphabetic string with no spaces.",
		)


def is_alpha_lowercase_no_spaces(value: str) -> bool:
	"""Check if a string is alphabetic, lowercase, and contains no spaces.

	Args:
		value (str): The string to check.

	Returns:
		bool: True if the string is alphanumeric, lowercase, and contains no spaces;
			False otherwise.

	"""
	if not value.islower():
		return False
	return all(c in ALPHABET for c in value)


@validator
def validate_text_obj(value: Any, name: str) -> None:
	"""Validate that a value is a valid TextStream object.

	Args:
		value (Any): The value to validate.
		name (str): The name of the parameter.

	Raises:
		TypeError: If the value is not a dict.
		KeyError: If the dict does not contain the required keys.
		ValueError: If the dict does not contain the required keys.

	"""
	if not isinstance(value, dict):
		raise TypeError(f"Parameter `{name}` must be of type dict.")

	required_keys = TextStream.__annotations__.keys()
	if set(value.keys()) != set(required_keys):
		raise KeyError(
			f"Parameter `{name}` must contain the following keys: {str(required_keys)}."
			f" Missing keys: {set(required_keys) - set(value.keys())}."
		)

	text_content = value["text"]
	if not text_content or not is_alpha_lowercase_no_spaces(text_content):
		raise ValueError(
			f"Parameter `{name}` must include a non-empty, lowercase alphabetic string "
			"with no spaces in the text field.",
		)
