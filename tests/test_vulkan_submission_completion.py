"""Windows contracts for actual SDK submission tracking and resource reuse.

Project work: djultra64. Requires the prepared SDK and a native developer shell.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from vulkan_submission_completion_fixture import generate


@unittest.skipUnless(os.name == 'nt', 'Vulkan SDK lifetime contracts execute on Windows')
class SubmissionCompletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdk = os.environ.get('FNR3_TEST_SDK')
        compiler = shutil.which('clang-cl')
        if not sdk or not compiler:
            raise unittest.SkipTest('set FNR3_TEST_SDK and provide native clang-cl')
        cls.directory = tempfile.TemporaryDirectory(prefix='fnr3-submission-')
        cls.addClassCleanup(cls.directory.cleanup)
        home = Path(cls.directory.name)
        cls.executable = home / 'completion.exe'
        source = home / 'completion.cpp'
        source.write_text(generate(Path(sdk)), encoding='utf-8')
        subprocess.run([compiler, '/std:c++17', '/EHsc', '/O2', '/MD',
                        '/I' + str(Path(sdk) / 'thirdparty/vulkan-headers/include'),
                        str(source), '/Fe:' + str(cls.executable)], cwd=home,
                       check=True, capture_output=True, text=True, timeout=120)

    def contract(self, mode):
        result = subprocess.run([self.executable, mode], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_later_completion_satisfies_an_earlier_wait(self):
        self.contract('await_reached')

    def test_failed_wait_does_not_reset_a_pending_paint_pool(self):
        self.contract('paint_wait_failure')

    def test_completed_paint_can_reuse_its_pool(self):
        self.contract('paint_ready')

    def test_unused_paint_pool_does_not_add_a_wait(self):
        self.contract('paint_initial')

    def test_wait_failure_never_invents_completion(self):
        self.contract('wait_failure_pending')

    def test_failed_wait_keeps_the_previous_output_image_alive(self):
        self.contract('resize_wait_failure')

    def test_completed_resize_can_retire_the_previous_image(self):
        self.contract('resize_ready')

    def test_unchanged_output_adds_neither_waits_nor_retirement(self):
        self.contract('resize_unchanged')

    def test_queue_completion_proof_recovers_paint_after_a_failed_wait(self):
        self.contract('paint_recovery')

    def test_paint_device_loss_uses_the_terminal_result(self):
        self.contract('paint_device_lost')

    def test_queue_completion_proof_recovers_output_resize(self):
        self.contract('resize_recovery')

    def test_resize_device_loss_reports_through_the_existing_callback(self):
        self.contract('resize_device_lost')

    def test_failed_signal_does_not_permanently_block_resize(self):
        self.contract('resize_signal_failure')

    def test_missing_fence_does_not_permanently_block_resize(self):
        self.contract('resize_null_fence')

    def test_dropped_submission_preserves_the_index_for_retry(self):
        self.contract('dropped_submission')
