# core/exceptions/custom_exceptions.py
class CustomException(Exception):
    pass

class InvalidInputError(CustomException):
    def __init__(self, message="Invalid input provided"):
        self.message = message
        super().__init__(self.message)

class NotFoundError(CustomException):
    def __init__(self, message="Resource not found"):
        self.message = message
        super().__init__(self.message)

class UnauthorizedError(CustomException):
    def __init__(self, message="Unauthorized access"):
        self.message = message
        super().__init__(self.message)

class ForbiddenError(CustomException):
    def __init__(self, message="Forbidden access"):
        self.message = message
        super().__init__(self.message)

class InternalServerError(CustomException):
    def __init__(self, message="Internal server error"):
        self.message = message
        super().__init__(self.message)

class BadRequestError(CustomException):
    def __init__(self, message="Bad request"):
        self.message = message
        super().__init__(self.message)

class ConflictError(CustomException):
    def __init__(self, message="Conflict occurred"):
        self.message = message
        super().__init__(self.message)

class UnprocessableEntityError(CustomException):
    def __init__(self, message="Unprocessable entity"):
        self.message = message
        super().__init__(self.message)

class ServiceUnavailableError(CustomException):
    def __init__(self, message="Service unavailable"):
        self.message = message
        super().__init__(self.message)

class GatewayTimeoutError(CustomException):
    def __init__(self, message="Gateway timeout"):
        self.message = message
        super().__init__(self.message)

class TooManyRequestsError(CustomException):
    def __init__(self, message="Too many requests"):
        self.message = message
        super().__init__(self.message)

class MethodNotAllowedError(CustomException):
    def __init__(self, message="Method not allowed"):
        self.message = message
        super().__init__(self.message)

class NotAcceptableError(CustomException):
    def __init__(self, message="Not acceptable"):
        self.message = message
        super().__init__(self.message)

class PreconditionFailedError(CustomException):
    def __init__(self, message="Precondition failed"):
        self.message = message
        super().__init__(self.message)

class RequestTimeoutError(CustomException):
    def __init__(self, message="Request timeout"):
        self.message = message
        super().__init__(self.message)

class RequestEntityTooLargeError(CustomException):
    def __init__(self, message="Request entity too large"):
        self.message = message
        super().__init__(self.message)

class RequestURITooLongError(CustomException):
    def __init__(self, message="Request URI too long"):
        self.message = message
        super().__init__(self.message)

class UnsupportedMediaTypeError(CustomException):
    def __init__(self, message="Unsupported media type"):
        self.message = message
        super().__init__(self.message)

class LengthRequiredError(CustomException):
    def __init__(self, message="Length required"):
        self.message = message
        super().__init__(self.message)

class ExpectationFailedError(CustomException):
    def __init__(self, message="Expectation failed"):
        self.message = message
        super().__init__(self.message)

class MisdirectedRequestError(CustomException):
    def __init__(self, message="Misdirected request"):
        self.message = message
        super().__init__(self.message)

class NetworkAuthenticationRequiredError(CustomException):
    def __init__(self, message="Network authentication required"):
        self.message = message
        super().__init__(self.message)

class NotExtendedError(CustomException):
    def __init__(self, message="Not extended"):
        self.message = message
        super().__init__(self.message)

