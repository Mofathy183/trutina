"""Login throttling use case.

Wraps an ``Authenticator`` and rejects further attempts for one client IP
and email once too many logins have failed within a time window. Depends
only on the login-attempt repository, clock and event-sink contracts, so
it has no storage, web or CLI knowledge. No route or command uses it yet.
"""

from datetime import timedelta

from pydantic import SecretStr
from trutina.authentication.credentials.users import (
    MAX_EMAIL_LENGTH,
    normalize_email,
)
from trutina.authentication.identity import Identity
from trutina.authentication.shared import (
    AuthEvent,
    AuthEventSink,
    Clock,
    NoOpAuthEventSink,
)
from trutina.shared.errors import AppError, ErrorCode

from .attempts import LoginAttemptRepo
from .authenticator import Authenticator

UNKNOWN_CLIENT_IP = "unknown"
"""Stored in place of a client address that could not be determined."""

_THROTTLED_EVENT = "auth.login_throttled"


class ThrottledAuthenticator(Authenticator):
    """Throttles repeated failed logins around another ``Authenticator``.

    Failures are counted per client IP and normalized email together, so
    one address cannot lock out an account and one account is not exposed
    to every address. The count is taken before the inner authenticator
    runs and never looks at whether the account exists, so an unknown
    email is throttled exactly like a known one, and a throttled attempt
    costs no hashing. Throttling is not locking: once the window has
    passed the same pair can sign in again, and other clients were never
    affected.

    Every ``AUTH_INVALID_CREDENTIALS`` from the inner authenticator is one
    failure; this class cannot and does not distinguish the causes. These
    are never counted: other errors, emails longer than
    ``MAX_EMAIL_LENGTH`` (not throttled or stored at all), and throttled
    attempts themselves, so a client that keeps retrying cannot extend its
    own delay.

    The check and the later record are not atomic, so concurrent attempts
    can overshoot the limit by the number in flight. Errors from the
    attempt store propagate unchanged: throttling fails closed.
    """

    def __init__(
        self,
        *,
        inner: Authenticator,
        attempts: LoginAttemptRepo,
        clock: Clock,
        max_failures: int,
        window_seconds: int,
        events: AuthEventSink | None = None,
    ) -> None:
        """Wire the throttle to its collaborators.

        Args:
            inner: The authenticator that checks the credentials.
            attempts: Where failed logins are recorded and counted.
            clock: Supplies timezone-aware UTC times.
            max_failures: Failures within the window at which further
                attempts are throttled.
            window_seconds: Length of the failure window, also reported
                as the retry delay.
            events: Receives the throttled event. Defaults to a sink that
                discards every event.

        Raises:
            ValueError: If ``max_failures`` or ``window_seconds`` is below 1.
        """
        if max_failures < 1:
            raise ValueError("max_failures must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")
        self._inner = inner
        self._attempts = attempts
        self._clock = clock
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._window = timedelta(seconds=window_seconds)
        self._events = events if events is not None else NoOpAuthEventSink()

    async def authenticate(
        self,
        *,
        email: str,
        password: SecretStr,
        client_ip: str | None,
    ) -> Identity:
        """Verify credentials unless this client and email are throttled.

        Args:
            email: The login email, as typed.
            password: The plaintext password, as typed.
            client_ip: Resolved client address, or ``None`` if unknown.

        Returns:
            The authenticated identity from the inner authenticator.

        Raises:
            AppError: AUTH_THROTTLED when the failures for this IP and
                email within the window have reached the limit, with
                ``retry_after_seconds`` in its context. Everything the
                inner authenticator raises, including
                AUTH_INVALID_CREDENTIALS, propagates unchanged after its
                failure is recorded. STORAGE_UNAVAILABLE or
                STORAGE_TIMEOUT from the attempt store propagate unchanged.
        """
        key = normalize_email(email)
        if len(key) > MAX_EMAIL_LENGTH:
            return await self._inner.authenticate(
                email=email, password=password, client_ip=client_ip
            )

        ip = client_ip or UNKNOWN_CLIENT_IP
        failures = await self._attempts.count_failures(
            ip=ip, email=key, since=self._clock.now() - self._window
        )
        if failures >= self._max_failures:
            self._events.emit(
                AuthEvent(
                    name=_THROTTLED_EVENT,
                    context={"retry_after_seconds": str(self._window_seconds)},
                )
            )
            raise AppError.throttled(self._window_seconds)

        try:
            identity = await self._inner.authenticate(
                email=email, password=password, client_ip=client_ip
            )
        except AppError as error:
            if error.code is ErrorCode.AUTH_INVALID_CREDENTIALS:
                failed_at = self._clock.now()
                await self._attempts.record_failure(ip=ip, email=key, at=failed_at)
                await self._attempts.purge_before(failed_at - self._window)
            raise

        if failures:
            await self._attempts.clear(ip=ip, email=key)
        return identity
