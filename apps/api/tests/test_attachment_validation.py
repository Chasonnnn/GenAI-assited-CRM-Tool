from app.services import attachment_service


def test_validate_file_allows_csv_mp4_mov():
    samples = [
        ("report.csv", "text/csv"),
        ("video.mp4", "video/mp4"),
        ("clip.mov", "video/quicktime"),
    ]

    for filename, content_type in samples:
        is_valid, error = attachment_service.validate_file(
            filename,
            content_type,
            file_size=1024,
        )
        assert is_valid, error
