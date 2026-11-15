"""SQLAlchemy models.

Importing this package registers every model, so relationship names declared as
strings (for example "LeadFollowUp") can be resolved in any process, including
the standalone integration worker.
"""

from app.models.integration_event import IntegrationEvent  # noqa: F401
from app.models.lead import Lead  # noqa: F401
from app.models.lead_follow_up import LeadFollowUp  # noqa: F401
from app.models.webhook_idempotency import WebhookIdempotency  # noqa: F401
