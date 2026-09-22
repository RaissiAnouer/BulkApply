"""CV management service — upload, safe atomic replacement, parsing, update, and deletion."""

import os
import uuid
import re
from pathlib import Path
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.user import User
from app.models.cv import CV
from app.schemas.cv import ParsedDataUpdateRequest
from app.services import cv_parser_service

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {"pdf", "docx"}
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "cvs"


def _ensure_upload_dir():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(filename: str | None) -> str:
    """Sanitize original filename purely for safe display metadata."""
    if not filename:
        return "resume.pdf"
    # Strip any directory traversal components
    base = os.path.basename(filename)
    # Remove any control or hazardous characters
    cleaned = re.sub(r"[^\w\.\-\s]", "", base).strip()
    return cleaned or "resume.pdf"


def save_and_parse_cv(db: Session, user: User, file: UploadFile) -> tuple[CV, bool]:
    """
    Safely uploads and parses a CV document.
    Atomic replacement:
      1. Validates format and size.
      2. Saves new file using a secure UUID.
      3. Extracts and parses text.
      4. If parsing succeeds, deletes the old physical file and updates DB record.
      5. If anything fails, removes the new file and keeps existing CV untouched.
    Returns (cv_record, is_created).
    """
    _ensure_upload_dir()

    original_name = file.filename or ""
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Invalid file format. Only PDF and DOCX documents are accepted.")

    # Read content to validate size
    content = file.file.read()
    file_size = len(content)

    if file_size == 0:
        raise ValueError("Uploaded file is empty.")

    if file_size > MAX_FILE_SIZE:
        raise ValueError("File size exceeds the 5 MB limit.")

    # Generate secure random UUID filename on disk
    secure_filename = f"cv_{user.id}_{uuid.uuid4().hex}.{ext}"
    target_path = UPLOAD_DIR / secure_filename

    # Step 1: Write new file to disk
    try:
        with open(target_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise IOError(f"Could not save file to disk: {str(e)}")

    # Step 2: Extract text and parse
    try:
        raw_text = cv_parser_service.extract_text(str(target_path), ext)
        parsed_data = cv_parser_service.parse_cv_text(raw_text)
    except Exception as e:
        # Clean up newly written file on extraction/parsing failure
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise ValueError(f"Failed to read or parse CV file: {str(e)}")

    display_name = _sanitize_filename(original_name)

    # Step 3: Check for existing active CV (Replacement Flow)
    existing_cv = db.query(CV).filter(CV.user_id == user.id).first()

    if existing_cv:
        old_file = Path(existing_cv.file_path)
        # Delete old file only after new file parsing has succeeded
        if old_file.exists():
            old_file.unlink(missing_ok=True)

        existing_cv.file_path = str(target_path)
        existing_cv.file_name = display_name
        existing_cv.file_type = ext
        existing_cv.file_size = file_size
        existing_cv.parsed_data = parsed_data
        existing_cv.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(existing_cv)
        return existing_cv, False
    else:
        # Initial creation
        new_cv = CV(
            user_id=user.id,
            file_path=str(target_path),
            file_name=display_name,
            file_type=ext,
            file_size=file_size,
            parsed_data=parsed_data,
        )
        db.add(new_cv)
        db.commit()
        db.refresh(new_cv)
        return new_cv, True


def get_cv(db: Session, user: User) -> CV:
    """Retrieve the active CV for the candidate."""
    cv = db.query(CV).filter(CV.user_id == user.id).first()
    if not cv:
        raise ValueError("No active CV found.")
    return cv


def update_parsed_data(db: Session, user: User, data: ParsedDataUpdateRequest) -> CV:
    """Update manual corrections to parsed CV data."""
    cv = get_cv(db, user)

    new_data = dict(cv.parsed_data or {})
    update_dict = data.model_dump(exclude_unset=True)

    for key, val in update_dict.items():
        new_data[key] = val

    cv.parsed_data = new_data
    flag_modified(cv, "parsed_data")
    cv.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(cv)
    return cv


def delete_cv(db: Session, user: User) -> None:
    """Delete active CV physical file and database record."""
    cv = get_cv(db, user)

    # Delete physical file
    file_path = Path(cv.file_path)
    if file_path.exists():
        file_path.unlink(missing_ok=True)

    db.delete(cv)
    db.commit()
