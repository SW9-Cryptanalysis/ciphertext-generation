import os
import json
from io import BytesIO
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.external_account_authorized_user import (
	Credentials as ExternalCredentials,
)
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from encipherment.cipher import SubstitutionCipher
from typing import Any
import dotenv
from utils.logging import get_colored_logger

log = get_colored_logger("drive")

dotenv.load_dotenv()

# --- Configuration Constants ---
# Full scope is needed to upload files
SCOPES = ["https://www.googleapis.com/auth/drive"]
# File names for credentials and saved token
CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")
TOKEN_JSON = os.getenv("GOOGLE_JSON_TOKEN")
TEMP_TOKEN_FILE = "temp_token_for_auth.json"  # noqa: S105
DRIVE_VERSION = "v3"
TEMP_CREDENTIALS_FILE = "temp_google_credentials.json"


def authenticate_drive_terminal() -> build:  # type: ignore
	"""Handle Google Drive API authentication using OAuth 2.0 (Terminal/Console mode).

	This function will prompt the user to manually open a URL and paste a code
	back into the terminal on the first run.

	Returns:
		The authenticated Google Drive service object.

	"""
	creds = None

	if TOKEN_JSON and TOKEN_JSON.strip() != "":
		creds_info = json.loads(TOKEN_JSON)
		creds = Credentials.from_authorized_user_info(creds_info, SCOPES)

	if not creds or not creds.valid:
		if creds and creds.expired:
			creds.refresh(Request())
		else:
			creds = authenticate()

		token_content = creds.to_json()

		os.environ["GOOGLE_TOKEN_JSON"] = token_content
		log.info("Updated GOOGLE_TOKEN_JSON in current environment.")

		log.warning(
			"\nACTION REQUIRED: For permanent storage, copy the token content below:",
		)
		log.warning(
			"----------------------------------------------------------------------",
		)
		log.warning(token_content)
		log.warning(
			"----------------------------------------------------------------------",
		)
		log.warning(
			"Paste this JSON string into GOOGLE_TOKEN_JSON in your actual .env file.",
		)

	# 4. Build the Drive service object
	return build("drive", DRIVE_VERSION, credentials=creds)


def authenticate() -> Credentials | ExternalCredentials:
	"""Authenticate with Google Drive using the provided credentials.

	Returns:
		Credentials: The authenticated credentials.

	"""
	creds = None

	with open(TEMP_CREDENTIALS_FILE, "w") as f:
		f.write(CREDENTIALS_JSON if CREDENTIALS_JSON else "")
	try:
		flow = InstalledAppFlow.from_client_secrets_file(
			TEMP_CREDENTIALS_FILE,
			SCOPES,
		)

		creds = flow.run_local_server(
			port=0,
			success_message="Authentication successful! You can close thisbrowser tab.",
		)
		log.info("Authentication successful.")
	finally:
		if os.path.exists(TEMP_CREDENTIALS_FILE):
			os.remove(TEMP_CREDENTIALS_FILE)

	return creds


def create_cipher_json(cipher: SubstitutionCipher) -> tuple[str, bytes]:
	"""Convert a Python dictionary of cipher data into a JSON string and bytes.

	Args:
		cipher(SubstitutionCipher): The cipher object to convert to JSON.

	Returns:
		tuple[str, bytes]: A tuple containing the JSON string and its byte
			representation.

	"""
	json_string = json.dumps(cipher.__json__(), indent=4)
	file_bytes = json_string.encode("utf-8")
	return json_string, file_bytes


def upload_to_drive(
	drive_service: build,  # type: ignore
	file_bytes: bytes,
	filename: str,
	folder_id: str | None = None,
) -> str:
	"""Upload the byte content to Google Drive.

	Args:
		drive_service (build): The authenticated Google Drive service object.
		file_bytes (bytes): The byte content of the file to upload.
		filename (str): The desired name for the file on Google Drive
			(e.g., 'cipher.json').
		folder_id (str | None, optional): The ID of the folder to upload the file to.
			If None, uploads to the root folder.

	Returns:
		str: The ID of the newly created file.

	"""
	log.debug(f"\nAttempting to upload file: {filename}...")

	media = MediaIoBaseUpload(
		BytesIO(file_bytes),
		mimetype="application/json",
		chunksize=-1,
		resumable=True,
	)

	file_metadata: dict[str, Any] = {"name": filename}

	if folder_id:
		file_metadata["parents"] = [folder_id]
	try:
		file = (
			drive_service.files()
			.create(
				body=file_metadata,
				media_body=media,
				fields="id, name, parents",
			)
			.execute()
		)

		parent_folder = file.get("parents", ["Root"])[0]
		log.info(
			f"✅ Upload successful! File name: {file.get('name')} in folder: "
			f"{parent_folder}",
		)
		return file.get("id")

	except Exception as error:
		log.error(f"❌ An error occurred during upload: {error}")
		return ""
