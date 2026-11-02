"""Validate color attachment headers at the actual deferred Vulkan boundary.

Project work: djultra64. Every color mask is exercised with depth on and off.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from vulkan_rendering_attachments_fixture import generate


@unittest.skipUnless(os.name == 'nt', 'Native Vulkan attachment contracts execute on Windows')
class RenderingAttachments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdk = os.environ.get('FNR3_TEST_SDK')
        compiler = shutil.which('clang-cl')
        if not sdk or not compiler:
            raise unittest.SkipTest('set FNR3_TEST_SDK and provide native clang-cl')
        cls.directory = tempfile.TemporaryDirectory(prefix='fnr3-attachments-')
        cls.addClassCleanup(cls.directory.cleanup)
        home = Path(cls.directory.name)
        cls.executable = home / 'attachments.exe'
        source = home / 'attachments.cpp'
        source.write_text(generate(Path(sdk)), encoding='utf-8')
        subprocess.run([compiler, '/std:c++17', '/EHsc', '/O2', '/MD',
                        '/I' + str(Path(sdk) / 'thirdparty/vulkan-headers/include'),
                        str(source), '/Fe:' + str(cls.executable)], cwd=home,
                       check=True, capture_output=True, text=True, timeout=120)

    def contract(self, mode):
        result = subprocess.run([self.executable, str(mode)], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


for mode in range(34):
    def case(self, selected=mode):
        self.contract(selected)
    setattr(RenderingAttachments, f'test_attachment_configuration_{mode:02d}', case)
