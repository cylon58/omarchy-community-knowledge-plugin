import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PluginContractTests(unittest.TestCase):
    def test_manifest_declares_one_bar_widget_entrypoint(self):
        manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["id"], "io.github.cylon58.omarchy-knowledge")
        self.assertEqual(manifest["kinds"], ["bar-widget"])
        self.assertEqual(manifest["entryPoints"], {"barWidget": "BarWidget.qml"})
        self.assertFalse(manifest["barWidget"]["allowMultiple"])

    def test_qml_has_no_implicit_mutation_or_background_service(self):
        sources = "\n".join(
            (ROOT / name).read_text(encoding="utf-8")
            for name in ("BarWidget.qml", "Panel.qml")
        )
        self.assertNotIn("Timer {", sources)
        self.assertNotIn("Component.onCompleted", sources)
        self.assertNotIn("installHook", sources)
        self.assertIn('["python3", root.companionPath, action]', sources)
        self.assertIn("switchPanelFrom(root.barIdentity, direction)", sources)
        for action in ("setup", "repair", "refresh", "remove"):
            self.assertIn(f'root.runAction("{action}")', sources)

    def test_stage_vendor_copies_only_named_release_inputs(self):
        import importlib.util
        module_path = ROOT / "scripts" / "stage_vendor.py"
        spec = importlib.util.spec_from_file_location("stage_vendor", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            wheel = base / "omarchy_community_knowledge_tools-0.4.1-py3-none-any.whl"
            setup = base / "setup_companion.py"
            destination = base / "export"
            wheel.write_bytes(b"reviewed-wheel")
            setup.write_text("# reviewed setup\n", encoding="utf-8")

            copied = module.stage(wheel, setup, destination)

            self.assertEqual(
                {path.name for path in copied},
                {wheel.name, "omarchy-knowledge-setup.py"},
            )
            self.assertEqual((destination / wheel.name).read_bytes(), b"reviewed-wheel")
            self.assertEqual(
                (destination / "omarchy-knowledge-setup.py").read_text(encoding="utf-8"),
                "# reviewed setup\n",
            )


if __name__ == "__main__":
    unittest.main()
