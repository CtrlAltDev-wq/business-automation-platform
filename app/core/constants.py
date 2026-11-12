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
