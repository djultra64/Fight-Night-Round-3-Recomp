"""Vulkan usage contracts for the SDK's real scratch allocation and DMA consumers.

Project work: djultra64. Native compiler and execution are Windows only.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from vulkan_scratch_usage_fixture import generate


@unittest.skipUnless(os.name == 'nt', 'Native scratch contracts execute on Windows')
class ScratchUsage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdk = os.environ.get('FNR3_TEST_SDK')
        compiler = shutil.which('clang-cl')
        if not sdk or not compiler:
            raise unittest.SkipTest('set FNR3_TEST_SDK and provide native clang-cl')
        cls.directory = tempfile.TemporaryDirectory(prefix='fnr3-scratch-')
        cls.addClassCleanup(cls.directory.cleanup)
        home = Path(cls.directory.name)
        cls.executable = home / 'scratch.exe'
        source = home / 'scratch.cpp'
        source.write_text(generate(Path(sdk)), encoding='utf-8')
        subprocess.run([compiler, '/std:c++17', '/EHsc', '/O2', '/MD',
                        '/I' + str(Path(sdk) / 'thirdparty/vulkan-headers/include'),
                        str(source), '/Fe:' + str(cls.executable)], cwd=home,
                       check=True, capture_output=True, text=True, timeout=120)

    def contract(self, mode):
        result = subprocess.run([self.executable, mode], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_new_16bit_snapshot_usage(self): self.contract('new16')
    def test_new_32bit_snapshot_usage(self): self.contract('new32')
    def test_reused_16bit_snapshot_usage(self): self.contract('reuse16')
    def test_reused_32bit_snapshot_usage(self): self.contract('reuse32')
    def test_pending_growth_16bit_snapshot_usage(self): self.contract('grow16')
    def test_pending_growth_32bit_snapshot_usage(self): self.contract('grow32')
    def test_completed_growth_16bit_snapshot_usage(self): self.contract('grow_completed16')
    def test_completed_growth_32bit_snapshot_usage(self): self.contract('grow_completed32')
    def test_zero_size_does_not_allocate(self): self.contract('zero')
    def test_creation_failure_preserves_empty_owner(self): self.contract('failure_empty')
    def test_growth_failure_preserves_existing_owner(self): self.contract('failure_grow')
    def test_texture_loading_usage_remains_available(self): self.contract('texture')
    def test_pending_growth_defers_retirement(self): self.contract('pending')
    def test_completed_growth_can_retire_old_buffer(self): self.contract('completed')
