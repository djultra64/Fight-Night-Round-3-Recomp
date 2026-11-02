"""EDRAM dump ordering after a caller abort, using full SDK methods.

Project work: djultra64. Run the native contracts on the Windows test host.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from vulkan_edram_dump_fixture import generate


@unittest.skipUnless(os.name == 'nt', 'Native EDRAM contracts execute on Windows')
class EdramDump(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdk = os.environ.get('FNR3_TEST_SDK')
        compiler = shutil.which('clang-cl')
        if not sdk or not compiler:
            raise unittest.SkipTest('set FNR3_TEST_SDK and provide native clang-cl')
        cls.directory = tempfile.TemporaryDirectory(prefix='fnr3-edram-')
        cls.addClassCleanup(cls.directory.cleanup)
        home = Path(cls.directory.name)
        cls.executable = home / 'edram.exe'
        source = home / 'edram.cpp'
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

    def test_overlapping_dumps_without_resolve_consumer(self): self.contract('abort')
    def test_partial_dump_failure_before_next_dump(self): self.contract('partial_abort')
    def test_normal_resolve_transition_keeps_existing_dependency(self): self.contract('normal')
    def test_empty_dump_adds_no_commands(self): self.contract('empty')
    def test_fresh_dump_adds_no_unnecessary_write_commit(self): self.contract('fresh')
