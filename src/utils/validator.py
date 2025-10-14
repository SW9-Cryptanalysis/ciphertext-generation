import inspect
from functools import wraps
from typing import Any, Callable, Protocol, TypeVar
from typing_extensions import ParamSpec

P = ParamSpec("P")
R = TypeVar("R")


class Validator(Protocol):
	"""A callable protocol for a validator function."""

	def __call__(self, value: Any, /, *, name: str, type_hint: type | None) -> None:
		"""Validate the value against the provided type hint.

		Args:
			value (Any): The value to validate.
			name (str): The name of the parameter being validated.
			type_hint (type | None): The expected type of the parameter.

		Raises:
			ValueError: If the value does not meet validation criteria.
			TypeError: If the value's type does not match the type hint.

		"""
		...


def strongly_typed(value: Any, /, *, name: str, type_hint: type | None) -> None:
	"""Ensure the argument's type matches its type hint."""
	if type_hint is None or type_hint is inspect.Parameter.empty:
		return

	if not isinstance(value, type_hint):
		raise TypeError(
			f"Parameter '{name}' requires type '{type_hint.__name__}' "
			f"but received type '{type(value).__name__}'.",
		)


def non_negative(value: Any, /, *, name: str, **_kwargs: Any) -> None:
	"""Ensure a numerical argument is not negative."""
	try:
		if value < 0:
			raise ValueError(
				f"Parameter '{name}' cannot be negative, but received {value}.",
			)
	except TypeError as e:
		# Chain the original exception for better debugging context.
		raise TypeError(
			f"Parameter '{name}' of type '{type(value).__name__}' does not support "
			"non-negative comparison.",
		) from e


def non_blank_string(value: Any, /, *, name: str, **_kwargs: Any) -> None:
	"""Validate that value is a non-empty string."""
	if not isinstance(value, str):
		raise TypeError(f"Parameter '{name}' must be `str`, got `{value.__class__.__name__}`.")
	if not value.strip():
		raise ValueError(f"Parameter `{name}` cannot be blank nor empty.")

# ## --- The Decorator Factory --- ##


def validate(**validators: Validator) -> Callable[[Callable[P, R]], Callable[P, R]]:
	"""Validate function parameters.

	Type-safe and preserves the signature of the decorated function.
	"""

	def decorator(func: Callable[P, R]) -> Callable[P, R]:
		func_sig = inspect.signature(func)

		@wraps(func)
		def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
			bound_args = func_sig.bind(*args, **kwargs)
			bound_args.apply_defaults()

			for param_name, validator_func in validators.items():
				if param_name in bound_args.arguments:
					value = bound_args.arguments[param_name]
					param_details = func_sig.parameters[param_name]

					validator_func(
						value,
						name=param_name,
						type_hint=param_details.annotation or None,
					)
			return func(*args, **kwargs)

		return wrapper

	return decorator
