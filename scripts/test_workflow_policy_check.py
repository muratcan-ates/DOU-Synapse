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

    def test_rejects_continue_on_error_for_steps_and_jobs(self) -> None:
        for body in (
            "jobs: {test: {continue-on-error: true, steps: [{run: pytest}]}}\n",
            "jobs: {test: {steps: [{run: pytest, continue-on-error: true}]}}\n",
            "jobs: {test: {steps: [{run: pytest, continue-on-error: '${{ inputs.allow_failure }}'}]}}\n",
            "jobs: {test: {steps: [{run: pytest, continue-on-error: 'false'}]}}\n",
        ):
            with self.subTest(body=body):
                self.assertIn(
                    "FAIL_OPEN_CONTINUE",
                    [item.code for item in inspect_workflows(self._repo(body))],
                )

    def test_accepts_literal_false_failure_policy(self) -> None:
        root = self._repo(
            "jobs: {test: {continue-on-error: false, steps: [{run: pytest, continue-on-error: false}]}}\n"
        )
        self.assertEqual(inspect_workflows(root), [])

    def test_alias_cannot_hide_failure_policy(self) -> None:
        root = self._repo(
            "jobs:\n  test:\n    steps:\n      - &unsafe {run: pytest, continue-on-error: true}\n      - *unsafe\n"
        )
        self.assertIn(
            "FAIL_OPEN_CONTINUE", [item.code for item in inspect_workflows(root)]
        )

    def test_local_composite_cannot_hide_failure_policy(self) -> None:
        root = self._repo(
            "jobs: {test: {steps: [{uses: ./.github/actions/local}]}}\n",
            local_action="name: local\nruns: {using: composite, steps: [{run: pytest, shell: bash, continue-on-error: true}]}\n",
        )
        violations = inspect_workflows(root)
        self.assertIn(
            ("FAIL_OPEN_CONTINUE", ".github/actions/local/action.yml"),
            [(item.code, item.path.as_posix()) for item in violations],
        )

    def test_rejects_swallowed_shell_failure(self) -> None:
        for script in (
            "pytest || true",
            "pytest||true",
            "pytest || :",
            "pytest || command true",
            "pytest || (true)",
            "pytest || 'true'",
            "pytest || /bin/true",
            "pytest || /usr/bin/true",
            "pytest || \\\n true",
        ):
            with self.subTest(script=script):
                root = self._repo(
                    "jobs:\n  test:\n    steps:\n      - run: |\n          "
                    + script.replace("\n", "\n          ")
                    + "\n"
                )
                self.assertIn(
                    "SWALLOWED_COMMAND_FAILURE",
                    [item.code for item in inspect_workflows(root)],
                )

    def test_shell_data_comments_and_failing_fallback_are_allowed(self) -> None:
        for script in (
            "echo '|| true'",
            "echo '||' true",
            'echo "pytest || true"',
            "# pytest || true\npytest",
            "pytest || exit 1",
            "pytest || { echo failed; exit 1; }",
        ):
            with self.subTest(script=script):
                indented = script.replace("\n", "\n          ")
                root = self._repo(
                    f"jobs:\n  test:\n    steps:\n      - run: |\n          {indented}\n"
                )
                self.assertEqual(inspect_workflows(root), [])

    def test_rejects_global_and_unexpected_job_write_permissions(self) -> None:
        for body in (
            "permissions: {contents: write}\njobs: {}\n",
            "permissions: write-all\njobs: {}\n",
            "jobs: {test: {permissions: {contents: write}}}\n",
            "jobs: {codeql: {permissions: {security-events: write}}}\n",
        ):
            with self.subTest(body=body):
                self.assertTrue(
                    any(
                        item.code
                        in {"UNSAFE_PERMISSIONS", "UNEXPECTED_WRITE_PERMISSION"}
                        for item in inspect_workflows(self._repo(body))
                    )
                )

    def test_rejects_dynamic_or_malformed_permissions(self) -> None:
        for body in (
            "permissions: '${{ inputs.permissions }}'\n",
            "permissions: {contents: '${{ inputs.access }}'}\n",
            "permissions: {contents: true}\n",
            "permissions: [contents, write]\n",
        ):
            with self.subTest(body=body):
                self.assertIn(
                    "UNSAFE_PERMISSIONS",
                    [item.code for item in inspect_workflows(self._repo(body))],
                )

    def test_accepts_empty_and_read_permissions(self) -> None:
        for body in (
            "permissions: {}\n",
            "permissions: read-all\n",
            "permissions: {contents: read, packages: none}\n",
            "jobs: {test: {permissions: {contents: read}}}\n",
        ):
            with self.subTest(body=body):
                self.assertEqual(inspect_workflows(self._repo(body)), [])

    def test_expected_write_scopes_are_bound_to_workflow_and_job(self) -> None:
        for filename, job, scopes in (
            ("security.yml", "codeql", "security-events: write"),
            (
                "release-candidate.yml",
                "candidate",
                "attestations: write, id-token: write, packages: write",
            ),
        ):
            with self.subTest(filename=filename):
                root = self._repo(f"jobs: {{{job}: {{permissions: {{{scopes}}}}}}}\n")
                source = root / ".github/workflows/ci.yml"
                target = source.with_name(filename)
                source.rename(target)
                self.assertEqual(inspect_workflows(root), [])
                target.write_text(
                    target.read_text().replace(f"{job}:", "other-job:"),
                    encoding="utf-8",
                )
                self.assertIn(
                    "UNEXPECTED_WRITE_PERMISSION",
                    [item.code for item in inspect_workflows(root)],
                )

    def test_allowlisted_job_cannot_add_scopes_or_widen_workflow_default(self) -> None:
        for body in (
            "jobs: {codeql: {permissions: {security-events: write, contents: write}}}\n",
            "permissions: {security-events: write}\njobs: {codeql: {steps: []}}\n",
        ):
            with self.subTest(body=body):
                root = self._repo(body)
                source = root / ".github/workflows/ci.yml"
                source.rename(source.with_name("security.yml"))
                self.assertIn(
                    "UNEXPECTED_WRITE_PERMISSION",
                    [item.code for item in inspect_workflows(root)],
                )

    def test_yaml_merge_cannot_hide_write_permissions(self) -> None:
        root = self._repo(
            "permissions: &read {contents: read}\njobs:\n  test:\n    permissions:\n      <<: *read\n      contents: write\n"
        )
        self.assertIn(
            "UNEXPECTED_WRITE_PERMISSION",
            [item.code for item in inspect_workflows(root)],
        )

    def test_current_repository_obeys_policy(self) -> None:
        self.assertEqual(inspect_workflows(Path(__file__).resolve().parents[1]), [])


if __name__ == "__main__":
    unittest.main()
