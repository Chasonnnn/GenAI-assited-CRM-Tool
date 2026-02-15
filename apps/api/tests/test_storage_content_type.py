import io
import unittest.mock
from app.services import attachment_service

def test_store_file_passes_content_type_to_s3(monkeypatch):
    mock_s3 = unittest.mock.Mock()

    # Mock _get_s3_client to return our mock
    monkeypatch.setattr(attachment_service, "_get_s3_client", lambda: mock_s3)

    # Mock _get_storage_backend to return "s3"
    monkeypatch.setattr(attachment_service, "_get_storage_backend", lambda: "s3")

    file_content = b"test content"
    file = io.BytesIO(file_content)
    storage_key = "test/key.txt"
    content_type = "text/plain"

    attachment_service.store_file(storage_key, file, content_type=content_type)

    mock_s3.upload_fileobj.assert_called_once_with(
        file,
        unittest.mock.ANY, # bucket
        storage_key,
        ExtraArgs={"ContentType": content_type}
    )

def test_store_file_passes_no_content_type_if_none(monkeypatch):
    mock_s3 = unittest.mock.Mock()

    # Mock _get_s3_client to return our mock
    monkeypatch.setattr(attachment_service, "_get_s3_client", lambda: mock_s3)

    # Mock _get_storage_backend to return "s3"
    monkeypatch.setattr(attachment_service, "_get_storage_backend", lambda: "s3")

    file_content = b"test content"
    file = io.BytesIO(file_content)
    storage_key = "test/key.txt"

    attachment_service.store_file(storage_key, file)

    mock_s3.upload_fileobj.assert_called_once_with(
        file,
        unittest.mock.ANY, # bucket
        storage_key,
        ExtraArgs=None
    )
