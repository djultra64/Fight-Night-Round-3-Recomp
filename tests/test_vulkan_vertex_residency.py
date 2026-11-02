"""Native vertex refresh regression, including real shared-memory page selection.

Project work: djultra64. Compiler and execution are Windows only.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from vulkan_vertex_residency_fixture import generate


@unittest.skipUnless(os.name == 'nt', 'Native residency contracts execute on Windows')
class VertexResidency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdk = os.environ.get('FNR3_TEST_SDK')
        compiler = shutil.which('clang-cl')
        if not sdk or not compiler:
            raise unittest.SkipTest('set FNR3_TEST_SDK and provide native clang-cl')
        cls.directory = tempfile.TemporaryDirectory(prefix='fnr3-residency-')
        cls.addClassCleanup(cls.directory.cleanup)
        home = Path(cls.directory.name)
        cls.executable = home / 'residency.exe'
        source = home / 'residency.cpp'
        source.write_text(generate(Path(sdk)), encoding='utf-8')
        subprocess.run([compiler, '/std:c++17', '/EHsc', '/O2', '/MD',
                        str(source), '/Fe:' + str(cls.executable)], cwd=home,
                       check=True, capture_output=True, text=True, timeout=120)

    def contract(self, mode):
        result = subprocess.run([self.executable, mode], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_first_draw_uploads_vertex_bytes(self): self.contract('first')
    def test_same_frame_reuses_valid_bytes(self): self.contract('same_frame')
    def test_warm_frame_avoids_duplicate_upload(self): self.contract('warm')
    def test_changed_address_uploads_new_bytes(self): self.contract('changed_address')
    def test_changed_size_refreshes_bytes(self): self.contract('changed_size')
    def test_same_address_and_size_refresh_after_swap(self): self.contract('rewrite')
    def test_register_write_refreshes_same_range(self): self.contract('register_invalidation')
    def test_high_fetch_slot_refreshes_bytes(self): self.contract('high_slot')
    def test_allocation_failure_cannot_mark_resident(self): self.contract('allocation_failure')
    def test_upload_failure_can_retry(self): self.contract('upload_failure')
