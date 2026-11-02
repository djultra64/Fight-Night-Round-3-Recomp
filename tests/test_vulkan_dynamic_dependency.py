"""Dependencies between actual dynamic-rendering entries and deferred replay.

Project work: djultra64. Native execution belongs exclusively on Windows.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from vulkan_dynamic_dependency_fixture import generate


@unittest.skipUnless(os.name == 'nt', 'Native dynamic-rendering contracts execute on Windows')
class DynamicDependency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdk = os.environ.get('FNR3_TEST_SDK')
        compiler = shutil.which('clang-cl')
        if not sdk or not compiler:
            raise unittest.SkipTest('set FNR3_TEST_SDK and provide native clang-cl')
        cls.directory = tempfile.TemporaryDirectory(prefix='fnr3-dynamic-dependency-')
        cls.addClassCleanup(cls.directory.cleanup)
        home = Path(cls.directory.name)
        cls.executable = home / 'dependency.exe'
        source = home / 'dependency.cpp'
        source.write_text(generate(Path(sdk)), encoding='utf-8')
        built = subprocess.run([compiler, '/std:c++17', '/EHsc', '/O2', '/MD',
                        '/I' + str(Path(sdk) / 'thirdparty/vulkan-headers/include'),
                        str(source), '/Fe:' + str(cls.executable)], cwd=home,
                        capture_output=True, text=True, timeout=120)
        if built.returncode:
            raise RuntimeError(built.stdout + built.stderr)

    def contract(self, mode):
        result = subprocess.run([self.executable, mode], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_color_reopen_after_unrelated_upload(self): self.contract('color')
    def test_depth_reopen_after_unrelated_upload(self): self.contract('depth')
    def test_color_reopen_in_later_submission(self): self.contract('split_color')
    def test_depth_reopen_in_later_submission(self): self.contract('split_depth')
    def test_transfer_color_reopen_after_upload(self): self.contract('transfer_color')
    def test_transfer_depth_reopen_after_upload(self): self.contract('transfer_depth')
    def test_transfer_color_reopen_in_later_submission(self): self.contract('transfer_split_color')
    def test_transfer_depth_reopen_in_later_submission(self): self.contract('transfer_split_depth')
    def test_color_draws_in_one_instance_stay_together(self): self.contract('same_color')
    def test_depth_draws_in_one_instance_stay_together(self): self.contract('same_depth')
    def test_legacy_color_uses_its_existing_dependency_path(self): self.contract('legacy_color')
    def test_legacy_depth_uses_its_existing_dependency_path(self): self.contract('legacy_depth')
    def test_transfer_color_draws_in_one_instance_stay_together(self): self.contract('same_transfer_color')
    def test_transfer_depth_draws_in_one_instance_stay_together(self): self.contract('same_transfer_depth')
    def test_attachment_free_entry_adds_no_attachment_dependency(self): self.contract('empty_same')
