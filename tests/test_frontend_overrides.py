"""Structural native menu tests; never start a game process."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('frontend_overrides', ROOT / 'tools/frontend_overrides.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


def archive():
    data = bytearray(b'BIGF' + struct.pack('<I', 64) + struct.pack('>II', 1, 32))
    data += struct.pack('>II', 32, 4) + b'a\0'
    data += bytes(32 - len(data)) + b'data' + bytes(28)
    return bytes(data)


class NativeVM:
    """Executes injected VM actions against native-menu and host callback fakes."""
    def __init__(self, data, constants):
        self.data, self.constants = data, constants
        self.stack, self.calls, self.rows = [], [], []
        self.selected, self.values, self.status = 0, [2, 1, 0, 3, 0], 1
        self.family,self.bindings=1,list(range(14))
        self.globals = {'AptTaskMessages': 'host', 'options': {'m_screen': {
            'm_title': 'title', 'mainControl': {'mainMenu': 'menu'}}, 'm_class': 'class'},
            'gStdHelp': 'help', 'gHlpPopup': 'helpPopup', 'gFM': 'focus',
            'INPUTCODE': {k: i for i, k in enumerate(('ADVANCE', 'CANCEL', 'CIRCLE', 'BACK', 'LEFT', 'RIGHT', 'UP', 'DOWN'))}}
        self.regs = {7: 0, 8: 0}
        self.functions = {}
        self.retail_rows = None
        self.native_title,self.native_handler=None,None
        self.signed_in,self.game_mode=False,0

    def method(self, obj, name, args):
        self.calls.append((obj, name, args))
        if obj == 'host':
            if name == 'PortGraphicsEvent':
                command = args[0]
                if 10 <= command < 15: self.values[command-10] = (self.values[command-10]-1) % len(m.GRAPHICS_CHOICES[command-10][1])
                if 20 <= command < 25: self.values[command-20] = (self.values[command-20]+1) % len(m.GRAPHICS_CHOICES[command-20][1])
                return self.status
            if name=='PortGetActiveFamily':return self.family
            if name=='PortGetBinding':return self.bindings[args[0]]
            return self.values[list(m.GRAPHICS_CALLBACKS[1:6]).index(name)]
        if obj=='title' and name=='setText':self.native_title=args[0]
        if obj=='class' and name=='mainInitGui' and self.retail_rows is not None:
            # Retail's verified initializer appends, then sets title, selected
            # context and handler. It relies on its caller for a fresh list.
            rows=self.retail_rows
            self.rows.extend(['GRAPHICS']+rows[:5]+
                ([rows[5],rows[6] if self.game_mode==4 else rows[7]] if self.signed_in else [])+rows[-1:])
            self.native_title='$2300'
            self.selected=0
            self.native_handler='retail_mainEventHandler'
        if obj == 'menu':
            if name == 'clearMenu': self.rows.clear()
            if name == 'addElement': self.rows.append(args[0])
            if name == 'getSelectedIndex': return self.selected
            if name == 'setSelectedIndex': self.selected = args[0]
        if obj is self.globals and name in self.functions:
            self.run(*self.functions[name])
        return None

    def run(self, start, end, stop=None):
        actions = {a.offset: a for a in m.decode_actions(self.data, start, end)}
        pc = start
        for _ in range(3000):
            if pc == stop or pc == end: return pc
            a = actions[pc]; op = a.opcode; stack = self.stack
            if op == 0x71: stack.append(self.globals)
            elif op == 0xa1: stack.append(m.cstring(self.data,m.u32(self.data,m.align4(pc+1))))
            elif op == 0xb5: stack.append(struct.unpack_from('b',self.data,pc+1)[0])
            elif op == 0x59: stack.append(0)
            elif op == 0x76: stack.append(None)
            elif op == 0x96:
                field=m.align4(pc+1); pointer=m.u32(self.data,field+4)
                index=m.u32(self.data,pointer); reg=m.u32(self.constants,36+index*8)
                stack.append(self.regs[reg])
            elif op == 0x87: self.regs[m.u32(self.data,m.align4(pc+1))]=stack[-1]
            elif op == 0x4e:
                key,obj=stack.pop(),stack.pop();stack.append(obj.get(key) if isinstance(obj,dict) else obj[key])
            elif op == 0x4f:
                value,key,obj=stack.pop(),stack.pop(),stack.pop();obj[key]=value
                if isinstance(value,tuple): self.functions[key]=value
            elif op == 0x42:
                count=stack.pop();stack.append([stack.pop() for _ in range(count)])
            elif op == 0x47:
                right,left=stack.pop(),stack.pop();stack.append(left+right)
            elif op == 0x66: stack.append(stack.pop()==stack.pop())
            elif op == 0x12: stack.append(not stack.pop())
            elif op == 0x51: stack.append(stack.pop()-1)
            elif op == 0x18: stack.append(int(stack.pop()))
            elif op == 0x17: stack.pop()
            elif op == 0x52:
                name,obj,count=stack.pop(),stack.pop(),stack.pop()
                args=[stack.pop() for _ in range(count)]
                stack.append(self.method(obj,name,args))
            elif op == 0xb0:
                if self.data[pc+1] != 60: raise AssertionError('unexpected scoped native function')
                count=stack.pop();args=[stack.pop() for _ in range(count)]
                self.calls.append(('scope','playSound',args))
            elif op == 0x9b: stack.append((a.body,a.end))
            elif op == 0x9d:
                if stack.pop(): pc=a.target;continue
            elif op == 0x99: pc=a.target;continue
            elif op == 0x3e: stack.pop(); return pc
            elif op == 0: return pc
            else: raise AssertionError(f'unsupported injected action {op:x} at {pc:x}')
            pc=a.end
        raise AssertionError('injected script did not terminate')


class FrontendOverrides(unittest.TestCase):
    def test_archive_roundtrip_and_untouched_prefix(self):
        original = archive()
        self.assertEqual(m.replace_big(original, {}), original)
        patched = m.replace_big(original, {'a': b'long replacement'})
        self.assertEqual(m.parse_big(patched)[0].payload, b'long replacement')
        self.assertEqual(patched[32:64], original[32:64])
        self.assertEqual(struct.unpack_from('<I', patched, 4)[0], len(patched))

    def test_reject_corrupt_archives(self):
        for data in (b'', archive()[:30], b'NOPE' + archive()[4:]):
            with self.assertRaises(ValueError):
                m.parse_big(data)
        bad = bytearray(archive()); struct.pack_into('>I', bad, 16, 999)
        with self.assertRaises(ValueError): m.parse_big(bytes(bad))
        with self.assertRaises(ValueError): m.replace_big(archive(), {'missing': b'x'})

    def test_constant_patch_preserves_indices_and_old_storage(self):
        data = b'Apt constant file\x1a\0\0' + struct.pack('>III', 20, 1, 32)
        data += struct.pack('>II', 1, 40) + b'original\0'
        patched = m.patch_constants(data, {0: ('original', 'extended')})
        self.assertEqual(m.constant_strings(patched), {0: 'extended'})
        self.assertEqual(patched[40:49], b'original\0')
        with self.assertRaises(ValueError): m.patch_constants(data, {0: ('wrong', 'x')})
        with self.assertRaises(ValueError): m.constant_strings(data[:-1])

    def test_retail_destructive_loader_fixup_never_reuses_array_slots(self):
        for path, stem, patch, inspect, marker in [
            (m.MAIN_MENU, 'mainmenu', m.patch_main_menu, m.inspect_main_menu_patch, b'FNR3_PORT_MAIN_MENU_V1\0'),
            (m.OPTIONS, 'options', m.patch_options, m.inspect_options_patch, b'FNR3_PORT_OPTIONS_V1\0')]:
            entries = {e.name: e.payload for e in m.parse_big((ROOT / path).read_bytes())}
            patched = patch(entries[stem + '.apt'])
            inspect(patched)
            metadata = patched.rfind(marker) + len(marker)
            start, size = struct.unpack_from('>II', patched, metadata)
            m.validate_constant_fixups(patched, entries[stem + '.const'], start, start + size)

    def test_cloned_class_scripts_end_before_metadata(self):
        for path, stem, patch, inspect, marker, original_end in [
            (m.MAIN_MENU, 'mainmenu', m.patch_main_menu, m.inspect_main_menu_patch,
             b'FNR3_PORT_MAIN_MENU_V1\0', 0xdf4b),
            (m.OPTIONS, 'options', m.patch_options, m.inspect_options_patch,
             b'FNR3_PORT_OPTIONS_V1\0', 0x1453c)]:
            original = next(e.payload for e in m.parse_big((ROOT / path).read_bytes())
                            if e.name == stem + '.apt')
            self.assertEqual(original[original_end], 0)
            patched = patch(original)
            location = patched.rfind(marker)
            self.assertEqual(patched[location - 1], original[original_end],
                             'native interpreter must stop before metadata')
            # A valid non-END opcode is still unsafe, even when all decoded
            # branch destinations and metadata lengths remain consistent.
            broken = bytearray(patched)
            broken[location - 1] = 0x17
            with self.assertRaisesRegex(ValueError, 'END'):
                inspect(bytes(broken))

    def test_native_quit_dispatch_preserves_original_six_items(self):
        original = next(e.payload for e in m.parse_big((ROOT / m.MAIN_MENU).read_bytes()) if e.name == 'mainmenu.apt')
        patched = m.patch_main_menu(original)
        report = m.inspect_main_menu_patch(patched)
        start = m.u32(patched, 0x4320)
        actions = {a.offset: a for a in m.decode_actions(patched, start, patched.rfind(b'FNR3_PORT_MAIN_MENU_V1\0'))}
        for selected in range(7):
            stack, calls, pc, returned = [], [], report['handler'], False
            for _ in range(30):
                if pc == report['resume']: break
                action = actions[pc]; op = action.opcode
                if op == 0x96: stack.append(selected)
                elif op == 0xb5: stack.append(patched[pc + 1])
                elif op == 0x59: stack.append(0)
                elif op == 0x66: stack.append(stack.pop() == stack.pop())
                elif op == 0x12: stack.append(not stack.pop())
                elif op == 0x9d:
                    if stack.pop(): pc = action.target; continue
                elif op == 0x71: stack.append({'AptTaskMessages': 'tasks'})
                elif op in (0xa1, 0xa5):
                    value = m.cstring(patched, m.u32(patched, m.align4(pc + 1)))
                    stack.append(stack.pop()[value] if op == 0xa5 else value)
                elif op == 0x5d:
                    method, obj, argc = stack.pop(), stack.pop(), stack.pop()
                    calls.append((obj, method, argc))
                elif op == 0x76: stack.append(None)
                elif op == 0x3e: returned = True; break
                else: self.fail(f'unexpected Quit dispatch opcode {op:x}')
                pc = action.end
                if pc == report['resume']: break
            self.assertEqual(calls, [('tasks', 'Quit', 0)] if selected == 6 else [])
            self.assertEqual(returned, selected == 6)
            if selected < 6:
                self.assertEqual(pc, report['resume'])
                self.assertEqual(stack, [])
        # The original continuation is byte-identical; no register rewrite or
        # replacement of any original item selector occurs on the 0..5 path.
        self.assertEqual(patched[report['resume']:report['resume'] + 64], original[0xce55:0xce55 + 64])

    def graphics_movie(self):
        entries={e.name:e.payload for e in m.parse_big((ROOT/m.OPTIONS).read_bytes())}
        data=m.patch_options(entries['options.apt']); report=m.inspect_options_patch(data)
        vm=NativeVM(data,entries['options.const'])
        vm.functions['_fnr3GraphicsRefresh']=(report['refresh_body'], report['refresh_end'])
        return data,report,vm

    def test_native_graphics_dispatch_preserves_original_selection(self):
        for selected in range(10):
            data,report,vm=self.graphics_movie();vm.regs[7]=selected
            pc=vm.run(report['graphics_dispatch'], report['script_end'], report['retail_resume'])
            events=[args for obj,name,args in vm.calls if name=='PortGraphicsEvent']
            self.assertEqual(events, [[0]] if selected==0 else [])
            if selected:
                self.assertEqual(vm.regs[7],selected-1)
                self.assertEqual(pc,report['retail_resume'])
            else:
                self.assertEqual(vm.rows[:2],['RESOLUTION: 1920 X 1080','FULLSCREEN: ON'])
                self.assertEqual(len(vm.rows),8)
                self.assertEqual(vm.selected,0)
            self.assertEqual(vm.stack,[])

    def test_native_page_navigation_owns_selection_without_focus_manager(self):
        for page in range(4):
            count=8
            for key,step in [('UP',-1),('DOWN',1)]:
                for selection in range(count):
                    data,report,vm=self.graphics_movie()
                    vm.globals.update(_fnr3GraphicsActive=1,_fnr3GraphicsPage=page,_fnr3GraphicsStatus=0)
                    vm.selected=selection;vm.regs[8]=vm.globals['INPUTCODE'][key]
                    vm.run(report['event_handler'],report['event_end'])
                    self.assertEqual(vm.selected,(selection+step)%count)
                    self.assertEqual(len(vm.rows),count)
                    self.assertFalse(any(obj=='focus' for obj,name,args in vm.calls))
                    self.assertEqual(vm.stack,[])

    def test_native_save_restart_is_distinct_and_failure_stays_open(self):
        for status in (0,1):
            data,report,vm=self.graphics_movie();vm.status=status
            vm.globals.update(_fnr3GraphicsActive=1,_fnr3GraphicsPage=0,_fnr3GraphicsStatus=0)
            vm.selected=7;vm.regs[8]=vm.globals['INPUTCODE']['ADVANCE']
            vm.run(report['event_handler'],report['event_end'])
            self.assertIn(('host','PortGraphicsEvent',[3]),vm.calls)
            self.assertEqual(vm.selected,7)
            self.assertEqual(len(vm.rows),8)
            self.assertEqual(vm.rows[7],'SAVE AND RESTART')
            self.assertNotIn('BACK',vm.rows)
            self.assertTrue(any(name=='setHelp' and 't,BACK' in args[0] for _,name,args in vm.calls))
            self.assertEqual(vm.globals['_fnr3GraphicsActive'],1)
            if status==0:self.assertIn('COULD NOT SAVE - TRY AGAIN',vm.rows)

    def test_native_graphics_edit_save_back_and_read_only(self):
        for key,selection,commands in [('LEFT',0,[10]),('RIGHT',4,[24]),('ADVANCE',2,[22]),
                ('ADVANCE',6,[2]),('ADVANCE',7,[3]),('CANCEL',3,[1]),('RIGHT',7,[])]:
            data,report,vm=self.graphics_movie();vm.globals['_fnr3GraphicsActive']=1
            vm.globals['_fnr3GraphicsStatus']=0;vm.selected=selection
            vm.regs[8]=vm.globals['INPUTCODE'][key]
            vm.run(report['event_handler'],report['event_end'])
            self.assertEqual([args[0] for obj,name,args in vm.calls if name=='PortGraphicsEvent'],commands)
            if commands and commands[0]>=10:self.assertEqual(vm.selected,selection)
            if commands==[1]:
                self.assertEqual(vm.globals['_fnr3GraphicsActive'],0)
                self.assertIn(('class','mainInitGui',[]),vm.calls)
            if commands==[2]:self.assertIn('SAVED - RESTART REQUIRED',vm.rows)
            self.assertEqual(vm.stack,[])
        data,report,vm=self.graphics_movie();vm.status=0;vm.selected=6
        vm.globals['_fnr3GraphicsActive']=1;vm.regs[8]=vm.globals['INPUTCODE']['ADVANCE']
        vm.run(report['event_handler'],report['event_end'])
        self.assertIn('COULD NOT SAVE - TRY AGAIN',vm.rows)

    def test_native_mapping_family_labels_and_draft_navigation(self):
        for family, expected in [(1,'CONFIRM / PRIMARY: A'),(2,'CONFIRM / PRIMARY: CROSS'),(3,'CONFIRM / PRIMARY: B')]:
            data,report,vm=self.graphics_movie()
            vm.family=family;vm.bindings=list(range(14));vm.selected=5
            vm.globals['_fnr3GraphicsActive']=1;vm.globals['_fnr3GraphicsStatus']=0
            vm.regs[8]=vm.globals['INPUTCODE']['ADVANCE']
            vm.run(report['event_handler'],report['event_end'])
            self.assertEqual(vm.rows[0],expected)
            self.assertEqual(len(vm.rows),8)
            self.assertEqual(vm.rows[-3:],['PREVIOUS PAGE','NEXT PAGE','BACK'])
            vm.selected=0;vm.regs[8]=vm.globals['INPUTCODE']['RIGHT']
            vm.run(report['event_handler'],report['event_end'])
            self.assertIn(('host','PortGraphicsEvent',[200]),vm.calls)
            vm.globals['_fnr3GraphicsPage']=3;vm.selected=4;vm.regs[8]=vm.globals['INPUTCODE']['ADVANCE']
            vm.run(report['event_handler'],report['event_end'])
            self.assertIn(('host','PortGraphicsEvent',[300]),vm.calls)
            vm.regs[8]=vm.globals['INPUTCODE']['CANCEL']
            vm.run(report['event_handler'],report['event_end'])
            self.assertEqual(vm.globals['_fnr3GraphicsActive'],1)
            self.assertEqual(vm.selected,5)
            self.assertIn('BUTTON MAPPING',vm.rows)

    def test_native_mapping_all_commands_and_page_limits(self):
        for direction,base in [('LEFT',100),('RIGHT',200)]:
            for action in range(14):
                data,report,vm=self.graphics_movie()
                vm.globals.update(_fnr3GraphicsActive=1,_fnr3GraphicsPage=action//5+1,_fnr3GraphicsStatus=1)
                vm.selected=action%5;vm.regs[8]=vm.globals['INPUTCODE'][direction]
                vm.run(report['event_handler'],report['event_end'])
                self.assertIn(('host','PortGraphicsEvent',[base+action]),vm.calls)
                self.assertEqual(len(vm.rows),8)
                self.assertEqual(vm.selected,action%5)
                self.assertEqual(vm.globals['_fnr3GraphicsStatus'],0)
        for page,selection,expected in [(1,5,1),(1,6,2),(2,5,1),(2,6,3),(3,6,3)]:
            data,report,vm=self.graphics_movie()
            vm.globals.update(_fnr3GraphicsActive=1,_fnr3GraphicsPage=page,_fnr3GraphicsStatus=0)
            vm.selected=selection;vm.regs[8]=vm.globals['INPUTCODE']['ADVANCE']
            vm.run(report['event_handler'],report['event_end'])
            self.assertEqual(vm.globals['_fnr3GraphicsPage'],expected)
            self.assertEqual(len(vm.rows),8)
        data,report,vm=self.graphics_movie()
        vm.globals.update(_fnr3GraphicsActive=1,_fnr3GraphicsPage=1,_fnr3GraphicsStatus=0)
        vm.family=3;vm.selected=1;vm.regs[8]=vm.globals['INPUTCODE']['DOWN']
        vm.run(report['event_handler'],report['event_end'])
        self.assertEqual(vm.rows[1],'BACK / SECONDARY: A')

    def test_native_navigation_and_setting_sounds_once(self):
        for page in range(4):
            for key,selection,expected in [('UP',0,'updown'),('DOWN',3,'updown'),
                    ('LEFT',0,'updown'),('RIGHT',3,'updown'),('RIGHT',7,None)]:
                data,report,vm=self.graphics_movie()
                vm.globals.update(_fnr3GraphicsActive=1,_fnr3GraphicsPage=page,_fnr3GraphicsStatus=0)
                vm.selected=selection;vm.regs[8]=vm.globals['INPUTCODE'][key]
                vm.run(report['event_handler'],report['event_end'])
                sounds=[args for obj,name,args in vm.calls if name=='playSound']
                self.assertEqual(sounds,[[expected]] if expected else [])
        for key,selection,page,sound in [('ADVANCE',5,0,'confirm'),('ADVANCE',6,0,'confirm'),
                ('ADVANCE',7,0,'confirm'),('CANCEL',0,0,'cancel'),('CANCEL',0,2,'cancel')]:
            data,report,vm=self.graphics_movie()
            vm.globals.update(_fnr3GraphicsActive=1,_fnr3GraphicsPage=page,_fnr3GraphicsStatus=0)
            vm.selected=selection;vm.regs[8]=vm.globals['INPUTCODE'][key]
            vm.run(report['event_handler'],report['event_end'])
            self.assertEqual([args for obj,name,args in vm.calls if name=='playSound'],[[sound]])

    def test_native_graphics_back_rebuilds_retail_render_and_actions_together(self):
        original={e.name:e.payload for e in m.parse_big((ROOT/m.OPTIONS).read_bytes())}
        apt=original['options.apt'];constants=m.constant_strings(original['options.const'])
        pool_field=m.align4(0xe9ec+1);pool=m.u32(apt,pool_field+4)
        def pool_string(index):return constants[m.u32(apt,pool+4*index)]
        original_init=m.decode_actions(apt,0xeb6c,0xed57)
        retail_rows=[]
        for index,action in enumerate(original_init):
            if action.opcode==0xb2 and pool_string(apt[action.offset+1])=='addElement':
                label=original_init[index-6]
                self.assertEqual(label.opcode,0xa2)
                retail_rows.append(pool_string(apt[label.offset+1]))
        self.assertEqual(retail_rows,['$2318','$2310','$28','$2311','$2319','$2317','$2322','$2307','$2313'])
        for signed_in,mode in [(False,0),(True,0),(True,4)]:
            for key,selection in [('CANCEL',0),('CIRCLE',2),('BACK',7)]:
                data,report,vm=self.graphics_movie();vm.retail_rows=retail_rows
                vm.signed_in,vm.game_mode=signed_in,mode
                vm.globals.update(_fnr3GraphicsActive=1,_fnr3GraphicsPage=0,_fnr3GraphicsStatus=0)
                vm.rows=['RESOLUTION: 1920 X 1080','FULLSCREEN: ON','FXAA: OFF','FILTERING: 4X',
                    'CONTROLLER: AUTOMATIC','BUTTON MAPPING','SAVE','SAVE AND RESTART']
                vm.selected=selection;vm.regs[8]=vm.globals['INPUTCODE'][key]
                vm.run(report['event_handler'],report['event_end'])
                expected=['GRAPHICS']+retail_rows[:5]+([retail_rows[5],retail_rows[6] if mode==4 else retail_rows[7]] if signed_in else [])+retail_rows[-1:]
                self.assertEqual(vm.rows,expected)
                self.assertEqual(vm.native_title,'$2300')
                self.assertEqual(vm.native_handler,'retail_mainEventHandler')
                self.assertEqual(vm.globals['_fnr3GraphicsActive'],0)
                self.assertLess(vm.selected,len(vm.rows))
                transitions=[name for obj,name,args in vm.calls if name in ('clearMenu','mainInitGui')]
                self.assertEqual(transitions,['clearMenu','mainInitGui'])

    def test_native_integer_literals_reject_negative(self):
        with self.assertRaises(ValueError):m.NativeScript(0,{}).integer(-1)

    def test_native_begin_failure_and_unflagged_event_are_inert(self):
        data,report,vm=self.graphics_movie();vm.status=0
        vm.run(report['graphics_dispatch'],report['script_end'])
        self.assertFalse(vm.globals.get('_fnr3GraphicsActive'))
        self.assertEqual(vm.rows,[])
        self.assertEqual(vm.stack,[])
        data,report,vm=self.graphics_movie()
        prefix=m.decode_actions(data,report['event_handler'],report['event_end'])
        retail=next(a.target for a in prefix if a.opcode==0x9d)
        self.assertEqual(vm.run(report['event_handler'],report['event_end'],retail),retail)
        self.assertEqual(vm.calls,[])
        self.assertEqual(vm.stack,[])

    def test_native_graphics_page_contract(self):
        original = next(e.payload for e in m.parse_big((ROOT / m.OPTIONS).read_bytes()) if e.name == 'options.apt')
        patched = m.patch_options(original)
        report = m.inspect_options_patch(patched)
        self.assertEqual(report['native_graphics_page'], True)
        self.assertEqual(report['setting_rows'], 5)
        self.assertEqual(report['read_only_rows'], ['MSAA: ORIGINAL', 'RESTART REQUIRED'])
        self.assertNotIn(b'PortGraphics\0', patched[len(original):])
        for name in m.GRAPHICS_CALLBACKS:
            self.assertIn(name.encode() + b'\0', patched[len(original):])
        self.assertEqual(patched[0xe9ec:0x1453d], original[0xe9ec:0x1453d])

    def test_pc_storage_warning_preserves_localization_structure(self):
        original=(ROOT/'assets/locale/ENGLISH.loc').read_bytes()
        patched=m.patch_localization(original)
        self.assertEqual(len(patched),len(original))
        self.assertEqual(patched[:0xe4],original[:0xe4])
        for index in range(22):
            start=0x7c+struct.unpack_from('<I',original,0x8c+4*index)[0]
            end=0x7c+struct.unpack_from('<I',original,0x90+4*index)[0] if index<21 else len(original)
            before=original[start:end].decode('utf-16le').split('\0',1)[0]
            after=patched[start:end].decode('utf-16le').split('\0',1)[0]
            if index in (9,14,18):
                self.assertEqual(after,before.replace("Please don't turn off your Xbox 360 console.","Please don't close the game."))
                self.assertIn('%1',after)
                self.assertNotIn('Xbox 360',after)
            else:self.assertEqual(patched[start:end],original[start:end])
        damaged=bytearray(original);damaged[-1]^=1
        with self.assertRaisesRegex(ValueError,'SHA256'):m.patch_localization(bytes(damaged))
        self.assertEqual((ROOT/'assets/locale/ENGLISH.loc').read_bytes(),original)

    def test_stale_localization_rejected_before_any_override_write(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);source=base/'data';destination=base/'overrides'
            for name in {**m.SOURCE_HASHES,**m.SIBLING_HASHES}:
                target=source/Path(name).relative_to('assets');target.parent.mkdir(parents=True,exist_ok=True)
                if name==m.LOCALIZATION:
                    damaged=bytearray((ROOT/name).read_bytes());damaged[-1]^=1;target.write_bytes(damaged)
                else:target.symlink_to(ROOT/name)
            with self.assertRaisesRegex(ValueError,'SHA256'):m.generate(ROOT,destination,source)
            self.assertFalse(destination.exists())

    def test_reject_overwriting_retail_assets(self):
        with self.assertRaises(ValueError): m.generate(ROOT, ROOT)

    def test_external_game_data_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            data = base / 'original game data'
            data.mkdir()
            (data / 'gui').symlink_to(ROOT / 'assets/gui', target_is_directory=True)
            (data / 'locale').symlink_to(ROOT / 'assets/locale', target_is_directory=True)
            manifest = m.generate(base / 'unrelated workspace', base / 'overrides', data)
            self.assertEqual(len(manifest['overrides']), 3)
            self.assertTrue((base / 'overrides/manifest.json').is_file())

    def test_retail_outputs_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = m.generate(ROOT, Path(directory))
            self.assertEqual(manifest['schema_version'], 1)
            self.assertEqual(len(manifest['overrides']), 3)
            self.assertEqual(len(manifest['preserved_siblings']), 9)
            for entry in manifest['preserved_siblings']:
                self.assertEqual((ROOT / entry['source']).read_bytes(), (Path(directory) / entry['override']).read_bytes())
            for entry in manifest['overrides']:
                original = (ROOT / entry['source']).read_bytes()
                patched = (Path(directory) / entry['override']).read_bytes()
                if entry['source'].endswith('.loc'):
                    self.assertEqual(entry['changed_entries'],['10','15','19'])
                    continue
                before = {e.name: e.payload for e in m.parse_big(original)}
                after = {e.name: e.payload for e in m.parse_big(patched)}
                self.assertEqual(before.keys(), after.keys())
                for name in before.keys() - set(entry['changed_entries']):
                    self.assertEqual(before[name], after[name])
            main = {e.name: e.payload for e in m.parse_big((Path(directory) / m.MAIN_MENU).read_bytes())}
            strings = m.constant_strings(main['mainmenu.const'])
            self.assertTrue(strings[278].endswith(',QUIT GAME'))
            self.assertTrue(strings[282].endswith(',QUIT'))
            options = {e.name: e.payload for e in m.parse_big((Path(directory) / m.OPTIONS).read_bytes())}
            report = m.inspect_options_patch(options['options.apt'])
            self.assertEqual(report['native_graphics_row'], True)
            self.assertEqual(report['callback'], 'AptTaskMessages.PortGraphicsEvent')
            self.assertTrue(report['all_branch_targets_valid'])

if __name__ == '__main__': unittest.main()
