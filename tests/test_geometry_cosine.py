"""Native regression for rounded collision-plane cosines. Work: djultra64."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'geometry_transform', ROOT / 'tools/port-build/native60_transform.py')
transform = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transform)


@unittest.skipUnless(os.name == 'nt' and os.environ.get('FNR3_GEOMETRY_CXX'),
                     'Requires an explicitly configured native Windows compiler')
class GeometryCosine(unittest.TestCase):
    def test_rounded_normals_reuse_groups_without_changing_other_angles(self):
        # Purpose-written call-site fixture, never generated game source.
        body = ('\tctx.lr = 0x82224A84;\n'
                '\tsub_826F92D8(ctx, base);\n')
        # Before the fix this executes the original acos call unchanged, so RED
        # reports the numerical failure rather than an unknown-transform error.
        if '82224770' in transform.TARGETS:
            body = transform.patch_function('82224770', body)
        program = r'''
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <immintrin.h>
struct Context { struct { double f64; } f1; uint64_t lr; };
static void sub_826F92D8(Context& ctx, uint8_t*) { ctx.f1.f64=std::acos(ctx.f1.f64); }
static double angle(double value) {
 Context ctx{{value},0}; uint8_t* base=nullptr;
BODY
 return ctx.f1.f64;
}
int main() {
 // A diagonal unit normal rounded to float. Its self-dot is one ULP above 1.
 const float a=0x1.6a09fap-1f, b=0x1.6a09d6p-1f;
 const __m128 n=_mm_set_ps(0,b,0,a);
 const float cosine=_mm_cvtss_f32(_mm_dp_ps(n,n,0xff));
 if(cosine!=1.00000011920928955078125f) return 2;
 int groups=1;
 for(int i=1;i<64;++i) {
   const double radians=angle(cosine);
   if(!std::isfinite(radians) || radians>0.4) ++groups;
 }
 if(groups!=1) { std::fprintf(stderr,"duplicate normals created %d groups; expected 1\n",groups); return 1; }
 for(double input: {1.0000001192092896, -1.0000001192092896,
                    1.0000004768371582, -1.0000004768371582}) {
   if(angle(input)!=(input>0 ? 0.0 : std::acos(-1.0))) return 3;
 }
 for(double input: {-1.0,-0.95,-0.5,-0.0,0.0,0.5,0.95,1.0}) {
   if(angle(input)!=std::acos(input)) return 4;
 }
 for(double input: {1.000001,-1.000001,2.0,-2.0,
                    std::numeric_limits<double>::infinity(),
                    -std::numeric_limits<double>::infinity(),
                    std::numeric_limits<double>::quiet_NaN()}) {
   if(!std::isnan(angle(input))) return 5;
 }
 std::puts("geometry cosine regression passed");
}
'''.replace('BODY', body).replace('#include <immintrin.h>',
                                '#include <immintrin.h>\n#include <initializer_list>')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, executable = root / 'probe.cpp', root / 'probe.exe'
            source.write_text(program)
            subprocess.run([os.environ['FNR3_GEOMETRY_CXX'], '/nologo', '/std:c++20',
                            '/EHsc', '/O2', '/arch:AVX', str(source), '/Fe:' + str(executable),
                            '/Fo:' + str(root / 'probe.obj')], check=True, timeout=120)
            result = subprocess.run([str(executable)], capture_output=True, text=True,
                                    timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
