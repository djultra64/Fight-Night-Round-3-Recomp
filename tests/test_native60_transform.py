"""Project-authored transform contracts. Project work: djultra64."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native60', ROOT / 'tools/port-build/native60_transform.py')
native60 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native60)


class TransformTests(unittest.TestCase):
    def test_exact_cardinality_rejects_generator_drift(self):
        with self.assertRaises(ValueError):
            native60.replace_exact('x x', 'x', 'y', 1)

    def test_missing_functions_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'input').mkdir()
            with self.assertRaises(ValueError):
                native60.transform(root / 'input', root / 'output')
            self.assertFalse((root / 'output').exists())

    def test_patched_input_rejected(self):
        with self.assertRaises(ValueError):
            native60.patch_function('8226E838', 'Fnr3Native60Begin(base);')

    def test_gameplay_hook_follows_final_guest_clock_write(self):
        body = '\tREX_STORE_U32(ctx.r3.u32 + 484, ctx.r11.u32);\n\treturn;'
        patched = native60.patch_function('82265A20', body)
        self.assertLess(patched.index('REX_STORE_U32'), patched.index('Fnr3Native60End'))
        self.assertLess(patched.index('Fnr3Native60End'), patched.index('return;'))

    def test_replay_begin_runs_before_register_restore(self):
        body = '\t// lwz r31,8(r3)\n\t// addi r1,r1,112\n\treturn;'
        patched = native60.patch_function('821A3D78', body)
        self.assertLess(patched.index('Fnr3ReplaySequenceBegin(base,ctx.r31.u32)'),
                        patched.index('// addi r1'))

    def test_tick_scales_two_callbacks_but_only_countdown_decrement(self):
        body = ('\tuint32_t ea{};\n'
                '\t// lwz r11,44(r31)\n'
                '\tsub_82255148(ctx, base);\n'
                '\t// lwz r11,44(r31)\n'
                'ctx.r11.s64 = ctx.r11.s64 + -1;\n'
                '\tsub_82255148(ctx, base);\n'
                'ctx.r11.s64 = ctx.r11.s64 + -1;\n'
                'ctx.f0.f64 = double(float(ctx.f13.f64 + ctx.f0.f64));')
        patched = native60.patch_function('822552E8', body)
        self.assertEqual(patched.count('ctx.f1.f64 * fnr3_replay_scale'), 2)
        self.assertEqual(patched.count('Fnr3ReplayCountdown('), 1)
        self.assertEqual(patched.count('ctx.r11.s64 = ctx.r11.s64 + -1;'), 1)
        self.assertIn('ctx.f13.f64 + ctx.f0.f64 * fnr3_replay_scale', patched)
        with self.assertRaises(ValueError):
            native60.patch_function('822552E8', body.replace('sub_82255148', 'sub_other', 1))

    def test_crowd_preserves_first_store_and_updates_only_elapsed_store(self):
        store = 'temp.f32 = float(ctx.f0.f64);\n\tREX_STORE_U32(ctx.r31.u32 + 832, temp.u32);'
        body = ('\tuint32_t ea{};\n' + store + '\n'
                '\tif (!ctx.cr6.gt) goto loc_82223340;\n' + store + '\n'
                'ctx.r11.s64 = ctx.r11.s64 + 2;')
        patched = native60.patch_function('82223260', body)
        self.assertEqual(patched.count(store), 1)
        self.assertLess(patched.index(store), patched.index('AdvanceCrowd('))
        self.assertIn('temp.f32 = fnr3_crowd.remainder', patched)
        self.assertIn('ctx.r11.s64 + fnr3_crowd.samples', patched)

    def test_phase_restore_and_replay_apply_bracket_stock_selection(self):
        body = ('\tREX_FUNC_PROLOGUE();\n'
                '\tREX_STORE_U32(ctx.r3.u32 + 484, ctx.r11.u32);\n'
                '\t// addi r1,r1,96\n\treturn;')
        patched = native60.patch_function('8226E838', body)
        self.assertLess(patched.index('Fnr3Native60Begin'), patched.index('REX_STORE_U32'))
        self.assertLess(patched.index('REX_STORE_U32'), patched.index('Fnr3ReplayPhaseEnd'))
        self.assertNotIn('Fnr3Native60End', patched)

    def test_duplicate_function_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('fnr3_recomp.0.cpp', 'fnr3_recomp.1.cpp'):
                (root / name).write_text('DEFINE_REX_FUNC(sub_8226E838) {\n}\n')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                native60.find_units(root)

    def test_safely_reruns_from_original_without_touching_input(self):
        # A purpose-written skeletal function, not generated original game code.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, output = root / 'input', root / 'output'
            source.mkdir()
            body = ('DEFINE_REX_FUNC(sub_82265A20) {\n'
                    '\tREX_STORE_U32(ctx.r3.u32 + 484, ctx.r11.u32);\n\treturn;\n}\n')
            path = source / 'fnr3_recomp.0.cpp'
            path.write_text(body)
            from unittest.mock import patch
            with patch.object(native60, 'TARGETS', ('82265A20',)):
                native60.transform(source, output)
                transformed = (output / path.name).read_bytes()
                before = (output / path.name).stat().st_mtime_ns
                native60.transform(source, output)
                self.assertEqual((output / path.name).read_bytes(), transformed)
                self.assertEqual((output / path.name).stat().st_mtime_ns, before)
                self.assertEqual(path.read_text(), body)
                with self.assertRaises(ValueError):
                    native60.transform(source, source)


if __name__ == '__main__':
    unittest.main()
