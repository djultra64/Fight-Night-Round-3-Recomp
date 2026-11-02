"""Readback resources must remain alive until their GPU work is completed.

Project work: djultra64. The compiled fixture uses the prepared SDK method.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from vulkan_readback_eviction_fixture import generate


@unittest.skipUnless(os.name == 'nt', 'Native Vulkan retirement contracts execute on Windows')
class ReadbackEviction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdk = os.environ.get('FNR3_TEST_SDK')
        compiler = shutil.which('clang-cl')
        if not sdk or not compiler:
            raise unittest.SkipTest('set FNR3_TEST_SDK and provide native clang-cl')
        cls.directory = tempfile.TemporaryDirectory(prefix='fnr3-readback-')
        cls.addClassCleanup(cls.directory.cleanup)
        home = Path(cls.directory.name)
        cls.executable = home / 'readback.exe'
        source = home / 'readback.cpp'
        source.write_text(generate(Path(sdk)), encoding='utf-8')
        subprocess.run([compiler, '/std:c++17', '/EHsc', '/O2', '/MD',
                        '/I' + str(Path(sdk) / 'thirdparty/vulkan-headers/include'),
                        str(source), '/Fe:' + str(cls.executable)], cwd=home,
                       check=True, capture_output=True, text=True, timeout=120)

    def contract(self, mode):
        result = subprocess.run([self.executable, mode], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_empty_cache_has_no_retirement(self): self.contract('empty')
    def test_pressure_keeps_first_slot_in_flight(self): self.contract('pressure_pending0')
    def test_pressure_keeps_second_slot_in_flight(self): self.contract('pressure_pending1')
    def test_pressure_keeps_recent_frame_references(self): self.contract('pressure_recent')
    def test_age_does_not_override_first_pending_slot(self): self.contract('age_pending0')
    def test_age_does_not_override_second_pending_slot(self): self.contract('age_pending1')
    def test_pressure_retires_completed_entries(self): self.contract('pressure_completed')
    def test_age_retires_completed_entries(self): self.contract('age_completed')
    def test_recent_entry_under_limit_stays_alive(self): self.contract('recent_under_limit')
    def test_exact_age_boundary_stays_alive(self): self.contract('age_boundary')
    def test_exact_completion_boundary_can_retire(self): self.contract('completion_boundary')
    def test_pressure_selects_completed_not_pending_entries(self): self.contract('mixed_pressure')
    def test_deferred_entries_retire_after_completion(self): self.contract('rescan')
