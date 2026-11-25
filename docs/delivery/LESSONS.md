# Lessons

## Index

| ID | Part | Source | Lead |
|---|---|---|---|
| L-01 | process | delivery split | The agent kept re-reading from line 1 |
| L-02 | process | delivery split | One line of the source belonged to no slice |
| L-03 | process | delivery split | Wrong line count, and a PowerShell parser error |
| L-04 | process | delivery split | A label file would have become a broken workflow |
| L-05 | process | delivery split | Resuming an OpenCode session failed with a provider error |
| L-06 | process | delivery split | A model's claim that its work was checked cannot be trusted by… |
| L-07 | process | delivery split | GLM-5.3-Flash (Nvidia) was slow and failed during sessions |
| L-08 | process | delivery split | Run 2 had no script to verify it, so the agent checked… |
| L-09 | process | delivery split | Run 2 was committed before any script had checked it |
| L-10 | process | delivery split | The agent edited the files to satisfy a failing check that was… |
| L-11 | process | delivery split | A passing script did not prove the file was complete |
| L-12 | process | delivery split | The agent wrote a card's status badge into the Labels field |
| L-13 | process | delivery split | The agent wrote `Package` and `Decisions / Gaps` lines that the HTML… |
| L-14 | process | delivery split | One run needed four rounds of follow-up fixes, each a small defect… |
| L-15 | process | delivery split | Defects were discovered one at a time by reading diffs |
| L-16 | process | delivery split | A mechanical copy was given to a model that varied the layout… |
| L-17 | process | delivery split | A raw `<code >msg</code >` tag reached `CHANGELOG.md` and the checker still… |
| L-18 | process | delivery split | A correct file looked broken in review (lines cut mid-word, text out… |
| L-19 | process | delivery split | The agent reported `verify-run1.ps1` as missing, so the regression check was not… |
| L-20 | process | delivery split | A committed file disagreed with a ruling made later (the `DECISIONS.md` index… |
| L-21 | process | delivery split | The branch compare showed 10 files while the plan said 9 |
| L-22 | process | delivery split | The agent's final report said it had created `label.yml` in Run 6a |
| L-23 | process | delivery split | `check_status.py` failed with 0 ticket rows parsed after `STATUS.md` was committed, although… |
| L-24 | process | delivery split | The agent reported a failing regression (`check_status.py`) as pre-existing, and a failing… |
| L-25 | process | delivery split | The padded positive control failed although the checker was right |
| L-26 | rule | Trutina_Auth_Ticket_Workflow_v3_12.md | `ty` does not see every call through untyped fixtures or `app.state`. For… |
| L-27 | rule | Trutina_Auth_Ticket_Workflow_v3_12.md | A model change without its migration can cause misleading integration failures. Run… |
| L-28 | rule | Trutina_Auth_Ticket_Workflow_v3_12.md | A unit test can pass while reaching a developer's PostgreSQL. Inject fakes… |
| L-29 | rule | Trutina_Auth_Ticket_Workflow_v3_12.md | Test migration downgrade/upgrade round trips while restoring the original head in a… |
| L-30 | rule | Trutina_Auth_Ticket_Workflow_v3_12.md | Keep credentials, password hashes, access/refresh tokens, and secret values out of logs,… |
| L-31 | rule | Trutina_Auth_Ticket_Workflow_v3_12.md | Do not use wall-clock timing assertions for dummy password verification or concurrency… |
| L-32 | premise | M2.3 Result | `_response_headers` took only the code, so it gained a context argument; the… |
| L-33 | premise | M2.5 Result | the ticket's "must not trim" wording was revised, so passwords are trimmed… |
| L-34 | premise | M2.6 Result | the ticket's "times from `Clock`" needed no clock because nothing in M2.6… |
| L-35 | premise | M2.7 Result | the frozen `LoginAttemptRepo` has no oldest-failure query, so the retry delay is… |
| L-36 | premise | M2.8 Result | criteria needing the real structlog pipeline or a real route cannot close… |
| L-37 | premise | M3.1 Result | the ticket's claim that `trutina-authentication` lacked `trutina-shared` was wrong, since its `pyproject.toml`… |
| L-38 | premise | M3.3 Result | the card said the lifetime comes from the kind, a touch writes… |
| L-39 | premise | M3.4 Result | the card said the purge on creation would be bounded and that… |

## Process lessons

### L-01

part: process
source: delivery split
symptom: The agent kept re-reading from line 1
cause: OpenCode Read tool (1.18.30) intermittently ignored `offset`; reads are also capped at about 50 KB
prevention: Cut files into slices of at most 45 KB and read each whole; check the footer

### L-02

part: process
source: delivery split
symptom: One line of the source belonged to no slice
cause: A slice script used `start + 799` and the next start `+ 1`
prevention: Generate contiguous slices and check that the lines in the slices equal the total

### L-03

part: process
source: delivery split
symptom: Wrong line count, and a PowerShell parser error
cause: `Measure-Object -Line` skips empty lines; a nested `@(@(...))` one-liner had unbalanced parentheses
prevention: Use `(Get-Content).Count`; put multi-line logic in a script file; use `-Encoding utf8`

### L-04

part: process
source: delivery split
symptom: A label file would have become a broken workflow
cause: Any file in `.github/workflows/` is treated as an Actions workflow
prevention: Keep label definitions at `.github/labels.yml`

### L-05

part: process
source: delivery split
symptom: Resuming an OpenCode session failed with a provider error
cause: Provider or session state problem (cause not diagnosed)
prevention: Keep a handoff file; start a fresh session from it

### L-06

part: process
source: delivery split
symptom: A model's claim that its work was checked cannot be trusted by itself
cause: The check existed only in the session's context
prevention: Verify output with a script (counts and text fidelity) before committing

### L-07

part: process
source: delivery split
symptom: GLM-5.3-Flash (Nvidia) was slow and failed during sessions
cause: Provider speed and reliability (cause not diagnosed)
prevention: Pin a model only after one real run; keep a handoff file; fallback order in decision 20

### L-08

part: process
source: delivery split
symptom: Run 2 had no script to verify it, so the agent checked its own output by hand
cause: The verify script covered only `gates` and `decisions`
prevention: Add the check mode for a run's file type before starting the run

### L-09

part: process
source: delivery split
symptom: Run 2 was committed before any script had checked it
cause: The verify script had no milestone mode, and the commit came first
prevention: Do not commit a run until its verify script prints PASS

### L-10

part: process
source: delivery split
symptom: The agent edited the files to satisfy a failing check that was itself wrong
cause: The verify script counted every `### M…` heading as a card
prevention: When a check fails, confirm the checker is right before changing the content; the card-heading pattern now requires a dotted ticket ID

### L-11

part: process
source: delivery split
symptom: A passing script did not prove the file was complete
cause: The script checked card and narrative text only, not WP headings or milestone paragraphs
prevention: Check the structure the template requires, not just the text that was copied; `-Delivery` covers the delivery-plan section

### L-12

part: process
source: delivery split
symptom: The agent wrote a card's status badge into the Labels field
cause: The script checks that source text is present, not that extra text is absent, and it strips the badge before comparing
prevention: Add an absence check (no status words or unstated fields in cards) to the verify script

### L-13

part: process
source: delivery split
symptom: The agent wrote `Package` and `Decisions / Gaps` lines that the HTML never states
cause: The card template has those fields, and the agent filled them by inference instead of omitting them
prevention: State in the prompt which card fields to omit; check that every card line maps to a field in the source card

### L-14

part: process
source: delivery split
symptom: One run needed four rounds of follow-up fixes, each a small defect found at a different time
cause: Acceptance criteria were written after the run, not before. The prompt gave rules but no layout. The checker proved presence only, so extras, heading levels and missing sections passed. The checker was never tested against a bad file, and the agent was allowed to verify by hand
prevention: Run readiness gate (decision 26): complete checker (presence, absence, structure) tested negatively before the run; prompt with layout, allowed fields, counts and verify command; loop until PASS inside the session; review the staged diff; one commit per run

### L-15

part: process
source: delivery split
symptom: Defects were discovered one at a time by reading diffs
cause: No list of defect classes existed to check for up front
prevention: Keep a defect-class list in the script. Every defect found at review becomes a check (heading level, unstated field, status word, missing section, duplicate card, invented number) before the next run

### L-16

part: process
source: delivery split
symptom: A mechanical copy was given to a model that varied the layout each run
cause: A regular transform was treated as a language task
prevention: Prefer a converter script for mechanical sections and keep the model for judgment (decision 27)

### L-17

part: process
source: delivery split
symptom: A raw `<code >msg</code >` tag reached `CHANGELOG.md` and the checker still printed PASS
cause: The source split the tag across lines (`<code` newline `>`), the converter's regex did not match it, and the checker used the same normaliser, so both agreed on the wrong text
prevention: The checker parses the source with its own code and has an explicit no-raw-HTML check; the converter accepts whitespace inside tags; a negative test seeds a raw tag

### L-18

part: process
source: delivery split
symptom: A correct file looked broken in review (lines cut mid-word, text out of order)
cause: The staged diff was read in a pager and a narrow terminal, which wrapped and cut lines
prevention: Write the staged diff to a file (`git --no-pager diff --staged > G:\trutina-plan\staged.diff`) and review that; confirm doubtful text with `grep -c` or a PowerShell count

### L-19

part: process
source: delivery split
symptom: The agent reported `verify-run1.ps1` as missing, so the regression check was not run the first time
cause: The script lives in `G:\trutina-plan\`, outside the repo, and the agent searched the repo only
prevention: Give every script by absolute path in the run prompt; the owner re-runs the regression checks

### L-20

part: process
source: delivery split
symptom: A committed file disagreed with a ruling made later (the `DECISIONS.md` index said Active for LD5, D10 and D35; decision 21 says Partly superseded)
cause: The verify script never checked the index column, and the rulings were only in prose
prevention: When a ruling is made, add a check that reads it from a rulings table kept in the script; fix the committed file in its own small run (Run 1b)

### L-21

part: process
source: delivery split
symptom: The branch compare showed 10 files while the plan said 9
cause: The expected-file list in the plan left out `CHANGELOG.md`; the repo was right
prevention: Each Run Pack lists the expected files, and the owner compares them with `git diff --stat main...HEAD` before the push

### L-22

part: process
source: delivery split
symptom: The agent's final report said it had created `label.yml` in Run 6a
cause: The agent reported the file's origin without evidence; the file was an untracked file that existed before the run
prevention: Read `git status --short` and the staged diff, not the agent's file list (same root as L-06)

### L-23

part: process
source: delivery split
symptom: `check_status.py` failed with 0 ticket rows parsed after `STATUS.md` was committed, although it had passed on the reviewed file
cause: Prettier format-on-save for Markdown in the owner's editor padded the table cells and separators after review and before the commit
prevention: Checkers accept padded tables (decision 40); keep the formatter off generated delivery files; `git show HEAD:<file>` and the worktree file tell which side changed

### L-24

part: process
source: delivery split
symptom: The agent reported a failing regression (`check_status.py`) as pre-existing, and a failing padded positive control as a test infrastructure issue, and its final report said all tests passed
cause: The agent's own report is not evidence, and the prompt did not say a failing regression stops the run
prevention: Any failing check stops the run and the agent must show evidence for which side is wrong; the test script exits non-zero and prints a single `ALL TESTS PASSED` line only when everything behaved as expected; the owner re-runs and the assistant reads raw output

### L-25

part: process
source: delivery split
symptom: The padded positive control failed although the checker was right
cause: The test's own table generator did not escape `|` in cell text, so `str | None` (item 88) split a row into 7 cells
prevention: Positive controls use the real file and its hardest rows (an escaped pipe, a long cell); a generator splits and pads cells respecting escaped pipes

## Carried-over rules

### L-26

part: rule
source: Trutina_Auth_Ticket_Workflow_v3_12.md
rule: `ty` does not see every call through untyped fixtures or `app.state`. For a changed repository/service contract, `git grep` every implementer and caller and run the relevant integration lanes.

### L-27

part: rule
source: Trutina_Auth_Ticket_Workflow_v3_12.md
rule: A model change without its migration can cause misleading integration failures. Run `alembic check` locally for every migration ticket; it is not yet in CI or `tools/pre-push.sh`.

### L-28

part: rule
source: Trutina_Auth_Ticket_Workflow_v3_12.md
rule: A unit test can pass while reaching a developer's PostgreSQL. Inject fakes in unit tests and verify the unit lane in CI.

### L-29

part: rule
source: Trutina_Auth_Ticket_Workflow_v3_12.md
rule: Test migration downgrade/upgrade round trips while restoring the original head in a `finally` block.

### L-30

part: rule
source: Trutina_Auth_Ticket_Workflow_v3_12.md
rule: Keep credentials, password hashes, access/refresh tokens, and secret values out of logs, error contexts, API responses, CLI output, and auth events as required by the plan.

### L-31

part: rule
source: Trutina_Auth_Ticket_Workflow_v3_12.md
rule: Do not use wall-clock timing assertions for dummy password verification or concurrency safeguards; test the intended calls/state transitions directly.

## Plan premise checks

### L-32

part: premise
source: M2.3 Result
premise check: `_response_headers` took only the code, so it gained a context argument; the CLI formatter lets a `field` context key override `FIELD_LABELS`, recorded as a constraint on M2.6.

### L-33

part: premise
source: M2.5 Result
premise check: the ticket's "must not trim" wording was revised, so passwords are trimmed at the edges after NFKC (D28); no existing `ErrorCode` fit a malformed email, so `INVALID_EMAIL` was added; a Pydantic validator would have downgraded it to `UNKNOWN_ERROR`, so the checks live in the service.

### L-34

part: premise
source: M2.6 Result
premise check: the ticket's "times from `Clock`" needed no clock because nothing in M2.6 uses time; `hash()` is async, so the dummy hash comes from `create()`.

### L-35

part: premise
source: M2.7 Result
premise check: the frozen `LoginAttemptRepo` has no oldest-failure query, so the retry delay is the window length; the 11th and 12th commits (docs sweep and the clear-only-its-own-pair test) were added after review.

### L-36

part: premise
source: M2.8 Result
premise check: criteria needing the real structlog pipeline or a real route cannot close at this layer.

### L-37

part: premise
source: M3.1 Result
premise check: the ticket's claim that `trutina-authentication` lacked `trutina-shared` was wrong, since its `pyproject.toml` already declares it; the folder was renamed `sessions/`, reversing the ticket's recommendation to keep `tokens/`.

### L-38

part: premise
source: M3.3 Result
premise check: the card said the lifetime comes from the kind, a touch writes only when the interval has passed, and a bounded purge runs when a session is created. The contract puts the first two in the service, and its `create` takes no cutoff while `purge_before` has no batch limit, so the purge on creation moves to M3.4.

### L-39

part: premise
source: M3.4 Result
premise check: the card said the purge on creation would be bounded and that a limit would be decided here, but the frozen `purge_before` has no limit and unfreezing the contract was out of scope, so the purge is one unbounded call made before the insert (D38); ADR 0002 section 5 was amended to match (per the diff stat). The card said the login runs only after `ThrottledAuthenticator` succeeds; the service takes any `Authenticator` and relies on the composition root to pass the throttled one. The revoke-all event kind `"all"` was chosen during implementation and is not in ADR 0002's list.
