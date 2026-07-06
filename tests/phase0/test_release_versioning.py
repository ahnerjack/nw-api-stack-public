#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / 'scripts/build-release-package.py'


def load_build_module():
    spec = importlib.util.spec_from_file_location('build_release_package_under_test', BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'Cannot load {BUILD_SCRIPT}')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VersionValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_build_module()

    def test_accepts_formal_patch_and_rc_versions(self):
        for version in ['V0.0.1', 'V0.0.1.2', 'V1.2.3', 'V1.2.3-rc.1', 'V1.2.3.4-rc.5']:
            self.assertEqual(self.mod.validate_version(version), version)

    def test_rejects_non_policy_versions(self):
        for version in ['0.0.1', 'v0.0.1', 'phase0-test', 'V0.0', 'V0.0.1-preview.1', 'V0.0.1.2.3']:
            with self.assertRaises(SystemExit, msg=version):
                self.mod.validate_version(version)


if __name__ == '__main__':
    unittest.main(verbosity=2)
