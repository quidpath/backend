from Authentication.models.logbase import State


class StateService:
    """Convenient access to system states."""

    def get_active(self):
        return State.objects.get(name="Active")

    def get_completed(self):
        return State.objects.get(name="Completed")

    def get_failed(self):
        return State.objects.get(name="Failed")

    def get_pending(self):
        return State.objects.get(name="Pending")
