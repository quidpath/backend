from Authentication.models.logbase import Organisation


class OrganisationService:
    """Fetch or fallback to default organisation."""

    def get_or_default(self, org_id=None):
        if org_id:
            try:
                return Organisation.objects.get(id=org_id)
            except Organisation.DoesNotExist:
                pass
        # fallback
        return Organisation.objects.first() or Organisation.bootstrap_defaults()
