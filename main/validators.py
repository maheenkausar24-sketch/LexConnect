from pathlib import Path
import re

from django.core.exceptions import ValidationError


MAX_CHAT_FILE_SIZE = 5 * 1024 * 1024
MAX_DOCUMENT_FILE_SIZE = 10 * 1024 * 1024
MAX_UPLOAD_FILENAME_LENGTH = 180
ALLOWED_CHAT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".txt", ".doc", ".docx"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".doc", ".docx"}
ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".webp": {"image/webp"},
    ".txt": {"text/plain"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip", "application/octet-stream"},
}
MAGIC_HEADERS = {
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".webp": (b"RIFF",),
    ".docx": (b"PK\x03\x04",),
}
SUSPICIOUS_FILENAME_PATTERN = re.compile(r"[\x00-\x1f\x7f]")


def file_header(uploaded_file, length=16):
    position = uploaded_file.tell() if hasattr(uploaded_file, "tell") else None
    header = uploaded_file.read(length)
    if position is not None:
        uploaded_file.seek(position)
    return header


def validate_uploaded_file(uploaded_file, *, allowed_extensions, max_size):
    if not uploaded_file:
        return

    filename = uploaded_file.name or ""
    if "/" in filename or "\\" in filename:
        raise ValidationError("Filename cannot contain path separators.")
    if len(filename) > MAX_UPLOAD_FILENAME_LENGTH:
        raise ValidationError("Filename is too long.")
    if SUSPICIOUS_FILENAME_PATTERN.search(filename):
        raise ValidationError("Filename contains unsupported characters.")
    if Path(filename).name.startswith("."):
        raise ValidationError("Hidden filenames are not allowed.")

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValidationError(f"Unsupported file type. Allowed types: {allowed}.")

    if extension == ".svg":
        raise ValidationError("SVG uploads are not allowed for security reasons.")

    if uploaded_file.size > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValidationError(f"File is too large. Maximum size is {max_mb} MB.")
    if uploaded_file.size <= 0:
        raise ValidationError("File cannot be empty.")

    content_type = (getattr(uploaded_file, "content_type", "") or "").split(";", 1)[0].strip().lower()
    allowed_mimes = ALLOWED_MIME_TYPES.get(extension, set())
    if content_type and allowed_mimes and content_type not in allowed_mimes:
        raise ValidationError("Uploaded file content type does not match the extension.")

    header = file_header(uploaded_file)
    expected_headers = MAGIC_HEADERS.get(extension)
    if expected_headers and header and not any(header.startswith(expected) for expected in expected_headers):
        raise ValidationError("Uploaded file contents do not match the extension.")
    if extension == ".webp" and len(header) >= 12 and header[8:12] != b"WEBP":
        raise ValidationError("Uploaded file contents do not match the extension.")


def validate_chat_file(uploaded_file):
    validate_uploaded_file(
        uploaded_file,
        allowed_extensions=ALLOWED_CHAT_EXTENSIONS,
        max_size=MAX_CHAT_FILE_SIZE,
    )


def validate_legal_document(uploaded_file):
    validate_uploaded_file(
        uploaded_file,
        allowed_extensions=ALLOWED_DOCUMENT_EXTENSIONS,
        max_size=MAX_DOCUMENT_FILE_SIZE,
    )
