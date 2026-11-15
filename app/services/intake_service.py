import logging
import re

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.lead_follow_up import LeadFollowUp
from app.schemas.intake import FormSubmission

logger = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Accepts "13900139000", "139 0013 9000", "139-0013-9000" and the +86 variants.
PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?86[\s-]?)?(1[3-9]\d(?:[\s-]?\d{4}){2})(?!\d)"
)


class IntakeValidationError(Exception):
    """Raised when a submission contains no usable contact information."""


def normalize_phone(raw: str | None) -> str | None:
    """Keep digits only, drop the +86 / 0086 country prefix, and validate the length."""
    if not raw:
        return None

    digits = re.sub(r"\D", "", raw)

    if digits.startswith("0086"):
        digits = digits[4:]
    elif digits.startswith("86") and len(digits) == 13:
        digits = digits[2:]

    if not 6 <= len(digits) <= 15:
        return None

    return digits


def normalize_email(raw: str | None) -> str | None:
    """Lowercase the address and reject anything that is not a valid email."""
    if not raw:
        return None

    value = raw.strip().strip(".,;:").lower()

    return value if EMAIL_PATTERN.fullmatch(value) else None


def _collect_extra_text(submission: FormSubmission) -> str:
    """Join unknown form fields, which often carry the message of custom forms."""
    extra = submission.model_extra or {}

    return "\n".join(
        value.strip()
        for value in extra.values()
        if isinstance(value, str) and value.strip()
    )


def extract_contact_info(submission: FormSubmission) -> tuple[dict, list[str]]:
    """Normalize explicit fields and recover missing ones from the free text.

    Returns the lead fields plus the list of fields recovered from free text,
    which the API exposes so callers can see what was inferred.
    """
    extra_text = _collect_extra_text(submission)
    free_text = "\n".join(part for part in (submission.message, extra_text) if part)

    extracted: list[str] = []

    email = normalize_email(submission.email)

    if email is None and free_text:
        match = EMAIL_PATTERN.search(free_text)
        if match:
            email = normalize_email(match.group(0))
            if email:
                extracted.append("email")

    phone = normalize_phone(submission.phone)

    if phone is None and free_text:
        match = PHONE_PATTERN.search(free_text)
        if match:
            phone = normalize_phone(match.group(1))
            if phone:
                extracted.append("phone")

    name = (submission.name or "").strip() or None

    if name is None and email:
        name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        extracted.append("name")

    if not name:
        name = "Website visitor"

    company = (submission.company or "").strip() or None

    message_parts = [
        part.strip()
        for part in (submission.message, extra_text)
        if part and part.strip()
    ]
    message = "\n\n".join(message_parts) or None

    if phone is None and email is None:
        raise IntakeValidationError(
            "A phone number or an email address is required"
        )

    fields = {
        "name": name[:100],
        # The leads table requires a phone number; an empty string is stored when
        # the visitor only left an email address.
        "phone": phone or "",
        "email": email,
        "company": company[:255] if company else None,
        "message": message,
    }

    return fields, extracted


def find_duplicate(db: Session, email: str | None, phone: str | None) -> Lead | None:
    """Find an existing lead with the same email or phone number."""
    conditions = []

    if email:
        conditions.append(func.lower(Lead.email) == email)
    if phone:
        conditions.append(Lead.phone == phone)

    if not conditions:
        return None

    statement = (
        select(Lead)
        .where(or_(*conditions))
        .order_by(Lead.id.asc())
        .limit(1)
    )

    return db.scalars(statement).first()


def submit_form(
    db: Session,
    submission: FormSubmission,
    source: str,
) -> tuple[Lead, bool, list[str]]:
    """Create a lead from a website form, or attach a note when it is a duplicate.

    Returns (lead, duplicate, extracted_fields).
    """
    fields, extracted = extract_contact_info(submission)

    duplicate = find_duplicate(db, fields["email"], fields["phone"])

    if duplicate is not None:
        note = fields["message"] or "Duplicate form submission without a message."
        db.add(
            LeadFollowUp(
                lead_id=duplicate.id,
                content=f"Duplicate submission ({source}): {note}",
            )
        )
        db.commit()
        db.refresh(duplicate)

        logger.info("Duplicate form submission matched lead %s", duplicate.id)

        return duplicate, True, extracted

    lead = Lead(status="NEW", **fields)
    db.add(lead)
    db.commit()
    db.refresh(lead)

    logger.info("Website form created lead %s from source %s", lead.id, source)

    return lead, False, extracted
