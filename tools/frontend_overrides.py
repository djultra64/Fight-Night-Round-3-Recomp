#!/usr/bin/env python3
"""Build hash-pinned native menus and PC storage-warning overrides. Port work: djultra64.

Reads the user's retail archives; never modifies or redistributes source assets.
No runtime/window is launched. Only Python's standard library is required.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct

MAIN_MENU = 'assets/gui/fn2k6/screengroups/mainmenu/mainmenu.big'
OPTIONS = 'assets/gui/fn2k6/screengroups/options/options.big'
LOCALIZATION = 'assets/locale/ENGLISH.loc'
SOURCE_HASHES = {
    MAIN_MENU: '3f565109eab0c108663d085f645624c160cb1c6ac5c9669600c2774eb40bfdaa',
    OPTIONS: '9688e765412b9d9727a8aabe392cd20eb6e05fada42379b927907c0c767975b4',
    LOCALIZATION: '2142ed127ebabc0fc991009e26fe044a7e9ece9f03b4ebd61d7dd4e78e20a981',
}
SIBLING_HASHES = {
    'assets/gui/fn2k6/screengroups/mainmenu/t3436t55.tmp':
        'c71d0ba5338ba22ef464fee90e6391fc775dea253f58df57585f8544c1c00c6f',
    'assets/locale/xloc_fe.euk': 'd97a14b6c63c85b3892919d2a02b90d477d65276e729d36b0ee2bb6b02f1de72',
    'assets/locale/xloc_fe.eus': '58a7807429c70ddfe849572b3a8b20526880619a6aaaa16b9489611b5005416a',
    'assets/locale/xloc_fe.fre': 'cdfa20501944a22e8be4bb765f018bb93b1002872e653bed1f10d0c356d48d4a',
    'assets/locale/xloc_fe.ger': '26562c70f51cbb93138794a98a7272a0f97eb6b490da46a353292bdb790cbdbd',
    'assets/locale/xloc_gm.euk': 'eb518b05b446871e89b275d4344c4ddf193ea528f6b2a3760f44fb897001c53c',
    'assets/locale/xloc_gm.eus': '5ea54b9ffb2d725c854272e3cae4d202b0eb70e1260b32f098c832eae07e70bb',
    'assets/locale/xloc_gm.fre': '4a4b52f0ee4f6b20f9f59b459b5c97359e5cba75d8420725fdbb07f74bb6d6b9',
    'assets/locale/xloc_gm.ger': '7e5bd9cf0be36fe568c293363c0f076d90eec6247086f768472b6583710b536b',
}


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError('32-bit field outside file')
    return struct.unpack_from('>I', data, offset)[0]


def cstring(data: bytes, offset: int) -> str:
    if not 0 <= offset < len(data):
        raise ValueError('string offset outside file')
    end = data.find(b'\0', offset)
    if end < 0:
        raise ValueError('unterminated string')
    try:
        return data[offset:end].decode('ascii')
    except UnicodeDecodeError as error:
        raise ValueError('non-ASCII resource string') from error


@dataclass(frozen=True)
class BigEntry:
    name: str
    payload: bytes
    toc_offset: int
    offset: int


def parse_big(data: bytes) -> list[BigEntry]:
    if len(data) < 16 or data[:4] != b'BIGF':
        raise ValueError('expected BIGF header')
    if struct.unpack_from('<I', data, 4)[0] != len(data):
        raise ValueError('BIGF file size mismatch')
    count, header_size = u32(data, 8), u32(data, 12)
    if not 16 <= header_size <= len(data) or count > (header_size - 16) // 9:
        raise ValueError('invalid BIGF table bounds')
    result, names, spans = [], set(), []
    cursor = 16
    for _ in range(count):
        toc = cursor
        offset, size = u32(data, cursor), u32(data, cursor + 4)
        cursor += 8
        name = cstring(data, cursor)
        cursor += len(name) + 1
        if cursor > header_size or not name or name in names:
            raise ValueError('invalid or duplicate BIGF entry')
        if offset < header_size or offset > len(data) or size > len(data) - offset:
            raise ValueError('BIGF payload outside file')
        names.add(name)
        spans.append((offset, offset + size))
        result.append(BigEntry(name, data[offset:offset + size], toc, offset))
    spans.sort()
    if any(right[0] < left[1] for left, right in zip(spans, spans[1:])):
        raise ValueError('overlapping BIGF payloads')
    return result


def replace_big(data: bytes, replacements: dict[str, bytes]) -> bytes:
    entries = parse_big(data)
    if set(replacements) - {entry.name for entry in entries}:
        raise ValueError('replacement names absent from BIGF')
    output = bytearray(data)
    for entry in entries:
        if entry.name not in replacements or replacements[entry.name] == entry.payload:
            continue
        output.extend(bytes((-len(output)) % 64))
        payload = replacements[entry.name]
        struct.pack_into('>II', output, entry.toc_offset, len(output), len(payload))
        output.extend(payload)
    struct.pack_into('<I', output, 4, len(output))
    parse_big(bytes(output))
    return bytes(output)


def patch_localization(data: bytes) -> bytes:
    """Change only three hash-pinned UTF-16LE storage warning slots in place."""
    if hashlib.sha256(data).hexdigest() != SOURCE_HASHES[LOCALIZATION]:
        raise ValueError('unsupported retail localization SHA256')
    base = 0x7c
    if data[:4] != b'LOCH' or data[base:base+4] != b'LOCL':
        raise ValueError('unexpected retail localization structure')
    if struct.unpack_from('<II', data, base+8) != (0, 22):
        raise ValueError('unexpected retail localization record count')
    output = bytearray(data)
    warning = "Please don't turn off your Xbox 360 console."
    for index, operation in ((9, 'Loading'), (14, 'Saving'), (18, 'Deleting')):
        start = base + struct.unpack_from('<I', data, 0x8c + index*4)[0]
        end = base + struct.unpack_from('<I', data, 0x90 + index*4)[0]
        if start < 0xe4 or not start < end <= len(data) or (end-start) % 2:
            raise ValueError('retail localization warning slot outside file')
        original = data[start:end].decode('utf-16le').split('\0', 1)[0]
        if original != f'{operation} %1. {warning}':
            raise ValueError('retail localization warning precondition failed')
        replacement = f"{operation} %1. Please don't close the game.".encode('utf-16le') + b'\0\0'
        if len(replacement) > end-start:
            raise ValueError('PC storage warning exceeds original localization slot')
        output[start:end] = replacement + bytes(end-start-len(replacement))
    return bytes(output)


def constant_strings(data: bytes) -> dict[int, str]:
    if len(data) < 32 or data[:20] != b'Apt constant file\x1a\0\0':
        raise ValueError('invalid APT constant header')
    count, table = u32(data, 24), u32(data, 28)
    if table < 32 or table > len(data) or count > (len(data) - table) // 8:
        raise ValueError('APT constant table outside file')
    strings = {}
    for index in range(count):
        kind, value = u32(data, table + index * 8), u32(data, table + index * 8 + 4)
        if kind == 1:
            if value < table + count * 8:
                raise ValueError('APT string overlaps constant table')
            strings[index] = cstring(data, value)
    return strings


def patch_constants(data: bytes, replacements: dict[int, tuple[str, str]]) -> bytes:
    strings = constant_strings(data)
    output = bytearray(data)
    table = u32(data, 28)
    for index, (expected, replacement) in replacements.items():
        if strings.get(index) != expected or '\0' in replacement:
            raise ValueError(f'APT constant {index} precondition failed')
        output.extend(bytes((-len(output)) % 4))
        struct.pack_into('>I', output, table + index * 8 + 4, len(output))
        output.extend(replacement.encode('ascii') + b'\0')
    constant_strings(bytes(output))
    return bytes(output)


@dataclass(frozen=True)
class Action:
    offset: int
    opcode: int
    end: int
    immediate: int | None = None
    target: int | None = None
    size_field: int | None = None
    body: int | None = None


def align4(value: int) -> int:
    return (value + 3) & ~3


def decode_actions(data: bytes, start: int, end: int) -> list[Action]:
    """Decode shipped Xenon APT actions, including nested function bodies.

    Endianness is BE here (unlike the PC SAGE APT variant). Unknown opcodes
    fail closed. Parameter/string/constant pointers remain file-relative.
    """
    actions = []
    p = start
    singles = set(range(0x04, 0x16)) | {0, 0x17, 0x18, 0x1c, 0x1d, 0x20, 0x21,
        0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b, 0x2c,
        0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37} | set(range(0x3a, 0x5f)) | set(range(0x60, 0x6a)) | set(range(0x70, 0x78))
    byte_args = {0x8d, 0x9a, 0x9f, 0xa2, 0xae, 0xaf, 0xb0, 0xb1, 0xb2, 0xb3, 0xb5, 0xb9}
    aligned_word = {0x81, 0x87, 0x8b, 0x8c, 0xa1, 0xa4, 0xa5, 0xa6, 0xa7}
    while p < end:
        origin, opcode = p, data[p]
        p += 1
        immediate = target = size_field = body = None
        if opcode in (0x8e, 0x9b):
            p = align4(p)
            size_field = p + (16 if opcode == 0x8e else 12)
            size = u32(data, size_field)
            body = size_field + 12
            function_end = body + size
            if function_end > end:
                raise ValueError(f'function exceeds action block at {origin:x}')
            actions.append(Action(origin, opcode, function_end, size_field=size_field, body=body))
            actions.extend(decode_actions(data, body, function_end))
            p = function_end
            continue
        if opcode in (0x99, 0x9d, 0xb8):
            p = align4(p)
            immediate = p
            target = p + 4 + struct.unpack_from('>i', data, p)[0]
            p += 4
        elif opcode in (0x88, 0x96, 0x83):
            p = align4(p) + 8
        elif opcode in aligned_word:
            p = align4(p) + 4
        elif opcode in byte_args:
            p += 1
        elif opcode in (0xa3, 0xb6):
            p += 2
        elif opcode in (0xb4, 0xb7):
            p += 4
        elif opcode not in singles:
            raise ValueError(f'unsupported APT action {opcode:02x} at {origin:x}')
        if p > end:
            raise ValueError(f'truncated APT action at {origin:x}')
        actions.append(Action(origin, opcode, p, immediate, target))
    return actions


def validate_constant_fixups(data: bytes, constants: bytes, start: int, end: int) -> dict:
    """Model the retail loader's destructive constant-index array conversion.

    sub_823CF0B0 handles both CONSTANTPOOL and PUSHDATA by replacing each array
    slot with an AptValue pointer. Reusing even one slot makes a later fixup
    interpret that pointer as a constant index and can dereference null.
    """
    constant_strings(constants)
    count, table = u32(constants, 24), u32(constants, 28)
    converted = set()
    arrays = 0
    for action in decode_actions(data, start, end):
        if action.opcode not in (0x88, 0x96): continue
        field = align4(action.offset + 1)
        length, pointer = u32(data, field), u32(data, field + 4)
        if pointer > len(data) or length > (len(data) - pointer) // 4:
            raise ValueError('APT constant-index array outside file')
        arrays += 1
        for offset in range(pointer, pointer + length * 4, 4):
            if offset in converted:
                raise ValueError(f'APT destructive fixup reuses index slot {offset:x}')
            converted.add(offset)
            index = u32(data, offset)
            if index >= count or u32(constants, table + index * 8) not in (1, 2, 3, 4, 5):
                raise ValueError(f'unsupported APT constant index/type at {offset:x}')
    return {'constant_arrays': arrays, 'converted_slots': len(converted)}


class Assembler:
    def __init__(self, address: int):
        self.address = address
        self.data = bytearray()

    def emit(self, *values: int):
        self.data.extend(values)

    def word_action(self, opcode: int, value: int):
        self.emit(opcode)
        self.data.extend(bytes((-self.address - len(self.data)) % 4))
        self.data.extend(struct.pack('>I', value))

    def branch(self, opcode: int, target: int):
        self.emit(opcode)
        self.data.extend(bytes((-self.address - len(self.data)) % 4))
        self.data.extend(struct.pack('>i', target - (self.address + len(self.data) + 4)))

    def finish(self) -> bytes:
        # Safe stack-neutral padding, never an END inside a live function.
        needed = (-len(self.data)) % 4
        if needed == 1:
            needed = 5
        if needed % 2:
            self.emit(0x59, 0x12, 0x17)
            needed -= 3
        for _ in range(needed // 2):
            self.emit(0x59, 0x17)
        return bytes(self.data)


def patch_main_menu(data: bytes) -> bytes:
    # The retail QUIT route requests a fn2k6-local movie that is not shipped.
    # Handle only the new item directly; original indices 0..5 resume unchanged.
    start, end, root_pointer = 0xafec, 0xdf4c, 0x4320
    position = 0xce55  # after getSelection->int->register4, before route/context
    if u32(data, root_pointer) != start:
        raise ValueError('unexpected main-menu action pointer')
    actions = decode_actions(data, start, end)
    boundaries = {a.offset for a in actions} | {end}
    if any(a.target not in boundaries for a in actions if a.target is not None):
        raise ValueError('original main-menu branch target is not an instruction')
    output = bytearray(data)
    strings = {}
    for value in ('AptTaskMessages', 'Quit'):
        output.extend(bytes((-len(output)) % 4))
        strings[value] = len(output)
        output.extend(value.encode() + b'\0')
    output.extend(bytes((-len(output)) % 4))
    # Index arrays are rewritten in-place by the native loader. The new push
    # must own its slot; sharing original ed6c would fix up the same slot twice.
    register_push_table = len(output)
    output.extend(data[0xed6c:0xed70])
    clone_start = len(output)
    delta = clone_start - start
    handler = Assembler(position + delta)
    handler.emit(0x96)
    handler.data.extend(bytes((-handler.address - len(handler.data)) % 4))
    handler.data.extend(struct.pack('>II', 1, register_push_table))  # original register-4 push
    handler.emit(0xb5, 6, 0x66, 0x12)
    branch_offset = len(handler.data)
    handler.branch(0x9d, 0)
    handler.emit(0x59, 0x71)
    handler.word_action(0xa5, strings['AptTaskMessages'])
    handler.word_action(0xa1, strings['Quit'])
    handler.emit(0x5d, 0x76, 0x3e)
    code = bytearray(handler.finish())
    imm = align4(handler.address + branch_offset + 1) - handler.address
    struct.pack_into('>i', code, imm, handler.address + len(code) - (handler.address + imm + 4))

    def relocated(address):
        return address + delta + (len(code) if address >= position else 0)

    clone = bytearray(data[start:position] + code + data[position:end])
    for action in actions:
        if action.immediate is not None:
            field = relocated(action.immediate) - clone_start
            struct.pack_into('>i', clone, field, relocated(action.target) - (clone_start + field + 4))
        if action.size_field is not None:
            extra = len(code) if action.body <= position < action.end else 0
            struct.pack_into('>I', clone, relocated(action.size_field) - clone_start,
                             u32(data, action.size_field) + extra)
    output.extend(clone)
    struct.pack_into('>I', output, root_pointer, clone_start)
    output.extend(b'FNR3_PORT_MAIN_MENU_V1\0' + struct.pack('>IIII', clone_start, len(clone), handler.address, len(code)))
    result = bytes(output)
    inspect_main_menu_patch(result)
    return result


def inspect_main_menu_patch(data: bytes) -> dict:
    marker = b'FNR3_PORT_MAIN_MENU_V1\0'
    location = data.rfind(marker)
    if location < 0 or location + len(marker) + 16 != len(data):
        raise ValueError('missing port main-menu metadata')
    start, size, handler, handler_size = struct.unpack_from('>IIII', data, location + len(marker))
    if start + size != location or u32(data, 0x4320) != start:
        raise ValueError('invalid port main-menu action block')
    actions = decode_actions(data, start, start + size)
    if not actions or actions[-1].opcode != 0 or actions[-1].end != start + size:
        raise ValueError('cloned action block must finish with native END before metadata')
    boundaries = {a.offset for a in actions} | {start + size}
    if any(a.target not in boundaries for a in actions if a.target is not None):
        raise ValueError('patched main-menu branch target is not an instruction')
    return {'callback': 'AptTaskMessages.Quit', 'all_branch_targets_valid': True,
            'handler': handler, 'resume': handler + handler_size, 'decoded_actions': len(actions)}


GRAPHICS_CALLBACKS = ('PortGraphicsEvent', 'PortGetResolution', 'PortGetFullscreen',
                      'PortGetFxaa', 'PortGetFiltering', 'PortGetFamily', 'PortGetBinding', 'PortGetActiveFamily')
GRAPHICS_CHOICES = (
    ('RESOLUTION: ', ('1280 X 720', '1600 X 900', '1920 X 1080', '2560 X 1440', '3200 X 1800', '3840 X 2160'), 'PortGetResolution'),
    ('FULLSCREEN: ', ('OFF', 'ON'), 'PortGetFullscreen'),
    ('FXAA: ', ('OFF', 'ON', 'EXTREME'), 'PortGetFxaa'),
    ('FILTERING: ', ('ORIGINAL', 'ANISOTROPIC 1X', 'ANISOTROPIC 2X', 'ANISOTROPIC 4X', 'ANISOTROPIC 8X', 'ANISOTROPIC 16X'), 'PortGetFiltering'),
    ('CONTROLLER: ', ('AUTOMATIC', 'XBOX', 'PLAYSTATION', 'NINTENDO SWITCH'), 'PortGetFamily'),
)


class NativeScript(Assembler):
    """Small native APT assembler; injected scripts own no constant-fixup slots."""
    def __init__(self, address, strings):
        super().__init__(address)
        self.strings = strings
        self.labels = {}
        self.jumps = []

    def string(self, text): self.word_action(0xa1, self.strings[text])
    def integer(self, value):
        if not isinstance(value, int) or not 0 <= value <= 0x7fffffff:
            raise ValueError('native integer literal outside nonnegative signed range')
        # B5 sign-extends its byte in the retail interpreter.
        if 0 <= value <= 127: self.emit(0xb5, value)
        else:
            self.integer(value // 2); self.integer(value - value // 2); self.emit(0x47, 0x18)
    def global_path(self, *parts):
        self.emit(0x71)
        for part in parts: self.string(part); self.emit(0x4e)
    def variable(self, name): self.string(name); self.emit(0x1c)
    def set_global(self, name, value):
        self.emit(0x71); self.string(name); self.integer(value); self.emit(0x4f)
    def call(self, path, method, argc=0, discard=True):
        self.integer(argc); self.global_path(*path); self.string(method); self.emit(0x52)
        if discard: self.emit(0x17)
    def host(self, method, argc=0, discard=True): self.call(('AptTaskMessages',), method, argc, discard)
    def sound(self, sound_id):
        # Retail options root pool slot60 is the scoped playSound function.
        self.string(sound_id); self.integer(1); self.emit(0xb0, 60)
    def event(self, command, discard=True):
        if command >= 10: self.set_global('_fnr3GraphicsStatus', 0)
        self.integer(command); self.host('PortGraphicsEvent', 1, discard)
    def label(self, name): self.labels[name] = self.address + len(self.data)
    def jump(self, opcode, name):
        self.jumps.append((len(self.data), name)); self.branch(opcode, 0)
    def resolved(self):
        for offset, name in self.jumps:
            field = align4(self.address + offset + 1) - self.address
            struct.pack_into('>i', self.data, field, self.labels[name] - (self.address + field + 4))
        return self.finish()


def graphics_strings():
    values = set(GRAPHICS_CALLBACKS) | {'GRAPHICS', 'AptTaskMessages', 'options', 'm_screen', 'm_class',
        'm_title', 'mainControl', 'mainMenu', 'clearMenu', 'addElement', 'setSelectedIndex', 'getSelectedIndex',
        'setText', 'animateIn', 'gStdHelp', 'gHlpPopup', 'setHelp', 'INPUTCODE', 'ADVANCE', 'CANCEL', 'CIRCLE', 'BACK',
        'LEFT', 'RIGHT', 'UP', 'DOWN', 'gFM', 'handleDefaultInputs', 'gSM', 'goBackScreen', 'mainInitGui',
        '_fnr3GraphicsActive', '_fnr3GraphicsSelection', '_fnr3GraphicsStatus', '_fnr3GraphicsRefresh',
        'updown', 'confirm', 'cancel', 'SAVE', 'SAVE AND RESTART', 'BACK', 'MSAA: ORIGINAL', 'RESTART REQUIRED', 'SAVED - RESTART REQUIRED', 'COULD NOT SAVE - TRY AGAIN',
        'x,SELECT,t,BACK,s,RESTART REQUIRED', 'x,SELECT,t,BACK,dlr,CHANGE,dud,SELECT', 'PREVIOUS PAGE', 'NEXT PAGE', 'x,SELECT,t,BACK,s,MSAA ORIGINAL - RESTART REQUIRED', 'keyCode', '_fnr3GraphicsPage', 'BUTTON MAPPING', 'RESET BUTTON MAPPING', 'x,SELECT,t,BACK,dlr,CHANGE,dud,SELECT'}
    for prefix, choices, _ in GRAPHICS_CHOICES: values.add(prefix); values.update(choices)
    values.update(action + ': ' for action in BINDING_ACTIONS)
    for family in BINDING_LABELS: values.update(family)
    return sorted(values)


BINDING_ACTIONS = ('CONFIRM / PRIMARY', 'BACK / SECONDARY', 'ALTERNATE X', 'ALTERNATE Y',
    'LEFT SHOULDER', 'RIGHT SHOULDER', 'LEFT STICK CLICK', 'RIGHT STICK CLICK',
    'PAUSE', 'VIEW', 'UP', 'DOWN', 'LEFT', 'RIGHT')
BINDING_LABELS = (
    ('A','B','X','Y','LB','RB','LS','RS','MENU','VIEW','UP','DOWN','LEFT','RIGHT'),
    ('CROSS','CIRCLE','SQUARE','TRIANGLE','L1','R1','L3','R3','OPTIONS','SHARE','UP','DOWN','LEFT','RIGHT'),
    ('B','A','Y','X','L','R','LS','RS','+','-','UP','DOWN','LEFT','RIGHT'),
)


def mapping_refresh(script):
    script.string('BUTTON MAPPING'); script.call(('options', 'm_screen', 'm_title'), 'setText', 1)
    script.call(MENU_PATH, 'clearMenu')
    for page in range(1,4):
        script.global_path('_fnr3GraphicsPage');script.integer(page);script.emit(0x66)
        script.jump(0x9d,f'binding_page_{page}')
    for page in range(1,4):
        script.label(f'binding_page_{page}')
        for index in range((page-1)*5,min(page*5,14)):
            action=BINDING_ACTIONS[index]
            script.string(action + ': ')
            script.host('PortGetActiveFamily', discard=False)
            script.integer(2);script.emit(0x66);script.jump(0x9d,f'ps_{index}')
            script.host('PortGetActiveFamily', discard=False)
            script.integer(3);script.emit(0x66);script.jump(0x9d,f'switch_{index}')
            for label in reversed(BINDING_LABELS[0]):script.string(label)
            script.jump(0x99,f'labels_{index}')
            script.label(f'ps_{index}')
            for label in reversed(BINDING_LABELS[1]):script.string(label)
            script.jump(0x99,f'labels_{index}')
            script.label(f'switch_{index}')
            for label in reversed(BINDING_LABELS[2]):script.string(label)
            script.label(f'labels_{index}')
            script.integer(14);script.emit(0x42)
            script.integer(index);script.host('PortGetBinding',1,discard=False)
            script.emit(0x4e,0x47);script.call(MENU_PATH,'addElement',1)
        if page==3:
            script.string('RESET BUTTON MAPPING');script.call(MENU_PATH,'addElement',1)
        script.jump(0x99,'binding_page_end')
    script.label('binding_page_end')
    for text in ('PREVIOUS PAGE','NEXT PAGE','BACK'):
        script.string(text);script.call(MENU_PATH,'addElement',1)
    script.global_path('_fnr3GraphicsSelection');script.call(MENU_PATH,'setSelectedIndex',1)
    for path in (('gStdHelp',),('gHlpPopup',)):
        script.string('x,SELECT,t,BACK,dlr,CHANGE,dud,SELECT');script.call(path,'setHelp',1)
    script.emit(0x76,0x3e)


MENU_PATH = ('options', 'm_screen', 'mainControl', 'mainMenu')


def graphics_refresh(script):
    script.global_path('_fnr3GraphicsPage'); script.jump(0x9d,'mapping_page')
    script.string('GRAPHICS'); script.call(('options', 'm_screen', 'm_title'), 'setText', 1)
    script.call(MENU_PATH, 'clearMenu')
    for prefix, choices, getter in GRAPHICS_CHOICES:
        script.string(prefix)
        for choice in reversed(choices): script.string(choice)
        script.integer(len(choices)); script.emit(0x42)
        script.host(getter, discard=False); script.emit(0x4e, 0x47)
        script.call(MENU_PATH, 'addElement', 1)
    script.string('BUTTON MAPPING'); script.call(MENU_PATH, 'addElement', 1)
    # Native feedback stays inside the movie, and a failed save remains retryable.
    script.global_path('_fnr3GraphicsStatus'); script.integer(1); script.emit(0x66)
    script.jump(0x9d, 'saved')
    script.global_path('_fnr3GraphicsStatus'); script.integer(2); script.emit(0x66)
    script.jump(0x9d, 'failed')
    script.string('SAVE'); script.jump(0x99, 'save_label')
    script.label('saved'); script.string('SAVED - RESTART REQUIRED'); script.jump(0x99, 'save_label')
    script.label('failed'); script.string('COULD NOT SAVE - TRY AGAIN')
    script.label('save_label'); script.call(MENU_PATH, 'addElement', 1)
    for text in ('SAVE AND RESTART',):
        script.string(text); script.call(MENU_PATH, 'addElement', 1)
    script.global_path('_fnr3GraphicsSelection'); script.call(MENU_PATH, 'setSelectedIndex', 1)
    for path, text in [(('gStdHelp',), 'x,SELECT,t,BACK,s,MSAA ORIGINAL - RESTART REQUIRED'),
                       (('gHlpPopup',), 'x,SELECT,t,BACK,dlr,CHANGE,dud,SELECT')]:
        script.string(text); script.call(path, 'setHelp', 1)
    script.emit(0x76, 0x3e)
    script.label('mapping_page'); mapping_refresh(script)


def graphics_event_handler(script, register_table):
    script.global_path('_fnr3GraphicsActive'); script.emit(0x12); script.jump(0x9d, 'retail')
    # The retail mainEventHandler's first argument is preloaded in register 8.
    # Every injected register push has its own destructive-fixup array slot.
    def key():
        pointer = register_table.pop(0)
        script.emit(0x96); script.data.extend(bytes((-script.address-len(script.data)) % 4))
        script.data.extend(struct.pack('>II', 1, pointer))
    def key_is(name):
        key(); script.global_path('INPUTCODE', name); script.emit(0x66)
    def selected(): script.call(MENU_PATH, 'getSelectedIndex', discard=False)
    def refresh(): script.call((), '_fnr3GraphicsRefresh')
    for name in ('CANCEL', 'CIRCLE', 'BACK'):
        key_is(name); script.jump(0x9d, 'back')
    key_is('ADVANCE'); script.jump(0x9d, 'advance')
    key_is('LEFT'); script.jump(0x9d, 'previous')
    key_is('RIGHT'); script.jump(0x9d, 'next')
    key_is('UP'); script.jump(0x9d, 'navigate_up')
    key_is('DOWN'); script.jump(0x9d, 'navigate_down')
    script.emit(0x71);script.string('_fnr3GraphicsSelection');selected();script.emit(0x4f)
    refresh()
    script.emit(0x76, 0x3e)
    # Native focus-manager state belongs to the retail list context. Graphics
    # owns its page selection, using the same verified widget setter directly.
    for direction,step in [('navigate_up',-1),('navigate_down',1)]:
        script.label(direction);script.sound('updown')
        for selection in range(8):
            selected();script.integer(selection);script.emit(0x66)
            script.jump(0x9d,f'{direction}_{selection}')
        script.emit(0x76,0x3e)
        for selection in range(8):
            script.label(f'{direction}_{selection}')
            script.set_global('_fnr3GraphicsSelection',(selection+step)%8)
            refresh();script.emit(0x76,0x3e)
    script.label('advance')
    script.global_path('_fnr3GraphicsPage');script.jump(0x9d,'mapping_advance')
    selected(); script.integer(5); script.emit(0x66); script.jump(0x9d,'open_mapping')
    selected(); script.integer(6); script.emit(0x66); script.jump(0x9d, 'save')
    selected(); script.integer(7); script.emit(0x66); script.jump(0x9d, 'save_restart')
    script.jump(0x99, 'next')
    for label, base in [('previous', 10), ('next', 20)]:
        script.label(label)
        script.global_path('_fnr3GraphicsPage');script.jump(0x9d,'mapping_'+label)
        for field in range(5):
            selected(); script.integer(field); script.emit(0x66); script.jump(0x9d, f'{label}_{field}')
        script.emit(0x76, 0x3e)
        for field in range(5):
            script.label(f'{label}_{field}'); script.set_global('_fnr3GraphicsSelection', field)
            script.sound('updown');script.event(base + field); refresh(); script.emit(0x76, 0x3e)
    for label,command,selection in [('save',2,6),('save_restart',3,7)]:
        script.label(label);script.sound('confirm');script.event(command,discard=False);script.jump(0x9d,label+'_ok')
        script.set_global('_fnr3GraphicsStatus',2);script.jump(0x99,label+'_refresh')
        script.label(label+'_ok');script.set_global('_fnr3GraphicsStatus',1)
        script.label(label+'_refresh');script.set_global('_fnr3GraphicsSelection',selection)
        refresh();script.emit(0x76,0x3e)
    script.label('back');script.global_path('_fnr3GraphicsPage');script.jump(0x9d,'mapping_back')
    script.sound('cancel');script.event(1); script.set_global('_fnr3GraphicsActive', 0)
    # Retail mainInitGui appends rows; timeline entry normally creates a new
    # widget, but this in-place page must clear its old rows first.
    script.call(MENU_PATH, 'clearMenu')
    script.call(('options', 'm_class'), 'mainInitGui'); script.emit(0x76, 0x3e)
    script.label('open_mapping');script.sound('confirm');script.set_global('_fnr3GraphicsPage',1)
    script.set_global('_fnr3GraphicsSelection',0);refresh();script.emit(0x76,0x3e)
    script.label('mapping_back');script.sound('cancel');script.set_global('_fnr3GraphicsPage',0)
    script.set_global('_fnr3GraphicsSelection',5);refresh();script.emit(0x76,0x3e)
    script.label('mapping_advance')
    selected();script.integer(5);script.emit(0x66);script.jump(0x9d,'binding_prev_page')
    selected();script.integer(6);script.emit(0x66);script.jump(0x9d,'binding_next_page')
    selected();script.integer(7);script.emit(0x66);script.jump(0x9d,'mapping_back')
    script.global_path('_fnr3GraphicsPage');script.integer(3);script.emit(0x66);script.jump(0x9d,'binding_last_advance')
    script.jump(0x99,'mapping_next')
    script.label('binding_last_advance')
    selected();script.integer(4);script.emit(0x66);script.jump(0x9d,'reset_mapping')
    script.jump(0x99,'mapping_next')
    script.label('reset_mapping');script.sound('confirm');script.event(300)
    script.set_global('_fnr3GraphicsSelection',4);refresh();script.emit(0x76,0x3e)
    for label,step,selection in [('binding_prev_page',-1,5),('binding_next_page',1,6)]:
        script.label(label);script.sound('updown')
        for page in range(1,4):
            script.global_path('_fnr3GraphicsPage');script.integer(page);script.emit(0x66)
            script.jump(0x9d,f'{label}_{page}')
        for page in range(1,4):
            script.label(f'{label}_{page}')
            script.set_global('_fnr3GraphicsPage',max(1,min(3,page+step)))
            script.set_global('_fnr3GraphicsSelection',selection);refresh();script.emit(0x76,0x3e)
    for label,base in [('previous',100),('next',200)]:
        script.label('mapping_'+label)
        for page in range(1,4):
            script.global_path('_fnr3GraphicsPage');script.integer(page);script.emit(0x66)
            script.jump(0x9d,f'{label}_page_{page}')
        for page in range(1,4):
            script.label(f'{label}_page_{page}')
            for selection,field in enumerate(range((page-1)*5,min(page*5,14))):
                selected();script.integer(selection);script.emit(0x66);script.jump(0x9d,f'map_{label}_{field}')
            script.emit(0x76,0x3e)
        for field in range(14):
            script.label(f'map_{label}_{field}');script.sound('updown');script.event(base+field)
            script.set_global('_fnr3GraphicsSelection',field%5);refresh();script.emit(0x76,0x3e)
    script.label('retail')


def patch_options(data: bytes) -> bytes:
    start, end, root_pointer = 0xe9ec, 0x1453d, 0x3ca4
    row_position, event_position, handler_position, definitions_position = 0xebcc, 0xed84, 0xee89, 0x1453c
    if u32(data, root_pointer) != start: raise ValueError('unexpected Options action pointer')
    actions = decode_actions(data, start, end)
    boundaries = {a.offset for a in actions} | {end}
    if any(a.target not in boundaries for a in actions if a.target is not None):
        raise ValueError('original Options branch target is not an instruction')
    output = bytearray(data); strings = {}
    for value in graphics_strings():
        output.extend(bytes((-len(output)) % 4)); strings[value] = len(output)
        output.extend(value.encode('ascii') + b'\0')
    output.extend(bytes((-len(output)) % 4))
    register_tables = []
    # REG8 used by event interception; REG7 by native retail route guard.
    field = align4(0xedd6 + 1); source = u32(data, field + 4)
    for _ in range(8): register_tables.append(len(output)); output.extend(data[source:source+4])
    selected_tables = []
    for _ in range(2): selected_tables.append(len(output)); output.extend(data[0x15944:0x15948])
    clone_start = len(output); delta = clone_start - start
    inserts = []
    def script_at(position): return NativeScript(position + delta + sum(len(c) for _, c in inserts), strings)
    row = script_at(row_position)
    row.string('GRAPHICS'); row.emit(0x5a, 0xae, 1, 0xaf, 2, 0xaf, 0x18, 0xaf, 0x19, 0xb2, 0x1a)
    inserts.append((row_position, row.finish()))
    event = script_at(event_position); graphics_event_handler(event, register_tables)
    event_code = event.resolved()
    inserts.append((event_position, event_code))
    handler = script_at(handler_position)
    def push_selected():
        handler.emit(0x96); handler.data.extend(bytes((-handler.address-len(handler.data)) % 4))
        handler.data.extend(struct.pack('>II', 1, selected_tables.pop(0)))
    push_selected(); handler.emit(0x59, 0x66, 0x12); handler.jump(0x9d, 'normal')
    handler.event(0, discard=False); handler.jump(0x9d, 'begin_ok')
    handler.emit(0x76, 0x3e)
    handler.label('begin_ok'); handler.set_global('_fnr3GraphicsActive', 1)
    handler.set_global('_fnr3GraphicsSelection', 0); handler.set_global('_fnr3GraphicsStatus', 0)
    handler.set_global('_fnr3GraphicsPage', 0)
    handler.call((), '_fnr3GraphicsRefresh'); handler.emit(0x76, 0x3e)
    handler.label('normal'); push_selected(); handler.emit(0x51); handler.word_action(0x87, 7); handler.emit(0x17)
    handler_code = handler.resolved(); inserts.append((handler_position, handler_code))
    definitions = script_at(definitions_position)
    definitions.emit(0x71); definitions.string('_fnr3GraphicsRefresh')
    definitions.emit(0x9b); definitions.data.extend(bytes((-definitions.address-len(definitions.data)) % 4))
    header = len(definitions.data)
    definitions.data.extend(struct.pack('>IIIIII', 0x1587c, 0, 0x15a04, 0, 0x98765432, 0x12345678))
    refresh = NativeScript(definitions.address+len(definitions.data), strings); graphics_refresh(refresh)
    refresh_code = refresh.resolved(); definitions.data.extend(refresh_code)
    struct.pack_into('>I', definitions.data, header+12, len(refresh_code))
    definitions.emit(0x4f)
    inserts.append((definitions_position, definitions.finish()))
    def relocated(address): return address+delta+sum(len(c) for p,c in inserts if p <= address)
    clone = bytearray(); cursor = start
    for where, code in inserts: clone.extend(data[cursor:where]); clone.extend(code); cursor = where
    clone.extend(data[cursor:end])
    for action in actions:
        if action.immediate is not None:
            field = relocated(action.immediate)-clone_start
            struct.pack_into('>i', clone, field, relocated(action.target)-(clone_start+field+4))
        if action.size_field is not None:
            extra=sum(len(c) for p,c in inserts if action.body <= p < action.end)
            struct.pack_into('>I',clone,relocated(action.size_field)-clone_start,u32(data,action.size_field)+extra)
    output.extend(clone); struct.pack_into('>I',output,root_pointer,clone_start)
    # V1 trailer remains outside every native action block.
    output.extend(b'FNR3_PORT_OPTIONS_V1\0'+struct.pack('>II',clone_start,len(clone)))
    patched=bytes(output); inspect_options_patch(patched); return patched

def inspect_options_patch(data: bytes) -> dict:
    marker = b'FNR3_PORT_OPTIONS_V1\0'
    location = data.rfind(marker)
    if location < 0 or location + len(marker) + 8 != len(data):
        raise ValueError('missing port Options metadata')
    start, size = struct.unpack_from('>II', data, location + len(marker))
    if start + size != location or u32(data, 0x3ca4) != start:
        raise ValueError('invalid port Options action block')
    actions = decode_actions(data, start, start + size)
    if not actions or actions[-1].opcode != 0 or actions[-1].end != start + size:
        raise ValueError('cloned action block must finish with native END before metadata')
    boundaries = {a.offset for a in actions} | {start + size}
    valid = all(a.target in boundaries for a in actions if a.target is not None)
    if not valid:
        raise ValueError('patched Options branch target is not an instruction')
    pushed_strings = [cstring(data, u32(data, align4(a.offset + 1)))
                      for a in actions if a.opcode in (0xa1, 0xa5)]
    if not all(s in pushed_strings for s in ('GRAPHICS', 'AptTaskMessages', 'PortGraphicsEvent')):
        raise ValueError('missing native Graphics row or callback')
    functions = [a for a in actions if a.opcode in (0x8e, 0x9b)]
    dispatch = next(a for n,a in enumerate(actions) if a.opcode == 0x96 and
                    [x.opcode for x in actions[n+1:n+5]] == [0x59,0x66,0x12,0x9d])
    normal = actions[actions.index(dispatch)+4].target
    resume = next(a.end for a in actions if a.offset >= normal and a.opcode == 0x17)
    return {'native_graphics_row': True, 'callback': 'AptTaskMessages.PortGraphicsEvent',
            'native_graphics_page': True, 'setting_rows': 5,
            'graphics_dispatch': dispatch.offset, 'retail_resume': resume,
            'event_handler': functions[4].body, 'event_end': functions[4].end,
            'refresh_body': functions[-1].body, 'refresh_end': functions[-1].end,
            'script_end': start+size,
            'read_only_rows': ['MSAA: ORIGINAL', 'RESTART REQUIRED'],
            'all_branch_targets_valid': valid, 'decoded_actions': len(actions)}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def generate(root: Path, destination: Path, game_data_root: Path | None = None) -> dict:
    outputs = []
    expected_hashes = {**SOURCE_HASHES, **SIBLING_HASHES}
    sources = {name: (game_data_root / Path(name).relative_to("assets")
                      if game_data_root is not None else root / name) for name in expected_hashes}
    # Parent-directory VFS aliases require a complete original sibling set.
    for parent in {Path(name).parent for name in SOURCE_HASHES}:
        expected = {Path(name).name for name in expected_hashes if Path(name).parent == parent}
        source_parent = sources[next(name for name in sources if Path(name).parent == parent)].parent
        if {entry.name for entry in source_parent.iterdir()} != expected:
            raise ValueError(f'unsupported frontend sibling inventory: {parent}')
        output_parent = destination / parent
        if output_parent.exists() and {entry.name for entry in output_parent.iterdir()} - expected:
            raise ValueError(f'unexpected file in frontend override directory: {parent}')
    if any((destination / name).resolve() == sources[name].resolve() for name in sources):
        raise ValueError('override destination would overwrite retail assets')
    # Validate every input before writing any overrides.
    inputs = {name: path.read_bytes() for name, path in sources.items()}
    for name, data in inputs.items():
        if sha256(data) != expected_hashes[name]:
            raise ValueError(f'unsupported retail resource SHA256: {name}')
    for name, data in inputs.items():
        if name in SIBLING_HASHES:
            outputs.append((name, data, []))
            continue
        if name == LOCALIZATION:
            outputs.append((name, patch_localization(data), ['10', '15', '19']))
            continue
        entries = {e.name: e.payload for e in parse_big(data)}
        if name == MAIN_MENU:
            replacements = {'mainmenu.const': patch_constants(entries['mainmenu.const'], {
                278: ('$1000,$1006,$4703,$1007,$1001,$1201', '$1000,$1006,$4703,$1007,$1001,$1201,QUIT GAME'),
                282: ('SELECTCORNER,RIVALSSELECTRIVALRY,~DNA~,GAMEMODES,CACMAIN,OPTIONSMAIN',
                      'SELECTCORNER,RIVALSSELECTRIVALRY,~DNA~,GAMEMODES,CACMAIN,OPTIONSMAIN,QUIT'),
            }), 'mainmenu.apt': patch_main_menu(entries['mainmenu.apt'])}
        else:
            replacements = {'options.apt': patch_options(entries['options.apt'])}
        # Native fixup mutates constant-index arrays even in function bodies
        # that have not executed. Check startup-loader semantics before output.
        stem = 'mainmenu' if name == MAIN_MENU else 'options'
        apt = replacements[stem + '.apt']
        marker = b'FNR3_PORT_MAIN_MENU_V1\0' if name == MAIN_MENU else b'FNR3_PORT_OPTIONS_V1\0'
        metadata = apt.rfind(marker) + len(marker)
        script_start, script_size = struct.unpack_from('>II', apt, metadata)
        validate_constant_fixups(apt, replacements.get(stem + '.const', entries[stem + '.const']), script_start, script_start + script_size)
        patched = replace_big(data, replacements)
        outputs.append((name, patched, sorted(replacements)))
    manifest = {'schema_version': 1, 'author': 'djultra64',
                'required_host_callbacks': ['AptTaskMessages.Quit'] + ['AptTaskMessages.' + name for name in GRAPHICS_CALLBACKS],
                'overrides': [], 'preserved_siblings': []}
    for name, data, changed in outputs:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        records = manifest['preserved_siblings'] if name in SIBLING_HASHES else manifest['overrides']
        records.append({'source': name, 'source_sha256': expected_hashes[name],
            'override': name, 'override_sha256': sha256(data), 'changed_entries': changed})
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--game-data-root', type=Path, help='Original game data folder containing gui/ and locale/ (workspace assets/ by default)')
    args = parser.parse_args()
    output = args.output or args.root / 'runtime/port-overrides'
    manifest = generate(args.root, output, args.game_data_root)
    print(f"Generated {len(manifest['overrides'])} native menu overrides in {output}")

if __name__ == '__main__':
    main()
