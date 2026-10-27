import io
import secrets
import sys
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch

import validate_frontend as validation


class FakeTTY(io.StringIO):
    def isatty(self):
        return True


class CredentialFallbackTests(unittest.TestCase):
    def test_missing_qa_file_prompts_for_enabled_roles_without_persisting_secrets(self):
        accounts = {
            "ADMIN": ["admin.one"],
            "VIEWER": ["viewer.one", "viewer.two"],
            "TECHNICIAN": ["tech.one"],
        }
        entered_accounts = iter(["", "viewer.two", ""])
        secret_values = [secrets.token_urlsafe(24) for _ in range(3)]
        entered_secrets = iter(secret_values)
        prompts = []

        result = validation.prompt_role_credentials(
            accounts,
            input_fn=lambda prompt: prompts.append(prompt) or next(entered_accounts),
            getpass_fn=lambda prompt: prompts.append(prompt) or next(entered_secrets),
        )

        self.assertEqual(
            result,
            {
                "admin.one": secret_values[0],
                "viewer.two": secret_values[1],
                "tech.one": secret_values[2],
            },
        )
        self.assertTrue(all("secret" not in prompt.lower() for prompt in prompts))
        self.assertTrue(all(secret not in "\n".join(prompts) for secret in result.values()))

    def test_missing_qa_file_uses_getpass_for_three_enabled_roles_and_writes_nothing(self):
        missing_file = validation.ROOT / "missing-qa-secret-test.json"
        accounts = validation.enabled_accounts_by_role()
        roles = ("ADMIN", "VIEWER", "TECHNICIAN")
        selected_accounts = [accounts[role][0] if len(accounts[role]) > 1 else "" for role in roles]
        secrets_in_memory = ["admin-memory-secret", "viewer-memory-secret", "technician-memory-secret"]
        output = io.StringIO()

        with patch.object(validation, "SECRETS_FILE", missing_file):
            with patch.object(validation.sys, "stdin", FakeTTY()):
                with patch("builtins.input", side_effect=selected_accounts):
                    with patch.object(validation.getpass, "getpass", side_effect=secrets_in_memory):
                        with redirect_stdout(output):
                            result = validation.load_test_credentials()

        expected_accounts = [account or accounts[role][0] for role, account in zip(roles, selected_accounts)]
        self.assertEqual(list(result), expected_accounts)
        self.assertEqual(list(result.values()), secrets_in_memory)
        self.assertFalse(missing_file.exists())
        self.assertTrue(all(secret not in output.getvalue() for secret in secrets_in_memory))

    def test_non_tty_missing_qa_file_explains_setup_without_prompting(self):
        with patch.object(validation, "SECRETS_FILE", validation.ROOT / "missing-qa-secret-test.json"):
            with patch.object(validation.sys, "stdin", io.StringIO("")):
                with self.assertRaises(validation.CheckFailure) as caught:
                    validation.load_test_credentials()

        self.assertIn("npm run preview:credentials", str(caught.exception))
        self.assertIn("交互终端", str(caught.exception))

    def test_main_non_tty_missing_qa_file_exits_before_writing_reports(self):
        output = io.StringIO()
        with patch.object(validation, "SECRETS_FILE", validation.ROOT / "missing-qa-secret-test.json"):
            with patch.object(validation.sys, "stdin", io.StringIO("")):
                with patch.object(validation.sys, "argv", ["validate_frontend.py"]):
                    with redirect_stdout(output):
                        exit_code = validation.main()

        self.assertEqual(exit_code, 2)
        self.assertIn("npm run preview:credentials", output.getvalue())
        self.assertIn("getpass", output.getvalue())
        self.assertEqual(len(validation.VISUAL_REVIEW), 21)


if __name__ == "__main__":
    unittest.main()
