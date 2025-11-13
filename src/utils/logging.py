import logging
import sys


class AnsiColorFormatter(logging.Formatter):
	"""Formatter that adds ANSI color codes to log messages based on severity level."""

	def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
		"""Initialize the AnsiColorFormatter.

		Args:
			fmt (str, optional): The format string for log messages. Defaults to None.
			datefmt (str, optional): The format string for timestamps. Defaults to None.

		"""
		super().__init__(fmt, datefmt)
		# Define color codes
		self.colors = {
			"grey": "\033[90m",
			"blue": "\033[94m",
			"green": "\033[92m",
			"yellow": "\033[93m",
			"red": "\033[91m",
			"cyan": "\033[96m",
			"reset": "\033[0m",
		}
		self.decorations = {
			"bold": "\033[1m",
			"underline": "\033[4m",
		}
		self.color_codes = {
			"time": "\033[90m",  # Grey
			"level": {
				10: self.colors["blue"],  # Blue
				20: self.colors["green"],  # Green
				30: self.colors["yellow"],  # Yellow
				40: self.colors["red"],  # Red
				50: self.colors["red"] + self.decorations["bold"],  # Bold Red
			},
			"name": self.colors["cyan"],  # Cyan
			"message": self.colors["reset"],  # Reset (default)
			"reset": self.colors["reset"],
		}

	def format(self, record: logging.LogRecord) -> str:
		"""Format a log record.

		Args:
			record (logging.LogRecord): The log record to format.

		Returns:
			str: The formatted log record.

		"""
		asctime = self.formatTime(record, self.datefmt)
		levelname = record.levelname
		levelno = record.levelno
		name = record.name
		message = record.getMessage()

		time_str = f"{self.color_codes['time']}{asctime}{self.color_codes['reset']}"
		level_str = (
			f"{self.color_codes['level'].get(levelno, self.color_codes['reset'])}"
			f"{levelname}{self.color_codes['reset']}"
		)
		name_str = f"{self.color_codes['name']}{name}{self.color_codes['reset']}"
		message_str = (
			f"{self.color_codes['message']}{message}{self.color_codes['reset']}"
		)
		filename_str = (
			f"{self.colors['grey']}({record.filename}:{record.lineno})"
			f"{self.color_codes['reset']}"
		)

		return f"{time_str} | {level_str} | {name_str} | {message_str} {filename_str}"


def get_colored_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
	"""Create and configures a logger with the AnsiColorFormatter.

	Args:
		name (str): The name of the logger
		level (int): The level for which logs should be printed (default: DEBUG (0))

	Returns:
		logging.Logger: A color formatted logger ready for use

	"""
	logger = logging.getLogger(name)
	logger.setLevel(level)

	if not logger.handlers:
		handler = logging.StreamHandler(sys.stdout)
		handler.setLevel(level)

		formatter = AnsiColorFormatter(datefmt="%Y-%m-%d %H:%M:%S")
		handler.setFormatter(formatter)

		logger.addHandler(handler)

	logger.propagate = False

	return logger
