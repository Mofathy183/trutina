import pytest
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from trutina.cli.shell.completion import build_completer


def _complete(completer, text: str) -> set[str]:
    return {c.text for c in completer.get_completions(Document(text), CompleteEvent())}


@pytest.mark.unit
class TestBuildCompleter:
    def test_completes_top_level_group_names(self):
        completer = build_completer()

        assert _complete(completer, "ac") == {"account"}
        assert _complete(completer, "jour") == {"journal"}
        assert _complete(completer, "post") == {"posting"}

    def test_completes_account_subcommands(self):
        completer = build_completer()

        assert _complete(completer, "account ") == {
            "create",
            "get",
            "list",
            "update",
            "delete",
            "help",
        }

    def test_completes_journal_subcommands(self):
        completer = build_completer()

        assert _complete(completer, "journal ") == {
            "create",
            "get",
            "list",
            "help",
        }

    def test_completes_posting_subcommands(self):
        completer = build_completer()

        assert _complete(completer, "posting ") == {
            "post",
            "get-by-account",
            "get-by-journal",
            "help",
        }


@pytest.mark.unit
class TestSlashPrefixCompletion:
    def test_slash_prefixed_group_completion_matches_bare(self):
        completer = build_completer()

        assert _complete(completer, "ac") == _complete(completer, "/ac")

    def test_slash_prefixed_subcommand_completion_matches_bare(self):
        completer = build_completer()

        assert _complete(completer, "account ") == _complete(completer, "/account ")


@pytest.mark.unit
class TestCompletionDescriptions:
    def test_group_completions_carry_description(self):
        completer = build_completer()
        completions = list(completer.get_completions(Document("ac"), CompleteEvent()))

        assert completions[0].display_meta_text == "Manage the chart of accounts."

    def test_subcommand_completions_carry_description(self):
        completer = build_completer()
        completions = list(
            completer.get_completions(Document("posting "), CompleteEvent())
        )

        by_name = {c.text: c.display_meta_text for c in completions}
        assert by_name["post"].startswith("Post a journal entry")


@pytest.mark.unit
class TestBuiltinCompletion:
    def test_completes_exit_and_quit(self):
        completer = build_completer()
        assert _complete(completer, "ex") == {"exit"}

    def test_builtin_completions_carry_description(self):
        completer = build_completer()
        completions = list(completer.get_completions(Document("exi"), CompleteEvent()))
        assert completions[0].display_meta_text == "Leave the interactive shell."

    def test_slash_prefixed_builtin_matches_bare(self):
        completer = build_completer()
        assert _complete(completer, "exit") == _complete(completer, "/exit")

    def test_completes_help(self):
        completer = build_completer()
        assert _complete(completer, "he") == {"help"}

    def test_help_completion_carries_description(self):
        completer = build_completer()
        completions = list(completer.get_completions(Document("hel"), CompleteEvent()))
        assert completions[0].display_meta_text == (
            "Show available commands, or help for one command."
        )

    def test_slash_prefixed_help_matches_bare(self):
        completer = build_completer()
        assert _complete(completer, "help") == _complete(completer, "/help")


@pytest.mark.unit
class TestTrailingHelpCompletion:
    """`<command...> help` -- offered alongside real subcommands so the
    shorthand shell.py accepts is discoverable without memorizing it.
    """

    def test_offered_after_a_group(self):
        completer = build_completer()

        assert "help" in _complete(completer, "account ")

    def test_offered_after_a_group_and_subcommand(self):
        completer = build_completer()

        assert _complete(completer, "journal create ") == {"help"}

    def test_narrows_like_any_other_completion(self):
        completer = build_completer()

        assert _complete(completer, "account h") == {"help"}
        assert _complete(completer, "account x") == set()

    def test_carries_a_contextual_description(self):
        completer = build_completer()
        completions = list(
            completer.get_completions(Document("journal create h"), CompleteEvent())
        )

        assert completions[0].display_meta_text == "Show help for journal create."

    def test_not_offered_after_a_builtin(self):
        completer = build_completer()

        assert _complete(completer, "exit ") == set()

    def test_slash_prefixed_matches_bare(self):
        completer = build_completer()

        assert _complete(completer, "account list ") == _complete(
            completer, "/account list "
        )


@pytest.mark.unit
class TestLeadingHelpTargetCompletion:
    """`help <target...>` -- the target completes like typing it
    directly, minus the builtins and minus a second trailing `help`.
    """

    def test_offers_real_commands_as_targets(self):
        completer = build_completer()

        assert _complete(completer, "help ") == {
            "account",
            "journal",
            "posting",
            "trial-balance",
        }

    def test_excludes_builtins_from_targets(self):
        completer = build_completer()

        assert "exit" not in _complete(completer, "help ")
        assert "help" not in _complete(completer, "help ")

    def test_completes_subcommand_targets(self):
        completer = build_completer()

        assert _complete(completer, "help account ") == {
            "create",
            "get",
            "list",
            "update",
            "delete",
        }

    def test_does_not_offer_a_second_trailing_help(self):
        completer = build_completer()

        assert "help" not in _complete(completer, "help account ")
