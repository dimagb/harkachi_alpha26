# TODO(lead): заменить импортом из app.errors после B-01.
class ApiErrorException(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details if details is not None else {}
        self.headers = headers
