"""Application-layer exceptions for the fact inventory service.

These exceptions express business rule violations without any HTTP or
framework dependency. The presentation layer is responsible for mapping
them to the appropriate HTTP response codes.
"""

__all__ = ["FactValidationError"]


class FactValidationError(ValueError):
    """Raised when submitted facts fail business validation.

    Used when all three fact categories (system_facts, package_facts,
    local_facts) are empty, which violates the rule that a submission
    must contain at least one category of data.
    """

    pass
