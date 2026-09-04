"""Exercise malformed packages, containment and read-only validation."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.check_agent_skills import validate


class SkillPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.add_skill("sample-workflow")

    def add_skill(self, name):
        skill = (
            f'---\nname: {name}\ndescription: "Prepare an isolated review workflow."\n---\n\n'
            "Read the relevant user request and prepare its artifacts.\n"
        )
        for root in (".agents", ".claude"):
            path = self.repo / root / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(skill)
        directory = self.repo / ".agents/skills" / name / "agents"
        directory.mkdir()
        (directory / "openai.yaml").write_text(
            'interface:\n  display_name: "Sample workflow"\n'
            '  short_description: "Prepare a review with isolated artifacts"\n'
            f'  default_prompt: "Use ${name} for this review."\n'
        )

    @property
    def target(self):
        return self.repo / ".agents/skills/sample-workflow/SKILL.md"

    def codes(self):
        return validate(self.repo)["errors"]

    def test_valid_package_does_not_modify_files(self):
        def snapshot():
            return {
                str(p.relative_to(self.repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.repo.rglob("*")
                if p.is_file()
            }

        before = snapshot()
        self.assertEqual(validate(self.repo)["status"], "pass")
        self.assertEqual(snapshot(), before)

    def test_missing_skill_mapping_fails(self):
        self.add_skill("second-workflow")
        self.target.unlink()
        self.assertIn("SKILL_PARSE:sample-workflow", self.codes())
        (self.repo / ".claude/skills/third-workflow").mkdir()
        self.assertIn("MISSING_CODEX_SKILL:third-workflow", self.codes())

    def test_duplicate_identity_fails(self):
        self.add_skill("second-workflow")
        path = self.repo / ".agents/skills/second-workflow/SKILL.md"
        path.write_text(path.read_text().replace("name: second-workflow", "name: sample-workflow"))
        self.assertIn("DUPLICATE_SKILL_NAME:sample-workflow", self.codes())

    def test_duplicate_yaml_key_fails_instead_of_overriding(self):
        self.target.write_text(
            self.target.read_text().replace(
                "name: sample-workflow", "name: another\nname: sample-workflow"
            )
        )
        self.assertIn("SKILL_PARSE:sample-workflow", self.codes())

    def test_empty_description_and_claude_metadata_fail(self):
        self.target.write_text(
            '---\nname: sample-workflow\ndescription: ""\n'
            "user-invocable: true\n---\nUse current task.\n"
        )
        codes = self.codes()
        self.assertIn("DESCRIPTION:sample-workflow", codes)
        self.assertIn("UNSUPPORTED_METADATA:sample-workflow", codes)

    def test_ui_yaml_missing_or_wrong_invocation_fails(self):
        path = self.target.parent / "agents/openai.yaml"
        path.write_text(path.read_text().replace("$sample-workflow", "$wrong"))
        self.assertIn("DEFAULT_PROMPT:sample-workflow", self.codes())
        path.unlink()
        self.assertIn("UI_METADATA:sample-workflow", self.codes())

    def test_unicode_ui_and_local_link_pass(self):
        path = self.repo / "docs/Örnek plan.md"
        path.parent.mkdir()
        path.write_text("Kaynak")
        self.target.write_text(
            self.target.read_text()
            + "\n[Plan](../../../docs/%C3%96rnek%20plan.md)\n[Kaynak](https://example.invalid/page)\n"
        )
        result = validate(self.repo)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["local_references_checked"], 1)

    def test_broken_reference_and_outside_path_fail(self):
        self.target.write_text(
            self.target.read_text()
            + "\n[Missing](../../../docs/missing.md)\n[Outside](../../../../outside.txt)\n"
        )
        self.assertEqual(len([c for c in self.codes() if c.startswith("LOCAL_REFERENCE:")]), 2)

    def test_symlink_escape_is_not_read(self):
        with tempfile.TemporaryDirectory() as external:
            secret = Path(external) / "secret.md"
            secret.write_text("should-not-be-loaded")
            self.target.unlink()
            self.target.symlink_to(secret)
            self.assertIn("SKILL_PARSE:sample-workflow", self.codes())

    def test_dou_runtime_drift_is_detected(self):
        self.add_skill("dou-kurulum")
        path = self.repo / ".claude/skills/dou-kurulum/SKILL.md"
        path.write_text(path.read_text() + "Different workflow\n")
        self.assertIn("DOU_RUNTIME_DRIFT:dou-kurulum", self.codes())

    def test_template_and_oversized_files_fail(self):
        self.target.write_text(self.target.read_text() + "\n$ARGUMENTS\n")
        self.assertIn("UNFINISHED_TEMPLATE:sample-workflow", self.codes())
        self.target.write_bytes(b"x" * 1_000_001)
        self.assertIn("SKILL_PARSE:sample-workflow", self.codes())

    def test_invalid_path_and_loop_are_reported_without_crashing(self):
        (self.target.parent / "loop").symlink_to("loop")
        self.target.write_text(self.target.read_text() + "\n[Nul](%00.md)\n[Loop](loop)\n")
        self.assertEqual(len([c for c in self.codes() if c.startswith("LOCAL_REFERENCE:")]), 2)

    def test_deep_yaml_and_object_tags_fail_safely(self):
        self.target.write_text("---\nname: " + "[" * 600 + "x" + "]" * 600 + "\n---\nBody")
        self.assertIn("SKILL_PARSE:sample-workflow", self.codes())
        self.target.write_text("---\nname: !!python/object:builtins.object {}\n---\nBody")
        self.assertIn("SKILL_PARSE:sample-workflow", self.codes())

    def test_optional_metadata_types_are_checked(self):
        self.target.write_text(
            self.target.read_text().replace(
                "name: sample-workflow",
                "name: sample-workflow\nmetadata: 42\nlicense: [1,2]\nallowed-tools: {bad: true}",
            )
        )
        self.assertEqual(len([c for c in self.codes() if c.startswith("METADATA_TYPE:")]), 3)

    def test_skill_name_prefix_is_not_an_invocation(self):
        path = self.target.parent / "agents/openai.yaml"
        path.write_text(path.read_text().replace("$sample-workflow", "$sample-workflow-other"))
        self.assertIn("DEFAULT_PROMPT:sample-workflow", self.codes())

    def test_reference_style_and_file_urls_are_checked(self):
        self.target.write_text(
            self.target.read_text()
            + (
                "\n[Read][guide]\n\n[guide]: references/missing.md\n"
                "[Read][not-defined]\n[Outside](file:///private/tmp/outside.md)\n"
            )
        )
        codes = self.codes()
        self.assertEqual(len([c for c in codes if c.startswith("LOCAL_REFERENCE:")]), 2)
        self.assertIn("UNDEFINED_REFERENCE:sample-workflow:not-defined", codes)

    def test_cli_exit_and_json_follow_real_validation(self):
        checker = Path(__file__).with_name("check_agent_skills.py")
        command = [sys.executable, str(checker), "--repo-root", str(self.repo), "--json"]
        # Fixed local checker and an isolated fixture; no shell or user command.
        passed = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
        self.assertEqual(passed.returncode, 0)
        self.assertEqual(json.loads(passed.stdout)["status"], "pass")
        self.target.unlink()
        failed = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
        self.assertEqual(failed.returncode, 1)
        self.assertEqual(json.loads(failed.stdout)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
