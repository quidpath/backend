import logging
from django.core.exceptions import ObjectDoesNotExist
from typing import Optional
from OrgAuth.models import Corporate  # Adjust the import to match your project structure

log = logging.getLogger(__name__)


class CorporateService:
    """
    Directly handles database operations for Corporate objects.
    """

    def get_or_default(self, corporate_id) -> Optional[Corporate]:
        """
        Retrieve a Corporate instance by ID or return None if not found.
        """
        try:
            if not corporate_id:
                log.warning("No corporate ID provided.")
                return None

            corporate = Corporate.objects.filter(id=corporate_id).first()
            if not corporate:
                log.warning(f"Corporate with ID {corporate_id} not found.")
                return None

            return corporate

        except Exception as e:
            log.error(f"Error retrieving corporate with ID {corporate_id}: {str(e)}", exc_info=True)
            return None
