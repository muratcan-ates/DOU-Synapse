from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.workflow_policy_check import inspect_workflows

PINNED_CHECKOUT = "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5"


class WorkflowPolicyCheckTests(unittest.TestCase):
    def _repo(
        self,
        body: str,
        *,
        local_action: str | None = None,
    ) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        directory = root / ".github" / "workflows"
        directory.mkdir(parents=True)
        workflow = (
            body
            if body.lstrip().startswith(("on:", "'on':", '"on":'))
            else f"on: push\n{body}"
        )
        (directory / "ci.yml").write_text(workflow, encoding="utf-8")
        if local_action is not None:
            action_directory = root / ".github" / "actions" / "local"
            action_directory.mkdir(parents=True)
            (action_directory / "action.yml").write_text(
                local_action,
                encoding="utf-8",
            )
        return root

    def test_accepts_sha_pinned_remote_and_local_action(self) -> None:
        root = self._repo(
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            f"      - uses: {PINNED_CHECKOUT}\n"
            "      - uses: ./.github/actions/local\n",
            local_action=(
                "name: local\n"
                "runs:\n"
                "  using: composite\n"
                "  steps:\n"
                "    - run: echo ok\n"
                "      shell: bash\n"
            ),
        )
        self.assertEqual(inspect_workflows(root), [])

    def test_rejects_mutable_action_tag(self) -> None:
        root = self._repo("jobs: {test: {steps: [{uses: actions/checkout@v4}]}}\n")
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["MUTABLE_ACTION_REF"],
        )

    def test_rejects_pull_request_target_mapping(self) -> None:
        root = self._repo("on:\n  pull_request_target:\n")
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["UNSAFE_TRIGGER"],
        )

    def test_rejects_quoted_pull_request_target(self) -> None:
        root = self._repo("'on':\n  \"pull_request_target\":\n")
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["UNSAFE_TRIGGER"],
        )

    def test_rejects_inline_pull_request_target_list(self) -> None:
        root = self._repo('on: [push, "pull_request_target"]\n')
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["UNSAFE_TRIGGER"],
        )

    def test_rejects_inline_pull_request_target_map(self) -> None:
        root = self._repo("on: {push: {}, pull_request_target: {}}\n")
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["UNSAFE_TRIGGER"],
        )

    def test_anchor_and_alias_cannot_hide_mutable_action(self) -> None:
        root = self._repo(
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            "      - &unsafe {uses: actions/cache@v4}\n"
            "      - *unsafe\n"
        )
        violations = inspect_workflows(root)
        self.assertGreaterEqual(
            [item.code for item in violations].count("MUTABLE_ACTION_REF"),
            1,
        )

    def test_aliased_trigger_is_evaluated_structurally(self) -> None:
        root = self._repo(
            "'on': &events [push, pull_request_target]\n"
            "name: unsafe\n"
            "x-events: *events\n"
        )
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["UNSAFE_TRIGGER"],
        )

    def test_does_not_treat_run_text_as_a_trigger(self) -> None:
        root = self._repo(
            "jobs:\n  test:\n    steps:\n      - run: 'echo pull_request_target:'\n"
        )
        self.assertEqual(inspect_workflows(root), [])

    def test_recursively_audits_nested_local_actions(self) -> None:
        root = self._repo(
            "jobs:\n  test:\n    steps:\n      - uses: ./.github/actions/local\n",
            local_action=(
                "name: outer\n"
                "runs:\n"
                "  using: composite\n"
                "  steps:\n"
                "    - uses: ./.github/actions/nested\n"
            ),
        )
        nested = root / ".github" / "actions" / "nested"
        nested.mkdir(parents=True)
        (nested / "action.yml").write_text(
            "name: nested\n"
            "runs:\n"
            "  using: composite\n"
            "  steps:\n"
            "    - uses: actions/cache@v4\n",
            encoding="utf-8",
        )
        self.assertEqual(
            [(item.code, item.path.as_posix()) for item in inspect_workflows(root)],
            [("MUTABLE_ACTION_REF", ".github/actions/nested/action.yml")],
        )

    def test_rejects_nested_missing_local_action(self) -> None:
        root = self._repo(
            "jobs:\n  test:\n    steps:\n      - uses: ./.github/actions/local\n",
            local_action=(
                "name: outer\n"
                "runs:\n"
                "  using: composite\n"
                "  steps:\n"
                "    - uses: ./.github/actions/missing\n"
            ),
        )
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["LOCAL_ACTION_UNRESOLVED"],
        )

    def test_rejects_non_scalar_action_reference(self) -> None:
        root = self._repo("jobs: {test: {steps: [{uses: [not, scalar]}]}}\n")
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["INVALID_ACTION_REF"],
        )

    def test_rejects_duplicate_yaml_keys(self) -> None:
        root = self._repo(
            "on: push\n"
            "jobs:\n"
            "  test:\n"
            "    steps:\n"
            f"      - uses: {PINNED_CHECKOUT}\n"
            "        uses: actions/checkout@v4\n"
        )
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["INVALID_YAML"],
        )

    def test_rejects_invalid_yaml(self) -> None:
        root = self._repo("on: [push\n")
        self.assertEqual(
            [item.code for item in inspect_workflows(root)],
            ["INVALID_YAML"],
        )


if __name__ == "__main__":
    unittest.main()
