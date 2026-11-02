"""Presenter replacement must preserve GPU resources when completion is unproved.

Project work: djultra64. Run native contracts on Windows.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from vulkan_present_retirement_fixture import generate


@unittest.skipUnless(os.name == 'nt', 'Native presenter lifetime contracts execute on Windows')
class PresentRetirement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdk = os.environ.get('FNR3_TEST_SDK')
        compiler = shutil.which('clang-cl')
        if not sdk or not compiler:
            raise unittest.SkipTest('set FNR3_TEST_SDK and provide native clang-cl')
        cls.directory = tempfile.TemporaryDirectory(prefix='fnr3-present-retirement-')
        cls.addClassCleanup(cls.directory.cleanup)
        home = Path(cls.directory.name)
        cls.executable = home / 'retirement.exe'
        source = home / 'retirement.cpp'
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

    def test_intermediate_failed_wait_keeps_resources(self): self.contract('intermediate_failure')
    def test_intermediate_device_loss_propagates(self): self.contract('intermediate_lost')
    def test_intermediate_queue_proof_allows_retirement(self): self.contract('intermediate_recovery')
    def test_intermediate_completed_use_needs_no_queue_wait(self): self.contract('intermediate_ready')
    def test_pipeline_failed_wait_keeps_resources(self): self.contract('pipeline_failure')
    def test_pipeline_device_loss_propagates(self): self.contract('pipeline_lost')
    def test_pipeline_queue_proof_allows_retirement(self): self.contract('pipeline_recovery')
    def test_pipeline_completed_use_needs_no_queue_wait(self): self.contract('pipeline_ready')
