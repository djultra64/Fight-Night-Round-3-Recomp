"""Real Windows XMA decoder regressions; captured packet data stays private.

Project work: djultra64. Set FNR3_TEST_SDK and FNR3_TEST_XMA_DATA; run in the
native VS developer environment with clang-cl on PATH. The latter directory
contains the two historical pairs named below, each packet exactly2048bytes.
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


MODES = ('reference', 'ring7', 'ring13', 'late', 'late_reuse', 'late_reset',
         'body_late', 'body_reuse', 'late_wait', 'body_wait', 'loop_late',
         'loop_body', 'tail_early', 'tail_late', 'tail_reuse', 'tail_body_early',
         'tail_body_late', 'tail_body_reuse', 'full')
PAIRS = ('xma', 'silence-third-ch0')


@unittest.skipUnless(os.name == 'nt', 'Real XMA contracts execute on Windows')
class NativeXmaStream(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sdk = os.environ.get('FNR3_TEST_SDK')
        data = os.environ.get('FNR3_TEST_XMA_DATA')
        compiler = shutil.which('clang-cl')
        if not sdk or not data or not compiler:
            raise unittest.SkipTest('provide SDK, private XMA captures and native clang-cl')
        sdk, cls.data = Path(sdk), Path(data)
        for pair in PAIRS:
            for index in (0, 1):
                if (cls.data / f'{pair}-input{index}.bin').stat().st_size != 2048:
                    raise ValueError('XMA fixture must be exactly2048bytes')
        cls.directory = tempfile.TemporaryDirectory(prefix='fnr3-xma-')
        cls.addClassCleanup(cls.directory.cleanup)
        home = Path(cls.directory.name)
        cls.executable = home / 'xma-stream.exe'
        source = Path(__file__).parent / 'audio/xma_stream_contract.cpp'
        include = ['/I' + str(sdk / path) for path in (
            'include', 'thirdparty/fmt/include', 'thirdparty/spdlog/include',
            'thirdparty/sdl3/include', 'thirdparty/simde')]
        subprocess.run([compiler, '/std:c++latest', '/utf-8', '/EHsc', '/O2', '/MD',
                        '/DSPDLOG_FMT_EXTERNAL', *include, str(source),
                        '/Fe:' + str(cls.executable), '/link',
                        '/LIBPATH:' + str(sdk / 'out/win-amd64'), 'rexruntime.lib'],
                       cwd=home, check=True, capture_output=True, text=True, timeout=120)
        cls.environment = dict(os.environ)
        cls.environment['PATH'] = str(sdk / 'out/win-amd64') + os.pathsep + os.environ['PATH']

    def contract(self, pair, legacy, mode):
        args = [str(self.executable), str(self.data / f'{pair}-input0.bin'),
                str(self.data / f'{pair}-input1.bin'), mode]
        if legacy:
            args.append('legacy')
        result = subprocess.run(args, cwd=self.directory.name, env=self.environment,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def case(pair, legacy, mode):
    def run(self):
        self.contract(pair, legacy, mode)
    return run


for pair in PAIRS:
    for legacy in (False, True):
        for mode in MODES:
            name = f'test_{pair.replace("-", "_")}_{"legacy" if legacy else "no_lookahead"}_{mode}'
            setattr(NativeXmaStream, name, case(pair, legacy, mode))
