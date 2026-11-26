# Status

## Tickets

| Ticket | Status | Needs | Issue | PR | Merge | Branch |
|---|---|---|---|---|---|---|
| M1b.1 | Done | none; implementation is complete | #55 | #56 | `fb541c2` | `feat/55-postgres-users-store` |
| M1c.1 | Done | M1b.1 (not required; ran in parallel) | #57 | #61 | `d433a5a` | `feat/57-account-write-actor` |
| M1c.2 | Done | M1c.1 (done) | #58 | #63 | `b76dcd3` | `feat/58-account-audit-events` |
| M2.0 | Done | — | #64 | #65 | `0ab8974` | `feat/64-redact-credential-log-keys` |
| M2.1 | Done | — | #66 | #67 | `a348d50` | `feat/66-secret-safe-validation-errors` |
| M2.3 | Done | — | #68 | #69 | `919c131` | `feat/68-auth-error-codes` |
| M2.2 | Done | M0b (done) | #70 | #71 | `42b2dd8` | `feat/70-password-hasher` |
| M2.4 | Done | M1b.1; ran in parallel with M2.2 | #72 | #73 | `5bb169e` | `feat/72-login-attempt-storage` |
| M2.5 | Done | M2.1, M2.2 | #74 | #75 | `7bce020` | `feat/74-register-use-case` |
| M2.6 | Done | M2.2, M2.3, M2.5 (done) | #76 | #77 | `b0c1f9c` | `feat/76-login-verification` |
| M2.7 | Done | M2.4, M2.6 (done) | #78 | #79 | `92a6982` | `feat/78-login-throttling` |
| M2.8 | Done | M2.0 to M2.7 (done) | #80 | #81 | `fe4928e` | `test/80-credentials-integration-verification` |
| M3.0 | Done | owner: you (approved 2026-10-30) | #82 | #83 | `acbdba4` | `chore/82-token-key-rotation-adr` |
| M3.1 | Done | M3.0 (done); ADR 0002 accepted by the owner | #86 | #87 | `8c53487` | `feat/86-session-contracts-and-settings` |
| M3.2 | Removed | — | — | — | — | — |
| M3.3 | Done | M3.1 (done); M4c.1 (not done, so the pool test builds its own one-connection pool) | #88 | #89 | `62c7210` | `feat/88-postgres-session-store` |
| M3.4 | Done | M3.3 (done), M2.8 (done) | #90 | #91 | `710539a` | `feat/90-session-service` |
| M3.5 | Not started | M3.3 (done); M3.4 is done, so it can start now | — | — | — | — |
| M3.6 | Not started | M3.4 (done), M3.5 | — | — | — | — |
| M3.7 | Not started | M3.6, M2.7, M2.1 | — | — | — | — |
| M3.8 | Not started | M3.7 | — | — | — | — |
| M4a.1 | Not started | M3.7 | — | — | — | — |
| M4a.2 | Not started | M4a.1 | — | — | — | — |
| M4a.3 | Not started | M3.6 | — | — | — | — |
| M4b.1 | Not started | M4a.2, M1c.2 | — | — | — | — |
| M4c.1 | Not started | owner: you; may start now. Pulled forward by ADR 0001: it also sizes the session-lookup pool for M3.3 | — | — | — | — |
| M4c.2 | Not started | M4b.1, M4c.1 | — | — | — | — |
| M4.5.1 | Not started | M2.8 (done), M3.3 (done), M3.4 (done; D1 settled by ADR 0001) | — | — | — | — |
| M4.5.2 | Not started | M4.5.1 | — | — | — | — |
| M4.5.3 | Not started | M4.5.2, M1c.1 | — | — | — | — |
| M5.0 | Not started | M4a.3 | — | — | — | — |
| M5.6 | Not started | M5.0 | — | — | — | — |
| M5.1 | Not started | M5.0 | — | — | — | — |
| M5.2 | Not started | M5.1 | — | — | — | — |
| M5.3 | Not started | M5.2, M4a.3 | — | — | — | — |
| M5.4 | Not started | M5.2 | — | — | — | — |
| M5.5 | Not started | M5.2 | — | — | — | — |
| M5.7 | Not started | M5.3 to M5.6, M4c.2, M4.5.3 | — | — | — | — |

## Work without cards

| Ticket | Status | Needs | Issue | PR | Merge | Branch |
|---|---|---|---|---|---|---|
| M0a-A | Done | — | #41 | #44 | Not recorded | Not recorded |
| M0a-B | Done | — | #42 | Not recorded | Not recorded | `fix/trial-balance-one-shot-dispatch` |
| M0a-C | Done | — | #43 | #46 | Not recorded | Not recorded |
| M0b-A | Done | — | #48 | #49 | Not recorded | Not recorded |
| M0b-B | Done | — | #47 | #50 | Not recorded | Not recorded |
| M0b-C | Done | — | #47 | #50 | Not recorded | Not recorded |
| M1a ticket 1 | Done | — | #51 | #53 | `555430e` | Not recorded |
| M1a ticket 2 | Done | — | #52 | #54 | `e9dd41b` | `feat/persist-created-by` |
