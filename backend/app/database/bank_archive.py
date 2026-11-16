"""Portable, versioned JSON + images in a ZIP; never extracts uploaded paths."""
from __future__ import annotations

import io
import json
import math
import zipfile
from pathlib import Path, PurePosixPath

from pydantic import ValidationError

from app.schemas import QuestionCreate

from . import services as svc
from .models import QuestionBank

MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_EXPANDED_BYTES = 100 * 1024 * 1024
MAX_QUESTIONS = 1000
FIELDS = ("type", "body_md", "explanation_md", "text_answer", "numeric_answer", "numeric_tolerance", "tags")


def export_bank(questions, media_dir) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        images = set()
        expanded = 0

        def image(media):
            nonlocal expanded
            if media is None:
                return None
            name = f"images/{media.sha256}{Path(media.file_path).suffix}"
            path = (Path(media_dir) / media.file_path).resolve()
            if Path(media_dir).resolve() not in path.parents or not path.is_file():
                raise svc.HuskyPollError("A question image is missing; restore it before exporting")
            if name not in images:
                payload = path.read_bytes()
                expanded += len(payload)
                if expanded > MAX_EXPANDED_BYTES:
                    raise svc.HuskyPollError("Export images exceed 100 MB")
                archive.writestr(name, payload)
                images.add(name)
            return name

        rows = []
        for q in questions:
            row = {key: getattr(q, key) for key in FIELDS}
            row["body_image"] = image(q.body_media)
            row["explanation_image"] = image(q.explanation_media)
            row["options"] = [{"text_md": o.text_md, "is_correct": o.is_correct, "image": image(o.media)}
                              for o in q.options]
            rows.append(row)
        if len(rows) > MAX_QUESTIONS:
            raise svc.HuskyPollError("Export at most 1000 questions at a time")
        manifest = json.dumps({"format": "huskypoll-question-bank", "version": 1,
                               "questions": rows}, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(manifest) > 5 * 1024 * 1024 or expanded + len(manifest) > MAX_EXPANDED_BYTES:
            raise svc.HuskyPollError("Export exceeds the portable archive size limits")
        archive.writestr("manifest.json", manifest)
    if len(stream.getvalue()) > MAX_ARCHIVE_BYTES:
        raise svc.HuskyPollError("Question bank export exceeds 50 MB")
    return stream.getvalue()


def read_archive(data: bytes):
    """Validate the entire archive before any records or files are created."""
    if len(data) > MAX_ARCHIVE_BYTES:
        raise svc.HuskyPollError("Question bank ZIP must be at most 50 MB")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [item.filename for item in infos]
            if len(names) != len(set(names)) or len(names) > 4001:
                raise ValueError("Duplicate paths or too many archive entries")
            if sum(item.file_size for item in infos) > MAX_EXPANDED_BYTES:
                raise ValueError("Expanded archive exceeds 100 MB")
            for name in names:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name:
                    raise ValueError("Unsafe archive path")
            if "manifest.json" not in names or archive.getinfo("manifest.json").file_size > 5 * 1024 * 1024:
                raise ValueError("Missing or oversized manifest.json")
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict) or manifest.get("format") != "huskypoll-question-bank" or manifest.get("version") != 1:
                raise ValueError("Unsupported question bank format/version")
            rows = manifest.get("questions")
            if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_QUESTIONS:
                raise ValueError("Archive must contain 1–1000 questions")
            images = {}

            def check_image(name):
                if name is None:
                    return
                if not isinstance(name, str) or not name.startswith("images/") or name not in names:
                    raise ValueError("Missing image reference")
                if archive.getinfo(name).file_size > svc.MAX_IMAGE_BYTES:
                    raise ValueError("An image exceeds 10 MB")
                if name not in images:
                    payload = archive.read(name)
                    svc.detect_image_type(payload)
                    images[name] = payload

            prepared = []
            for row in rows:
                if not isinstance(row, dict) or set(row) - set(FIELDS) - {"body_image", "explanation_image", "options"}:
                    raise ValueError("Invalid question fields")
                options = row.get("options", [])
                if not isinstance(options, list) or len(options) > 26:
                    raise ValueError("Use at most 26 choices")
                for option in options:
                    if not isinstance(option, dict) or set(option) - {"text_md", "is_correct", "image"}:
                        raise ValueError("Invalid choice fields")
                    check_image(option.get("image"))
                check_image(row.get("body_image"))
                check_image(row.get("explanation_image"))
                model = QuestionCreate.model_validate({**{key: row[key] for key in FIELDS if key in row},
                    "options": [{key: option[key] for key in ("text_md", "is_correct") if key in option}
                                for option in options]})
                if not model.body_md.strip() and not row.get("body_image"):
                    raise ValueError("Each question needs text or an image")
                if model.type.startswith("mc") and len(model.options) < 2:
                    raise ValueError("Multiple-choice questions need at least two choices")
                if model.type == "mc_single" and sum(o.is_correct for o in model.options) > 1:
                    raise ValueError("Single-choice questions may have at most one correct answer")
                if any(value is not None and not math.isfinite(value) for value in
                       (model.numeric_answer, model.numeric_tolerance)):
                    raise ValueError("Numeric answers and tolerances must be finite")
                if model.type != "numeric" and (model.numeric_answer is not None or model.numeric_tolerance is not None):
                    raise ValueError("Only numeric questions may have a numeric answer")
                prepared.append((model, row))
            return prepared, images
    except (ValueError, TypeError, KeyError, zipfile.BadZipFile, RuntimeError, ValidationError) as exc:
        raise svc.HuskyPollError(f"Cannot import question bank: {exc}") from exc


def import_bank(db, prepared, images, user, media_dir, bank: QuestionBank, existing_questions=None):
    media_ids = {name: svc.save_media(db, payload, user, media_dir).id for name, payload in images.items()}
    def identity(values, body_id, explanation_id, options):
        content = {**values, "tags": sorted(values.get("tags") or [], key=str.casefold),
                   "body_media_id": body_id, "explanation_media_id": explanation_id, "options": options}
        return json.dumps(content, sort_keys=True, ensure_ascii=False, allow_nan=False)

    existing = {identity({key: getattr(q, key) for key in FIELDS}, q.body_media_id, q.explanation_media_id,
                         [(o.text_md, o.is_correct, o.media_id) for o in q.options]) for q in (bank.questions if existing_questions is None else existing_questions)}
    imported = 0
    for model, row in prepared:
        values = model.model_dump(exclude={"bank_id", "options", "body_media_id", "explanation_media_id"})
        options = [(o.text_md, o.is_correct, media_ids.get(original.get("image")))
                   for o, original in zip(model.options, row.get("options", []), strict=True)]
        key = identity(values, media_ids.get(row.get("body_image")), media_ids.get(row.get("explanation_image")), options)
        if key in existing:
            continue
        existing.add(key)
        imported += 1
        q = svc.create_question(db, user, bank=bank, **values,
            body_media_id=media_ids.get(row.get("body_image")),
            explanation_media_id=media_ids.get(row.get("explanation_image")),
            options=[(o.text_md, o.is_correct) for o in model.options])
        for option, original in zip(q.options, row.get("options", []), strict=True):
            option.media_id = media_ids.get(original.get("image"))
    db.flush()
    return imported, len(prepared) - imported
