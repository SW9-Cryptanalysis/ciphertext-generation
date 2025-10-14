import pytest
from utils.validator import validate, strongly_typed, non_negative, non_blank_string

# ## --- Setup: Dummy Functions for Testing --- ##
# These simple functions are decorated to test the behavior of the validators.


@validate(name=non_blank_string)
def set_name(name: str):
	"""A dummy function to test the non_blank_string validator."""
	return f"Name set to {name}"


@validate(age=non_negative)
def set_age(age: int):
	"""A dummy function to test the non_negative validator."""
	return f"Age set to {age}"


@validate(user_id=strongly_typed)
def set_user_id(user_id: str):
	"""A dummy function to test the strongly_typed validator."""
	return f"User ID set to {user_id}"


@validate(item_id=strongly_typed)
def set_untyped_item_id(item_id):  # No type hint on purpose
	"""A dummy function to test strongly_typed with no type hint."""
	return f"Untyped ID set to {item_id}"


@validate(name=non_blank_string, age=non_negative)
def create_user(name: str, age: int, is_active: bool = True):
	"""A dummy function to test multiple validators at once."""
	return f"User {name} ({age}) created. Active: {is_active}"


def test_decorator_success_cases():
	"""Tests that the decorator allows valid calls to proceed."""
	assert create_user("Alice", 30) == "User Alice (30) created. Active: True"
	assert create_user(name="Bob", age=0) == "User Bob (0) created. Active: True"
	assert (
		create_user("Charlie", 100, is_active=False)
		== "User Charlie (100) created. Active: False"
	)


def test_non_blank_string_validator():
	"""Tests the non_blank_string validator for success and failure."""
	assert set_name("Valid Name") == "Name set to Valid Name"

	with pytest.raises(ValueError) as excinfo:
		set_name("")
	assert "cannot be blank nor empty" in str(excinfo.value)

	with pytest.raises(ValueError) as excinfo:
		set_name("    ")
	assert "cannot be blank nor empty" in str(excinfo.value)

	with pytest.raises(TypeError) as excinfo:
		set_name(123)  # type: ignore
	assert "must be `str`, got `int`" in str(excinfo.value)


def test_non_negative_validator():
	"""Tests the non_negative validator for success and failure."""
	assert set_age(100) == "Age set to 100"
	assert set_age(0) == "Age set to 0"
	assert set_age(123.45) == "Age set to 123.45"  # type: ignore

	with pytest.raises(ValueError) as excinfo:
		set_age(-1)
	assert "cannot be negative" in str(excinfo.value)

	with pytest.raises(TypeError) as excinfo:
		set_age("not a number")  # type: ignore
	assert "does not support non-negative comparison" in str(excinfo.value)


def test_strongly_typed_validator():
	"""Tests the strongly_typed validator for success and failure."""
	assert set_user_id("user-123-abc") == "User ID set to user-123-abc"

	# Test failure when the type is incorrect
	with pytest.raises(TypeError) as excinfo:
		set_user_id(12345)  # type: ignore
	assert "Parameter 'user_id' requires type 'str' but received type 'int'" in str(
		excinfo.value
	)

	# Test that it correctly does nothing if no type hint is present
	assert set_untyped_item_id(123) == "Untyped ID set to 123"
	assert set_untyped_item_id("abc") == "Untyped ID set to abc"
