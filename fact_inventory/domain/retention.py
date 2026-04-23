"""Time-based fact retention policy domain objects.

Domain objects expressing retention rules independently of persistence
mechanisms. No framework or ORM imports.

Notes
-----
Domain objects represent core business concepts. By isolating business
rules here, they can be:

- Unit tested without mocking the database or ORM
- Reused across different services and versions
- Updated in response to business requirement changes without touching storage
"""

import datetime

__all__ = [
    "HistoryRetentionPolicy",
    "TimeRetentionPolicy",
]


class TimeRetentionPolicy:
    """Encapsulates time-based fact retention policy as a domain concept.

    Validates retention period is within acceptable bounds and provides
    methods to calculate retention cutoff dates based on time elapsed.

    Notes
    -----
    Keeps facts newer than a specified number of days. Older facts are
    considered expired and eligible for deletion. This approach is suitable
    when regulatory or business requirements mandate holding facts for a
    minimum period.

    Examples
    --------
    >>> policy = TimeRetentionPolicy(days=90)
    >>> cutoff = policy.cutoff_datetime
    >>> facts_to_delete = [f for f in facts if f.updated_at < cutoff]
    """

    MIN_DAYS = 1
    MAX_DAYS = 3650

    def __init__(self, days: int) -> None:
        """Initialize time-based retention policy.

        Parameters
        ----------
        days : int
            Number of days to retain facts.
            Must be between ``MIN_DAYS`` and ``MAX_DAYS``, inclusive.

        Raises
        ------
        ValueError
            If days is outside the valid range defined by ``MIN_DAYS`` and ``MAX_DAYS``.
        """
        if days < self.MIN_DAYS or days > self.MAX_DAYS:
            raise ValueError(  # noqa: TRY003
                f"Retention days must be between {self.MIN_DAYS} "
                f"and {self.MAX_DAYS}, got {days}"
            )
        self._days = days

    @property
    def cutoff_datetime(self) -> datetime.datetime:
        """The cutoff datetime for old facts.

        Returns
        -------
        datetime.datetime
            UTC datetime before which facts should be deleted.
        """
        return datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(
            days=self._days
        )

    def __repr__(self) -> str:
        """Return string representation of the TimeRetentionPolicy instance.

        Returns
        -------
        str
            Formatted string showing the retention policy configuration.
        """
        return f"TimeRetentionPolicy(days={self._days})"


class HistoryRetentionPolicy:
    """Encapsulates per-client fact history retention policy as a domain concept.

    Validates that history retention limits are within acceptable bounds and
    provides access to the maximum number of fact records to keep per client.

    Notes
    -----
    Keeps at most max_entries fact records per client_address, deleting the
    oldest records when a client exceeds this limit. This approach prevents
    unbounded growth of historical records while retaining recent facts for
    each client.

    Examples
    --------
    >>> policy = HistoryRetentionPolicy(max_entries=100)
    >>> max_entries = policy.max_entries
    >>> # Pass policy to repository for deletion
    """

    MIN_ENTRIES = 1
    MAX_ENTRIES = 1000

    def __init__(self, max_entries: int) -> None:
        """Initialize history-based retention policy.

        Parameters
        ----------
        max_entries : int
            Maximum number of fact records to retain per client_address.
            Must be between ``MIN_ENTRIES`` and ``MAX_ENTRIES``, inclusive.

        Raises
        ------
        ValueError
            If max_entries is outside the valid range defined by ``MIN_ENTRIES``
            and ``MAX_ENTRIES``.
        """
        if max_entries < self.MIN_ENTRIES or max_entries > self.MAX_ENTRIES:
            raise ValueError(  # noqa: TRY003
                f"Max entries must be between {self.MIN_ENTRIES} "
                f"and {self.MAX_ENTRIES}, got {max_entries}"
            )
        self._max_entries = max_entries

    @property
    def max_entries(self) -> int:
        """Return the maximum number of fact records retained per client_address.

        Returns
        -------
        int
            Maximum number of fact records to keep per client_address.
        """
        return self._max_entries

    def __repr__(self) -> str:
        """Return string representation of the HistoryRetentionPolicy instance.

        Returns
        -------
        str
            Formatted string showing the retention policy configuration.
        """
        return f"HistoryRetentionPolicy(max_entries={self._max_entries})"
