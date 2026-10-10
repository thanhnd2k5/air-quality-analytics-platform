class EmptyMartError(Exception):
    """Raised when a required mart/table has no rows for dashboard queries."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
