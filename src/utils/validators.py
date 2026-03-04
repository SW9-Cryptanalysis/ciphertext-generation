from parameter_validator import validator
from typing import Callable, Any, get_origin, get_args
from types import UnionType
from utils.constants import ALPHABET


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
		if isinstance(value, int) and not (min_value <= value <= max_value):
			raise ValueError(
				f"Parameter `{name}` must be between {min_value} and {max_value}.",
			)

	return validate


@validator
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


@validator
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


def _deep_validate(value: Any, type_hint: Any) -> None:
	"""Validate on list or dict elements recursively."""
	element_type = get_args(type_hint)[0]
	if not all(isinstance(item, element_type) for item in value):
		raise ValueError(
			f"All elements in '{value}' must be of type {element_type.__name__}.",
		)

def _validate_field(key: str, type_hint: type, dict: dict[str, Any], name: str) -> None:
	"""Validate a field in a dictionary.

	Args:
		key (str): The key to validate.
		type_hint (type): The expected type hint.
		dict (dict[str, Any]): The dictionary to validate.
		name (str): The name of the dictionary parameter.

	Raises:
		ValueError: If the value is invalid.

	"""
	if key not in dict:
			raise ValueError(f"Missing required key in {name}: '{key}'")

	origin_type = get_origin(type_hint) or type_hint

	if not isinstance(dict[key], origin_type):
		raise ValueError(
			f"Invalid type for key '{key}'. "
			f"Expected {origin_type.__name__}, got {type(dict[key]).__name__}.",
		)

	if origin_type is list:
		_deep_validate(dict[key], type_hint)


@validator
def validate_typed_dict(dict: dict[str, Any], name: str, type_hint: type) -> None:
	"""Validate a dictionary with a specific type hint.

	Args:
		dict (dict[str, Any]): The dictionary to validate.
		name (str): The name of the parameter.
		type_hint (type): The expected type hint.

	Raises:
		ValueError: If the dictionary is invalid.

	"""
	for key, type_hint_sub in type_hint.__annotations__.items():
		_validate_field(key, type_hint_sub, dict, name)
