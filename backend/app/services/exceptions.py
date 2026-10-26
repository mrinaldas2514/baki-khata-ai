class NotFoundError(Exception):
    """The requested record does not exist (or belongs to another shop)."""


class ConflictError(Exception):
    """The request clashes with existing data."""
