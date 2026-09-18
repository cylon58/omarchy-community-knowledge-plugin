import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "bin" / "companion.py"


def load_companion():
    spec = importlib.util.spec_from_file_location("plugin_companion", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, argv, *, timeout):
        self.calls.append((list(argv), timeout))
        return self.responses.pop(0)


class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.module = load_companion()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.plugin = self.root / "plugin"
        (self.plugin / "bin").mkdir(parents=True)
        (self.plugin / "vendor").mkdir()
        self.script = self.plugin / "vendor" / "omarchy-knowledge-setup.py"
        self.wheel = self.plugin / "vendor" / "omarchy_community_knowledge_tools-0.3.0-py3-none-any.whl"
        self.script.write_text("# setup\n", encoding="utf-8")
        self.wheel.write_bytes(b"wheel")
        self.home = self.root / "home"
        (self.home / ".local/bin").mkdir(parents=True)

    @staticmethod
    def completed(argv, returncode=0, stdout="", stderr=""):
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    def test_status_reports_supported_agent_install_and_cache_age(self):
        launcher = self.home / ".local/bin/omarchy-knowledge"
        launcher.write_text("launcher", encoding="utf-8")
        runner = FakeRunner([
            self.completed([], stdout="codex\n"),
            self.completed([], stdout=json.dumps({
                "revision": "a" * 40,
                "synced_at": "2026-09-18T12:00:00Z",
                "count": 3,
                "refresh_error": None,
            })),
        ])

        result = self.module.perform(
            "status", plugin_root=self.plugin, home=self.home, runner=runner,
            now=self.module.datetime(2026, 9, 18, 12, 1, tzinfo=self.module.timezone.utc),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["agent"], "codex")
        self.assertTrue(result["agent_supported"])
        self.assertTrue(result["installed"])
        self.assertEqual(result["cache_age_seconds"], 60)
        self.assertEqual(runner.calls[0][0], ["omarchy-default-agent"])
        self.assertEqual(runner.calls[1][0], [str(launcher), "status"])

    def test_unknown_agent_is_manual_fallback_not_success(self):
        runner = FakeRunner([self.completed([], stdout="mystery-agent\n")])

        result = self.module.perform(
            "status", plugin_root=self.plugin, home=self.home, runner=runner,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["agent"], "mystery-agent")
        self.assertFalse(result["agent_supported"])
        self.assertEqual(result["action"], "status")
        self.assertIn("manual", result["action_required"].lower())
        self.assertFalse(result["installed"])

    def test_antigravity_cli_is_a_distinct_supported_target(self):
        runner = FakeRunner([self.completed([], stdout="agy\n")])

        result = self.module.perform(
            "status", plugin_root=self.plugin, home=self.home, runner=runner,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["agent"], "agy")
        self.assertTrue(result["agent_supported"])
        self.assertFalse(result["installed"])

    def test_setup_and_repair_use_fixed_bundled_argv(self):
        for action, suffix in (("setup", []), ("repair", ["--repair"])):
            with self.subTest(action=action):
                runner = FakeRunner([self.completed([], stdout="complete\n")])
                result = self.module.perform(
                    action, plugin_root=self.plugin, home=self.home, runner=runner,
                )
                self.assertTrue(result["ok"])
                self.assertEqual(runner.calls[0][0], [
                    "python3", str(self.script), "--wheel", str(self.wheel),
                    "--agent", "auto", *suffix,
                ])

    def test_setup_and_repair_allow_the_helpers_bounded_command_sequence(self):
        for action in ("setup", "repair"):
            with self.subTest(action=action):
                runner = FakeRunner([self.completed([], stdout="complete\n")])

                self.module.perform(
                    action, plugin_root=self.plugin, home=self.home, runner=runner,
                )

                self.assertEqual(runner.calls[0][1], 1800)

    def test_remove_does_not_pass_wheel(self):
        runner = FakeRunner([self.completed([], stdout="Removal result: removed\n")])

        result = self.module.perform(
            "remove", plugin_root=self.plugin, home=self.home, runner=runner,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(runner.calls[0][0], [
            "python3", str(self.script), "--agent", "codex", "--remove",
        ])
        self.assertEqual(runner.calls[0][1], 1800)

    def test_refresh_uses_installed_launcher_and_sync_only(self):
        launcher = self.home / ".local/bin/omarchy-knowledge"
        launcher.write_text("launcher", encoding="utf-8")
        runner = FakeRunner([self.completed([], stdout='{"count": 4}\n')])

        result = self.module.perform(
            "refresh", plugin_root=self.plugin, home=self.home, runner=runner,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(runner.calls[0][0], [str(launcher), "sync"])

    def test_missing_bundle_and_failed_command_are_actionable(self):
        self.wheel.unlink()
        missing = self.module.perform(
            "setup", plugin_root=self.plugin, home=self.home, runner=FakeRunner([]),
        )
        self.assertFalse(missing["ok"])
        self.assertIn("bundled wheel", missing["error"])

        self.wheel.write_bytes(b"wheel")
        failed = self.module.perform(
            "setup", plugin_root=self.plugin, home=self.home,
            runner=FakeRunner([self.completed([], returncode=7, stderr="pip failed\n")]),
        )
        self.assertFalse(failed["ok"])
        self.assertEqual(failed["exit_code"], 7)
        self.assertEqual(failed["error"], "pip failed")

    def test_cli_prints_one_json_object_and_rejects_unknown_action(self):
        output = io.StringIO()
        code = self.module.main(["nonsense"], output=output)
        self.assertEqual(code, 2)
        value = json.loads(output.getvalue())
        self.assertFalse(value["ok"])
        self.assertIn("Unknown action", value["error"])


if __name__ == "__main__":
    unittest.main()
