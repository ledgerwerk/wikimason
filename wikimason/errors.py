class WikiMasonError(Exception):
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class UsageError(WikiMasonError):
    def __init__(self, message: str):
        super().__init__(message, exit_code=2)
