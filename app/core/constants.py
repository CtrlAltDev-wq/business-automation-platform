from typing import Literal, get_args

# Single source of truth for the sales pipeline stages.
LeadStatus = Literal[
    "NEW",
    "CONTACTED",
    "QUALIFIED",
    "CONVERTED",
    "LOST",
]

LEAD_STATUSES: tuple[str, ...] = get_args(LeadStatus)

# Allowed status changes for the sales pipeline. Terminal states cannot move further.
ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "NEW": {"CONTACTED", "LOST"},
    "CONTACTED": {"QUALIFIED", "LOST"},
    "QUALIFIED": {"CONVERTED", "LOST"},
    "CONVERTED": set(),
    "LOST": set(),
}

# Lifecycle of an outbound integration event (outbox pattern).
EventStatus = Literal["PENDING", "SENT", "FAILED"]

INTEGRATION_EVENT_STATUSES: tuple[str, ...] = get_args(EventStatus)

EVENT_PENDING = "PENDING"
EVENT_SENT = "SENT"
EVENT_FAILED = "FAILED"

# Event types handled by the integration dispatcher.
EVENT_SHEETS_APPEND = "sheets.append_lead"
EVENT_EMAIL_AUTO_REPLY = "email.auto_reply"
EVENT_N8N_LEAD_CREATED = "n8n.lead_created"

INTEGRATION_EVENT_TYPES: tuple[str, ...] = (
    EVENT_SHEETS_APPEND,
    EVENT_EMAIL_AUTO_REPLY,
    EVENT_N8N_LEAD_CREATED,
)
