"""Execute generated CAC actions against the original profile-writer boundary.

Project work: djultra64. Tests do not run a game or write a user's profile.
"""
from pathlib import Path
import struct
import unittest

from test_frontend_overrides import NativeVM, ROOT, m


CAC = 'assets/gui/fn2k6/screengroups/cac/cac.big'


class BoxerVM(NativeVM):
    """Retail CAC opcode subset plus deterministic external APT services."""
    def __init__(self, data, constants, original):
        super().__init__(data, constants)
        self.root = {'dummyEventHandler': 'dummy'}
        self.globals.update(cac={'m_OldBoxer': 0, 'm_screen': {'m_filmStrip': 'film'}},
            CFeCreateBoxerApt='boxer', CFePlayerManagerApt='players',
            gSM='screens', gEH='events', gStdPopup='popup', gPflPopup='profilePopup',
            gNetPopupAllowed=True, gNetPopupInAutosave=False)
        self.regs[1] = self.globals
        self.roster_result, self.save_status, self.accept_save = 0, 0, True
        self.requests, self.popups = [], []
        self.pool = []
        field = m.align4(0xffb4 + 1)
        count, pointer = m.u32(original, field), m.u32(original, field + 4)
        self.pool = [m.u32(original, pointer + i * 4) for i in range(count)]

    def constant(self, index):
        table = m.u32(self.constants, 28)
        kind, value = struct.unpack_from('>II', self.constants, table + index * 8)
        if kind == 1: return m.cstring(self.constants, value)
        if kind == 4: return self.regs[value]
        if kind == 8: return self.constant(self.pool[value])
        if kind == 7: return struct.unpack('>i', struct.pack('>I', value))[0]
        raise AssertionError(f'unexpected retail constant type {kind}')

    def variable(self, name):
        return self.root if name == '_root' else self.globals.get(name, self.root.get(name))

    def method(self, obj, name, args):
        if obj == 'host':
            self.calls.append((obj, name, args))
            if name == 'PortGetEditedSaveStatus': return self.save_status
            if name == 'PortSaveEditedProfile':
                self.requests.append(args)
                if not self.accept_save: return 0
                self.save_status = 1
                return 1
            raise AssertionError(f'unexpected host method {name}')
        if obj == 'boxer' and name == 'SaveBoxerToRoster':
            self.calls.append((obj, name, args)); return self.roster_result
        if obj == 'popup' and name == 'show': self.popups.append(args)
        return super().method(obj, name, args)

    def run(self, start, end, stop=None):
        actions = {a.offset: a for a in m.decode_actions(self.data, start, end)}
        pc = start
        for _ in range(4000):
            if pc == end or pc == stop: return pc
            a = actions[pc]; op = a.opcode; s = self.stack
            value = lambda: m.u32(self.data, m.align4(pc + 1))
            if op == 0x71: s.append(self.globals)
            elif op == 0xa1: s.append(m.cstring(self.data, value()))
            elif op in (0xa2, 0xa3):
                index = self.data[pc + 1] if op == 0xa2 else struct.unpack_from('>H', self.data, pc + 1)[0]
                s.append(self.constant(self.pool[index]))
            elif op == 0xb5: s.append(struct.unpack_from('b', self.data, pc + 1)[0])
            elif op in (0x59, 0x5a, 0x73, 0x74, 0x75, 0x76):
                s.append({0x59: 0, 0x5a: 1, 0x73: True, 0x74: False, 0x75: None, 0x76: None}[op])
            elif op == 0x96:
                field = m.align4(pc + 1); count = m.u32(self.data, field); pointer = m.u32(self.data, field + 4)
                s.extend(self.constant(m.u32(self.data, pointer + i * 4)) for i in range(count))
            elif op == 0x1c: s.append(self.variable(s.pop()))
            elif op == 0xae: s.append(self.variable(self.constant(self.pool[self.data[pc + 1]])))
            elif op in (0x4e, 0xaf):
                key = s.pop() if op == 0x4e else self.constant(self.pool[self.data[pc + 1]])
                obj = s.pop(); s.append(obj.get(key) if isinstance(obj, dict) else None)
            elif op == 0x4f:
                val, key, obj = s.pop(), s.pop(), s.pop(); obj[key] = val
            elif op == 0x3a:
                key, obj = s.pop(), s.pop(); s.append(obj.pop(key, None) is not None)
            elif op == 0x47:
                right, left = s.pop(), s.pop()
                s.append(str(left) + str(right) if isinstance(left, str) or isinstance(right, str) else left + right)
            elif op in (0x49, 0x66): s.append(s.pop() == s.pop())
            elif op == 0x12: s.append(not s.pop())
            elif op == 0x18: s.append(int(s.pop()))
            elif op in (0x17, 0x26): s.pop()
            elif op in (0x52, 0xb2):
                name = s.pop() if op == 0x52 else self.constant(self.pool[self.data[pc + 1]])
                obj, count = s.pop(), s.pop(); result = self.method(obj, name, [s.pop() for _ in range(count)])
                if op == 0x52: s.append(result)
            elif op in (0x9b, 0x8e): s.append((a.body, a.end))
            elif op == 0x9d:
                if s.pop(): pc = a.target; continue
            elif op == 0x99: pc = a.target; continue
            elif op == 0x3e: s.pop(); return pc
            elif op == 0: return pc
            else: raise AssertionError(f'unsupported CAC action {op:x} at {pc:x}')
            pc = a.end
        raise AssertionError('CAC action did not terminate')

    def invoke(self, name):
        self.run(*self.globals['cac'][name])

    def callback(self, status, success=True):
        self.save_status = status
        callback = self.root['carSuccessCB' if success else 'carFailureCB']
        self.run(*callback)

    def names(self): return [name for _, name, _ in self.calls]


class BoxerProfileSave(unittest.TestCase):
    def movie(self):
        self.assertTrue(callable(getattr(m, 'patch_cac', None)),
            'confirmed boxer saving must generate a CAC APT override')
        entries = {e.name: e.payload for e in m.parse_big((ROOT / CAC).read_bytes())}
        data = m.patch_cac(entries['cac.apt'], entries['cac.const'])
        report = m.inspect_cac_patch(data, entries['cac.const'])
        vm = BoxerVM(data, entries['cac.const'], entries['cac.apt'])
        vm.run(report['definitions_start'], report['script_end'])
        vm.globals['cac']['fxnSave'] = (report['save_body'], report['save_end'])
        return entries, data, report, vm

    def test_confirm_waits_for_storage_callback_and_uses_class_owned_helpers(self):
        _, _, _, vm = self.movie()
        vm.invoke('fxnSave')
        self.assertEqual(vm.names().count('SaveBoxerToRoster'), 1)
        self.assertEqual(len(vm.requests), 1)
        self.assertNotIn('goBackScreen', vm.names())
        self.assertNotIn('animateOut', vm.names())
        self.assertEqual(vm.root['carSuccessCB'], vm.globals['cac']['_fnr3RequiredSaveSucceeded'])
        self.assertEqual(vm.requests[0], [vm.root['carSuccessCB'], vm.root['carFailureCB']])
        self.assertFalse(vm.globals['gNetPopupAllowed'])
        self.assertTrue(vm.globals['gNetPopupInAutosave'])
        self.assertIn(('events', 'setLocalEventHandler', ['dummy']), vm.calls)
        self.assertFalse(any(key.startswith('_fnr3') for key in vm.globals))
        vm.callback(2)
        self.assertEqual(vm.names().count('goBackScreen'), 1)
        self.assertEqual([name for name in vm.names() if name in ('animateOut', 'SetCacMode', 'UpdateTBlends', 'goBackScreen')],
            ['animateOut', 'SetCacMode', 'UpdateTBlends', 'goBackScreen'])
        self.assertIn(('boxer', 'SetCacMode', [255]), vm.calls)
        self.assertIsNone(vm.root['carSuccessCB'])
        self.assertIsNone(vm.root['carFailureCB'])
        self.assertTrue(vm.globals['gNetPopupAllowed'])
        self.assertFalse(vm.globals['gNetPopupInAutosave'])

    def test_duplicate_save_and_callback_cannot_repeat_roster_or_navigation(self):
        _, _, _, vm = self.movie()
        vm.invoke('fxnSave'); vm.invoke('fxnSave'); vm.invoke('_fnr3BeginRequiredSave')
        self.assertEqual(vm.names().count('SaveBoxerToRoster'), 1)
        self.assertEqual(len(vm.requests), 1)
        callback = vm.root['carSuccessCB']
        vm.callback(2); vm.run(*callback)
        self.assertEqual(vm.names().count('goBackScreen'), 1)

    def test_roster_failure_keeps_original_error_and_never_starts_profile_save(self):
        _, _, _, vm = self.movie(); vm.roster_result = 1
        vm.invoke('fxnSave')
        self.assertEqual(vm.requests, [])
        self.assertNotIn('goBackScreen', vm.names())
        self.assertIn('$1324', vm.popups[-1])

    def test_failed_storage_retry_does_not_commit_a_new_boxer_twice(self):
        _, _, _, vm = self.movie(); vm.globals['cac']['m_OldBoxer'] = 0
        vm.invoke('fxnSave'); vm.callback(3, success=False)
        self.assertNotIn('goBackScreen', vm.names())
        popup = vm.popups[-1]
        self.assertEqual(popup[:2], ['fnr3RequiredProfile', 'w'])
        self.assertEqual(popup[4:7], [2, 0, 'RETRY'])
        self.assertEqual(popup[9], 'CONTINUE WITHOUT SAVING')
        self.assertIsNone(vm.root['carSuccessCB'])
        vm.run(*popup[7])
        self.assertEqual(vm.names().count('SaveBoxerToRoster'), 1)
        self.assertEqual(len(vm.requests), 2)
        vm.callback(2)
        self.assertEqual(vm.names().count('goBackScreen'), 1)

    def test_rejected_or_unverified_success_never_claims_saved(self):
        for accepted, status in [(False, 0), (True, 0), (True, 3)]:
            with self.subTest(accepted=accepted, status=status):
                _, _, _, vm = self.movie(); vm.accept_save = accepted
                vm.invoke('fxnSave')
                if accepted: vm.callback(status)
                self.assertNotIn('goBackScreen', vm.names())
                self.assertEqual(vm.popups[-1][6], 'RETRY')

    def test_next_new_or_edit_in_same_group_can_save_after_terminal_success(self):
        for entry, old_boxer in [('fresh_new', 0), ('fresh_edit', 1)]:
            with self.subTest(entry=entry):
                _, _, report, vm = self.movie()
                self.assertIn(entry + '_body', report, 'fresh boxer entry must reset completed save state')
                vm.invoke('fxnSave'); old_success = vm.root['carSuccessCB']; vm.callback(2)
                vm.run(report[entry + '_body'], report[entry + '_end'])
                self.assertEqual(vm.globals['cac']['m_OldBoxer'], old_boxer)
                vm.run(*old_success)
                self.assertEqual(vm.names().count('goBackScreen'), 1)
                vm.invoke('fxnSave')
                self.assertEqual(len(vm.requests), 2)
                self.assertEqual(vm.names().count('SaveBoxerToRoster'), 2)
                vm.callback(2)
                self.assertEqual(vm.names().count('goBackScreen'), 2)

    def test_late_callbacks_cannot_interrupt_a_pending_second_edit(self):
        _, _, report, vm = self.movie()
        self.assertIn('fresh_edit_body', report, 'fresh edit must reset only terminal state')
        vm.invoke('fxnSave')
        old_callbacks = [vm.root['carSuccessCB'], vm.root['carFailureCB']]
        vm.callback(2)
        vm.run(report['fresh_edit_body'], report['fresh_edit_end']); vm.invoke('fxnSave')
        for callback in old_callbacks: vm.run(*callback)
        self.assertEqual(vm.popups, [])
        self.assertEqual(vm.globals['cac']['_fnr3RequiredSaveState'], 1)
        self.assertEqual(vm.names().count('goBackScreen'), 1)
        vm.callback(2)
        self.assertEqual(vm.names().count('goBackScreen'), 2)

    def test_explicit_continue_can_exit_after_failure_without_a_second_save(self):
        _, _, _, vm = self.movie()
        vm.invoke('fxnSave'); vm.callback(3, success=False)
        vm.run(*vm.popups[-1][10])
        self.assertEqual(len(vm.requests), 1)
        self.assertEqual(vm.names().count('SaveBoxerToRoster'), 1)
        self.assertEqual(vm.names().count('goBackScreen'), 1)
        self.assertIsNone(vm.root['carFailureCB'])

    def test_discard_and_cancel_keep_original_paths_without_profile_writes(self):
        for method in ('discard', 'cancel'):
            _, _, report, vm = self.movie()
            vm.run(report[method + '_body'], report[method + '_end'])
            self.assertEqual(vm.requests, [])
            self.assertNotIn('SaveBoxerToRoster', vm.names())
            self.assertEqual(vm.names().count('goBackScreen'), int(method == 'discard'))

    def test_stale_callback_after_unload_does_not_change_the_next_screen(self):
        _, _, _, vm = self.movie()
        vm.invoke('fxnSave'); callback = vm.root['carSuccessCB']
        del vm.globals['cac']; vm.save_status = 2
        vm.run(*callback)
        self.assertNotIn('goBackScreen', vm.names())
        self.assertIsNone(vm.root['carSuccessCB'])
        self.assertIsNone(vm.root['carFailureCB'])

    def test_clone_is_loader_safe_and_preserves_unconfirmed_and_error_bytes(self):
        entries, data, report, _ = self.movie()
        result = m.validate_constant_fixups(data, entries['cac.const'], report['script_start'], report['script_end'])
        self.assertGreater(result['constant_arrays'], 1)
        original = entries['cac.apt']
        self.assertEqual(data[0xffb4:0x12e0f], original[0xffb4:0x12e0f])
        for start, end, key in [(0x11020, 0x11030, 'cancel'), (0x1105c, 0x110ac, 'discard')]:
            self.assertEqual(data[report[key + '_body']:report[key + '_end']], original[start:end])
        with self.assertRaises(ValueError): m.patch_cac(data, entries['cac.const'])


if __name__ == '__main__': unittest.main()
