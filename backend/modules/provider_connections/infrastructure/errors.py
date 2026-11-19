"""Safe, actionable failures. Never serialize an upstream exception or request."""


class ProviderAuthenticationError(ValueError):
    def __init__(self, message="F1 sign-in could not be completed. Try browser sign-in in Profile.", *, code="f1_sign_in_failed"):
        super().__init__(message)
        self.code = code


class ProviderUnavailableError(ValueError):
    def __init__(self, message="F1 is temporarily unavailable. Your saved connection remains linked; retry shortly or choose OpenF1.", *, code="f1_temporarily_unavailable"):
        super().__init__(message)
        self.code = code


class ProviderAccessError(ProviderUnavailableError):
    def __init__(self):
        super().__init__("F1 refused access to its timing archive. This can be a subscription, region or server-network restriction; it does not prove your password is wrong. Check your F1 access in Profile, or choose OpenF1.", code="f1_source_access_denied")


def error_detail(error):
    return {"code": error.code, "message": str(error), "action_url": "/profile?connect=f1#f1-connection"}
