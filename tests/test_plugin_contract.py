import json
import hashlib
import ast
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile
from email.parser import Parser


ROOT = Path(__file__).resolve().parents[1]


class PluginContractTests(unittest.TestCase):
    def test_published_bundle_matches_release_and_runtime(self):
        vendor = ROOT / "vendor"
        release = json.loads((vendor / "RELEASE.json").read_text())
        self.assertEqual(release["toolkit_repository"],
                         "cylon58/omarchy-community-knowledge-tools")
        self.assertRegex(release["toolkit_revision"], r"^[0-9a-f]{40}$")
        wheel_name = f'omarchy_community_knowledge_tools-{release["version"]}-py3-none-any.whl'
        self.assertEqual([p.name for p in vendor.glob("*.whl")], [wheel_name])
        expected_sums = ""
        for name, key in ((wheel_name, "wheel_sha256"),
                          ("omarchy-knowledge-setup.py", "setup_sha256")):
            digest = hashlib.sha256((vendor / name).read_bytes()).hexdigest()
            self.assertEqual(digest, release[key])
            expected_sums += f"{digest}  {name}\n"
        self.assertEqual((vendor / "SHA256SUMS").read_text(), expected_sums)
        for source in ("bin/companion.py", "scripts/stage_vendor.py"):
            tree = ast.parse((ROOT / source).read_text())
            names = [ast.literal_eval(node.value) for node in tree.body
                     if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == "WHEEL_NAME"
                             for t in node.targets)]
            self.assertEqual(names, [wheel_name])
        with ZipFile(vendor / wheel_name) as archive:
            metadata_path = next(n for n in archive.namelist()
                                 if n.endswith(".dist-info/METADATA"))
            metadata = Parser().parsestr(archive.read(metadata_path).decode())
            self.assertEqual(metadata["Version"], release["version"])

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

            copied = module.stage(wheel, setup, destination, toolkit_revision="a" * 40)

            self.assertEqual(
                {path.name for path in copied},
                {wheel.name, "omarchy-knowledge-setup.py"},
            )
            self.assertEqual((destination / wheel.name).read_bytes(), b"reviewed-wheel")
            self.assertEqual(
                (destination / "omarchy-knowledge-setup.py").read_text(encoding="utf-8"),
                "# reviewed setup\n",
            )
            release = json.loads((destination / "RELEASE.json").read_text())
            self.assertEqual(release["toolkit_revision"], "a" * 40)
            self.assertEqual(release["version"], "0.4.1")
            self.assertEqual(release["wheel_sha256"],
                             hashlib.sha256(wheel.read_bytes()).hexdigest())
            self.assertEqual(release["setup_sha256"],
                             hashlib.sha256(setup.read_bytes()).hexdigest())
            self.assertEqual((destination / "SHA256SUMS").read_text(),
                             f'{release["wheel_sha256"]}  {wheel.name}\n'
                             f'{release["setup_sha256"]}  omarchy-knowledge-setup.py\n')
            with self.assertRaises(ValueError):
                module.stage(wheel, setup, base / "invalid", toolkit_revision="main")
            self.assertFalse((base / "invalid").exists())


if __name__ == "__main__":
    unittest.main()
