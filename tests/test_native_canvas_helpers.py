"""Windows native contracts for the actual canvas hooks. Project work: djultra64."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from native_canvas_fixture import generate

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(os.name=='nt','Canvas hook execution is Windows only')
class NativeCanvasHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler=shutil.which('clang-cl')
        if not compiler:raise unittest.SkipTest('Native clang-cl required')
        cls.directory=tempfile.TemporaryDirectory(prefix='fnr3-canvas-')
        cls.addClassCleanup(cls.directory.cleanup)
        home=Path(cls.directory.name);source,includes=generate(ROOT,home)
        cls.executable=home/'canvas.exe'
        subprocess.run([compiler,'/std:c++latest','/EHsc','/O2','/MD','/I'+str(includes),'/I'+str(ROOT/'src'),str(source),'/Fe:'+str(cls.executable)],cwd=home,check=True,capture_output=True,text=True,timeout=120)
    def contract(self,mode):
        p=subprocess.run([self.executable,mode],capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def test_primitive_direct_native_canvas_unchanged(self):self.contract('primitive_direct')
    def test_primitive_nested_scope(self):self.contract('primitive_nested')
    def test_primitive1080_preserves_source(self):self.contract('primitive')
    def test_primitive900(self):self.contract('900_primitive')
    def test_primitive720_unchanged(self):self.contract('720_primitive')
    def test_primitive_nonortho_excluded(self):self.contract('primitive_nonortho')
    def test_primitive_no_target_excluded(self):self.contract('primitive_no_target')
    def test_bloom_context_cursor_and_signed15(self):self.contract('bloom')
    def test_bloom_unknown_geometry_uses_original(self):self.contract('bloom_fallback')
    def test_font_all_columns_and_translation(self):self.contract('font')
    def test_font_nested_scope(self):self.contract('font_nested')
    def test_font_apt_not_scaled_twice(self):self.contract('font_apt')
    def test_font_3d_excluded(self):self.contract('font_3d')
    def test_font_nonortho_excluded(self):self.contract('font_nonortho')
    def test_font_native720_unchanged(self):self.contract('720_font')
    def test_movie_four_setters_and_context(self):self.contract('movie')
    def test_movie_preserves43_aspect(self):self.contract('movie_43')
    def test_movie_failed_initialization(self):self.contract('movie_fail')
    def test_movie_terminal_state(self):self.contract('movie_terminal')
    def test_movie_native720_unchanged(self):self.contract('720_movie')
    def test_physical_null_cannot_fallback(self):
        p=subprocess.run([self.executable,'physical_null'],capture_output=True,text=True,timeout=10)
        self.assertEqual(p.returncode,73,p.stdout+p.stderr)
        self.assertIn('PHYSICAL_ORIGINAL',p.stdout)
        self.assertIn('cannot use a different allocator owner',p.stderr)
    def test_physical_other_caller_untouched(self):self.contract('physical_other')
    def test_budget720(self):self.contract('720_budget')
    def test_budget900(self):self.contract('900_budget')
    def test_budget1080(self):self.contract('1080_budget')
    def test_budget_other_category_untouched(self):self.contract('budget_other')
