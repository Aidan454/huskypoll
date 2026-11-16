"""Question banks, questions and image uploads."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import services as svc
from app.database.bank_archive import (
    MAX_ARCHIVE_BYTES,
    export_bank,
    import_bank,
    read_archive,
)
from app.database.models import (
    Course,
    CourseInstructor,
    Media,
    Question,
    QuestionBank,
    User,
)

from .. import schemas as s
from ..config import Settings
from ..deps import (
    course_or_404,
    current_user,
    get_db,
    get_settings,
    poll_or_404,
    question_or_404,
    require_instructor,
    require_question_access,
    require_staff,
)
from ..serializers import bank_out, media_url, question_out

router = APIRouter(tags=["questions"])


def _bank_or_404(db: Session, bank_id: int, user: User) -> QuestionBank:
    bank = db.get(QuestionBank, bank_id)
    if bank is None or not _can_use_bank(db, bank, user):
        raise HTTPException(404, "Question bank not found")
    return bank


def _can_use_bank(db: Session, bank: QuestionBank, user: User) -> bool:
    if user.is_admin or bank.owner_id == user.id:
        return True
    if bank.course_id is not None:
        course = db.get(Course, bank.course_id)
        return course is not None and svc.is_instructor(db, course, user)
    return False


def _check_course_link(db: Session, course_id: int | None, user: User) -> None:
    if course_id is not None:
        require_instructor(db, course_or_404(db, course_id), user)


def _check_media(db: Session, *media_ids: int | None) -> None:
    for mid in media_ids:
        if mid is not None and db.get(Media, mid) is None:
            raise HTTPException(400, f"Image {mid} does not exist; upload it first with POST /media")


def _library_bank(db: Session, user: User) -> QuestionBank:
    bank = db.scalar(select(QuestionBank).where(QuestionBank.owner_id == user.id,
                                               QuestionBank.course_id.is_(None), QuestionBank.name == "My questions").order_by(QuestionBank.id))
    if bank is None:
        bank = QuestionBank(owner_id=user.id, name="My questions")
        db.add(bank)
        db.flush()
    return bank


def _library_questions(db: Session, user: User):
    my_courses = select(CourseInstructor.course_id).where(CourseInstructor.user_id == user.id)
    bank_ids = select(QuestionBank.id).where(or_(QuestionBank.owner_id == user.id,
                                                QuestionBank.course_id.in_(my_courses)))
    return db.scalars(select(Question).where(Question.bank_id.in_(bank_ids)).order_by(Question.id.desc())).all()


@router.get("/library", response_model=s.LibraryOut)
def library(db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)],
            settings: Annotated[Settings, Depends(get_settings)]):
    require_staff(user)
    questions = _library_questions(db, user)
    tags = sorted({tag for q in questions for tag in (q.tags or [])}, key=str.casefold)
    return s.LibraryOut(questions=[question_out(settings, q) for q in questions], tags=tags)


@router.post("/library/questions", response_model=s.QuestionOut, status_code=201)
def library_create(body: s.QuestionCreate, db: Annotated[Session, Depends(get_db, scope="function")],
                   user: Annotated[User, Depends(current_user)], settings: Annotated[Settings, Depends(get_settings)]):
    require_staff(user)
    bank = _bank_or_404(db, body.bank_id, user) if body.bank_id else _library_bank(db, user)
    _check_media(db, body.body_media_id, body.explanation_media_id)
    values = body.model_dump(exclude={"bank_id", "options"})
    q = svc.create_question(db, user, bank=bank, **values, options=[(o.text_md, o.is_correct) for o in body.options])
    return question_out(settings, q)


@router.post("/polls/{poll_id}/save-to-bank", response_model=s.QuestionOut, status_code=201)
def save_poll_question(poll_id: int, body: s.SaveToBank,
                       db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)],
                       settings: Annotated[Settings, Depends(get_settings)]):
    poll = poll_or_404(db, poll_id)
    require_instructor(db, poll.session.course, user)
    bank = _bank_or_404(db, body.bank_id, user) if body.bank_id else _library_bank(db, user)
    source = poll.question
    if source.bank_id == bank.id or db.scalar(select(Question.id).where(
            Question.bank_id == bank.id, Question.copied_from_id == source.id)):
        raise HTTPException(409, "This question is already saved in that bank; edit the existing question instead")
    q = svc.copy_question(db, source, user, bank=bank)
    q.tags = body.tags or list(source.tags or [])
    return question_out(settings, q)


@router.get("/library/export")
def library_export(db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)],
                   settings: Annotated[Settings, Depends(get_settings)]):
    require_staff(user)
    return Response(export_bank(_library_questions(db, user), settings.media_dir), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="huskypoll-questions.zip"'})


@router.post("/library/import")
def library_import(file: Annotated[UploadFile, File(...)], db: Annotated[Session, Depends(get_db, scope="function")],
                   user: Annotated[User, Depends(current_user)], settings: Annotated[Settings, Depends(get_settings)],
                   bank_id: int | None = None, preview: bool = False):
    require_staff(user)
    prepared, images = read_archive(file.file.read(MAX_ARCHIVE_BYTES + 1))
    if bank_id is not None:
        _bank_or_404(db, bank_id, user)
    if preview:
        return {"questions": len(prepared), "images": len(images),
                "tags": sorted({t for model, _ in prepared for t in model.tags})}
    bank = _bank_or_404(db, bank_id, user) if bank_id else _library_bank(db, user)
    count, skipped = import_bank(db, prepared, images, user, settings.media_dir, bank,
                                 existing_questions=_library_questions(db, user) if bank_id is None else None)
    return {"imported": count, "skipped": skipped, "bank_id": bank.id}


@router.get("/banks/{bank_id}/export")
def single_bank_export(bank_id: int, db: Annotated[Session, Depends(get_db, scope="function")],
                       user: Annotated[User, Depends(current_user)], settings: Annotated[Settings, Depends(get_settings)]):
    bank = _bank_or_404(db, bank_id, user)
    return Response(export_bank(bank.questions, settings.media_dir), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="huskypoll-questions.zip"'})


# --- banks ----------------------------------------------------------------------

@router.get("/banks", response_model=list[s.BankOut], summary="Banks I own or can use through my courses")
def list_banks(db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)]):
    my_courses = select(CourseInstructor.course_id).where(CourseInstructor.user_id == user.id)
    banks = db.scalars(select(QuestionBank).where(
        or_(QuestionBank.owner_id == user.id, QuestionBank.course_id.in_(my_courses))
    ).order_by(QuestionBank.created_at.desc()))
    return [bank_out(db, b) for b in banks]


@router.post("/banks", response_model=s.BankOut, status_code=201)
def create_bank(body: s.BankCreate, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)]):
    require_staff(user)
    _check_course_link(db, body.course_id, user)
    bank = QuestionBank(owner_id=user.id, **body.model_dump())
    db.add(bank)
    db.flush()
    return bank_out(db, bank)


@router.get("/banks/{bank_id}", response_model=s.BankDetail)
def get_bank(bank_id: int, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)],
             settings: Annotated[Settings, Depends(get_settings)]):
    bank = _bank_or_404(db, bank_id, user)
    qs = db.scalars(select(Question).where(Question.bank_id == bank.id).order_by(Question.id)).all()
    return s.BankDetail(**bank_out(db, bank).model_dump(), questions=[question_out(settings, q) for q in qs])


@router.patch("/banks/{bank_id}", response_model=s.BankOut)
def update_bank(bank_id: int, body: s.BankUpdate, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)]):
    bank = _bank_or_404(db, bank_id, user)
    changes = body.model_dump(exclude_unset=True)
    if "course_id" in changes:
        _check_course_link(db, changes["course_id"], user)
    for k, v in changes.items():
        setattr(bank, k, v)
    db.flush()
    return bank_out(db, bank)


@router.delete("/banks/{bank_id}", status_code=204,
               summary="Delete a bank (its questions are kept, just no longer in a bank)")
def delete_bank(bank_id: int, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)]):
    bank = _bank_or_404(db, bank_id, user)
    if bank.owner_id != user.id and not user.is_admin:
        raise HTTPException(403, "Only the bank's owner can delete it")
    db.delete(bank)


@router.post("/banks/{bank_id}/copy", response_model=s.BankOut, status_code=201,
             summary="Copy a bank, e.g. into next semester's course")
def copy_bank(bank_id: int, body: s.BankCopy, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)]):
    bank = _bank_or_404(db, bank_id, user)
    course = None
    if body.course_id is not None:
        course = course_or_404(db, body.course_id)
        require_instructor(db, course, user)
    return bank_out(db, svc.copy_bank(db, bank, user, name=body.name, course=course))


# --- questions -----------------------------------------------------------------

@router.post("/questions", response_model=s.QuestionOut, status_code=201)
def create_question(body: s.QuestionCreate, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)],
                    settings: Annotated[Settings, Depends(get_settings)]):
    require_staff(user)
    bank = _bank_or_404(db, body.bank_id, user) if body.bank_id else None
    _check_media(db, body.body_media_id, body.explanation_media_id)
    data = body.model_dump(exclude={"bank_id", "options"})
    q = svc.create_question(db, user, bank=bank, options=[(o.text_md, o.is_correct) for o in body.options], **data)
    return question_out(settings, q)


@router.get("/questions/{question_id}", response_model=s.QuestionOut)
def get_question(question_id: int, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)],
                 settings: Annotated[Settings, Depends(get_settings)]):
    q = question_or_404(db, question_id)
    require_question_access(db, q, user)
    return question_out(settings, q)


@router.patch("/questions/{question_id}", response_model=s.QuestionUpdateOut,
              summary="Edit a question (after it's been polled, only the answer and explanation)")
def update_question(question_id: int, body: s.QuestionUpdate, db: Annotated[Session, Depends(get_db, scope="function")],
                    user: Annotated[User, Depends(current_user)], settings: Annotated[Settings, Depends(get_settings)]):
    q = question_or_404(db, question_id)
    require_question_access(db, q, user)
    changes = body.model_dump(exclude_unset=True)
    options = changes.pop("options", None)
    correct_ids = changes.pop("correct_option_ids", None)
    if changes.get("bank_id") is not None:
        _bank_or_404(db, changes["bank_id"], user)
    _check_media(db, changes.get("body_media_id"), changes.get("explanation_media_id"))
    q, regraded = svc.update_question(
        db, q, options=[(o["text_md"], o["is_correct"]) for o in options] if options is not None else None,
        correct_option_ids=correct_ids, **changes)
    db.refresh(q)
    return s.QuestionUpdateOut(question=question_out(settings, q), responses_regraded=regraded)


@router.post("/questions/{question_id}/copy", response_model=s.QuestionOut, status_code=201,
             summary="Editable copy (use this to change a question that has been polled)")
def copy_question(question_id: int, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)],
                  settings: Annotated[Settings, Depends(get_settings)]):
    q = question_or_404(db, question_id)
    require_question_access(db, q, user)
    return question_out(settings, svc.copy_question(db, q, user))


@router.delete("/questions/{question_id}", status_code=204, summary="Delete a question that was never polled")
def delete_question(question_id: int, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)]):
    q = question_or_404(db, question_id)
    require_question_access(db, q, user)
    svc.delete_question(db, q)


# --- images -------------------------------------------------------------------

@router.post("/media", response_model=s.MediaOut, status_code=201,
             summary="Upload or paste an image (PNG, JPEG, GIF, WebP; 10 MB max)", tags=["media"])
def upload_media(file: Annotated[UploadFile, File(...)], db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)],
                 settings: Annotated[Settings, Depends(get_settings)]):
    require_staff(user)
    data = file.file.read(svc.MAX_IMAGE_BYTES + 1)
    m = svc.save_media(db, data, user, settings.media_dir)
    return s.MediaOut(id=m.id, url=media_url(settings, m), mime_type=m.mime_type, size_bytes=m.size_bytes)


@router.get("/media/{sha256}", response_class=FileResponse, summary="Get an image", tags=["media"])
def get_media(sha256: str, db: Annotated[Session, Depends(get_db, scope="function")], user: Annotated[User, Depends(current_user)],
              settings: Annotated[Settings, Depends(get_settings)]):
    m = db.scalar(select(Media).where(Media.sha256 == sha256.lower()))
    if m is None:
        raise HTTPException(404, "Image not found")
    path = (Path(settings.media_dir) / m.file_path).resolve()
    if not path.is_file() or Path(settings.media_dir).resolve() not in path.parents:
        raise HTTPException(404, "Image file missing")
    return FileResponse(path, media_type=m.mime_type, headers={"Cache-Control": "private, max-age=31536000, immutable",
                                                               "X-Content-Type-Options": "nosniff"})
