import logging

log = logging.getLogger(__name__)

class SMSService:
    """
    Placeholder for future SMS provider integrations.
    """
    def send_sms(self, destination: str, message: str):
        log.info(f"[SMSService] Sending SMS to {destination}: {message}")
        # TODO: Integrate actual SMS provider
        return {"status": "success", "code": "200.001.001"}
