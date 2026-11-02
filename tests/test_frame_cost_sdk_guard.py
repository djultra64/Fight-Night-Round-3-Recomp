"""Guard the production SDK's selective readback while adding CPU probes.

This source identity guard complements (does not replace) live custom-boxer
and hair validation on Windows. Work: djultra64.
"""
import hashlib
import os
from pathlib import Path
import unittest
from pipeline_completion_fixture import extract


class FrameCostSdkGuardTests(unittest.TestCase):
    def test_selective_readback_matches_verified_103_source(self):
        configured = os.environ.get('FNR3_TEST_SDK')
        if not configured:
            self.skipTest('set FNR3_TEST_SDK to the prepared candidate SDK on Windows')
        source = (Path(configured) / 'src/graphics/vulkan/command_processor.cpp').read_text()
        method = extract(source, 'bool VulkanCommandProcessor::IssueCopy_ReadbackResolvePath(')
        # Verified sdk-inputs.json command_processor hash: 73ca9ad7...6a6b50.
        # This function forces selective texture-bake requests to kFull even
        # with global mode none; its waits, copies and retirement stay identical.
        digest = hashlib.sha256((method + '\n').encode()).hexdigest()
        self.assertEqual(digest, 'e73f6c45860addd65ebf1018ff811d22f0fc87c7bebf99698a2b97657aad9f3c')


if __name__ == '__main__':
    unittest.main()
