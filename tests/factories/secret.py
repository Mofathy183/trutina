"""Test-only credential model for secret-safety tests (M2.1).

No real credential schema exists until M2.5/M3.7, so the API and CLI
proofs validate against this probe instead. It mirrors the convention
real credential models must follow: `SecretStr` for the credential and
`hide_input_in_errors=True` so `str(ValidationError)` never echoes input.

Defaults: the payload omits `email` and sends `SECRET_SENTINEL` as both
`password` and `new_password`, so one validation produces a `missing`
error (whose Pydantic input is the whole payload) and a
`string_too_short` error on a credential-named field.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr

SECRET_SENTINEL = "S3NTINEL-must-never-be-logged"


class SecretProbe(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    email: str
    password: SecretStr
    new_password: str = Field(min_length=64)


def make_secret_probe_payload(**overrides: Any) -> dict[str, Any]:
    """Build an invalid probe payload that carries the sentinel twice."""
    payload: dict[str, Any] = {
        "password": SECRET_SENTINEL,
        "new_password": SECRET_SENTINEL,
    }
    payload.update(overrides)
    return payload
