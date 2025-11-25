import pytest
import json
import os
from unittest.mock import MagicMock, mock_open
from google.oauth2.credentials import Credentials
from utils.drive import (
    authenticate_drive_terminal,
    create_cipher_json,
    upload_to_drive,
    CREDENTIALS_JSON,
    TOKEN_JSON,
)

@pytest.fixture
def mock_credentials():
    creds = MagicMock(spec=Credentials)
    creds.valid = True
    creds.expired = False
    creds.to_json.return_value = '{"token": "mock_token"}'
    return creds

@pytest.fixture
def mock_cipher():
    cipher = MagicMock()
    # Directly assign the mock method to bypass configure_mock's getattr check on dunders
    cipher.__json__ = MagicMock(return_value={"plaintext": "test", "ciphertext": "1 2 3"})
    return cipher

class TestDriveUtils:

    def test_authenticate_drive_terminal_existing_valid_token(self, mocker, mock_credentials):
        mocker.patch("utils.drive.TOKEN_JSON", '{"token": "valid"}')
        mocker.patch("google.oauth2.credentials.Credentials.from_authorized_user_info", return_value=mock_credentials)
        mock_build = mocker.patch("utils.drive.build")

        service = authenticate_drive_terminal()

        assert service == mock_build.return_value
        mock_build.assert_called_once_with("drive", "v3", credentials=mock_credentials)

    def test_authenticate_drive_terminal_expired_token_refresh(self, mocker, mock_credentials):
        mock_credentials.valid = False
        mock_credentials.expired = True
        mock_credentials.refresh_token = "refresh_token"
        
        mocker.patch("utils.drive.TOKEN_JSON", '{"token": "expired"}')
        mocker.patch("google.oauth2.credentials.Credentials.from_authorized_user_info", return_value=mock_credentials)
        mock_build = mocker.patch("utils.drive.build")
        
        service = authenticate_drive_terminal()

        mock_credentials.refresh.assert_called_once()
        assert service == mock_build.return_value

    def test_authenticate_drive_terminal_new_auth_flow(self, mocker, mock_credentials):
        mocker.patch("utils.drive.TOKEN_JSON", "")
        
        mock_flow = mocker.patch("utils.drive.InstalledAppFlow")
        mock_flow.from_client_secrets_file.return_value.run_local_server.return_value = mock_credentials
        
        mock_build = mocker.patch("utils.drive.build")
        mocker.patch("builtins.open", mock_open())
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.remove")

        service = authenticate_drive_terminal()

        assert service == mock_build.return_value
        mock_flow.from_client_secrets_file.return_value.run_local_server.assert_called_once()

    def test_create_cipher_json(self, mock_cipher):
        json_str, file_bytes = create_cipher_json(mock_cipher)

        expected_dict = {"plaintext": "test", "ciphertext": "1 2 3"}
        assert json.loads(json_str) == expected_dict
        assert file_bytes == json_str.encode("utf-8")

    def test_upload_to_drive_success(self, mocker):
        mock_service = MagicMock()
        mock_execute = mock_service.files.return_value.create.return_value.execute
        mock_execute.return_value = {"id": "file_123", "name": "cipher.json", "parents": ["root"]}
        
        file_id = upload_to_drive(
            mock_service,
            b"data",
            "cipher.json",
            "folder_123"
        )

        assert file_id == "file_123"
        mock_service.files.return_value.create.assert_called_once()
        
        call_kwargs = mock_service.files.return_value.create.call_args[1]
        assert call_kwargs["body"]["name"] == "cipher.json"
        assert call_kwargs["body"]["parents"] == ["folder_123"]

    def test_upload_to_drive_failure(self, mocker):
        mock_service = MagicMock()
        mock_service.files.return_value.create.return_value.execute.side_effect = Exception("Upload failed")
        mock_log = mocker.patch("utils.drive.log")

        file_id = upload_to_drive(
            mock_service,
            b"data",
            "cipher.json"
        )

        assert file_id == ""
        mock_log.error.assert_called_once()