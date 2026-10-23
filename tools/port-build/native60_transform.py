#!/usr/bin/env python3
"""Validated native60 transform of private codegen output. Project work: djultra64.

Never modifies its input. Output contains generated game code and stays private.
Every invocation starts from original generated code; patched input is rejected.
"""
import argparse
from pathlib import Path
import re

TARGETS = ('8226E838', '82265A20', '82223260', '821A3D78', '821A3E58', '822552E8')
FUNCTION = re.compile(r'^DEFINE_REX_FUNC\(sub_([0-9A-F]{8})\) \{', re.MULTILINE)


def replace_exact(text, old, new, count=1):
    actual = text.count(old)
    if actual != count:
        raise ValueError(f'Expected {count} occurrences of {old!r}; found {actual}')
    return text.replace(old, new)


def before_epilogue(body, call, stack_size):
    marker = f'\t// addi r1,r1,{stack_size}\n'
    return replace_exact(body, marker, '\t' + call + ';\n' + marker)


def patch_function(address, body):
    if 'Fnr3' in body or 'fnr3_' in body:
        raise ValueError(f'{address}: input already patched or instrumented; regenerate original code')
    if address == '8226E838':
        # Restore before stock phase selection, then replay override after it.
        body = replace_exact(body, '\tREX_FUNC_PROLOGUE();',
                             '\tREX_FUNC_PROLOGUE();\n\tFnr3Native60Begin(base);')
        replace_exact(body, '\tREX_STORE_U32(ctx.r3.u32 + 484, ctx.r11.u32);', '')
        return before_epilogue(body, 'Fnr3ReplayPhaseEnd(base)', 96)
    if address == '82265A20':
        # This mode job owns the final stock clock write. Applying earlier is overwritten.
        replace_exact(body, '\tREX_STORE_U32(ctx.r3.u32 + 484, ctx.r11.u32);', '')
        return replace_exact(body, '\treturn;', '\tFnr3Native60End(base);\n\treturn;')
    if address == '821A3D78':
        replace_exact(body, '\t// lwz r31,8(r3)', '')
        return before_epilogue(body, 'Fnr3ReplaySequenceBegin(base,ctx.r31.u32)', 112)
    if address == '821A3E58':
        return replace_exact(body, '\tREX_FUNC_PROLOGUE();',
                             '\tREX_FUNC_PROLOGUE();\n\tFnr3ReplaySequenceEnd(base);')
    if address == '82223260':
        body = replace_exact(body, '\tuint32_t ea{};',
                             '\tuint32_t ea{};\n\tfnr3::port::timing::CrowdAdvance fnr3_crowd;')
        marker = '\tif (!ctx.cr6.gt) goto loc_82223340;'
        body = replace_exact(body, marker, marker +
                             '\n\tfnr3_crowd = fnr3::port::timing::AdvanceCrowd(ctx.f0.f64);')
        store = 'temp.f32 = float(ctx.f0.f64);\n\tREX_STORE_U32(ctx.r31.u32 + 832, temp.u32);'
        if body.count(store) != 2:
            raise ValueError('82223260: expected exactly two elapsed-sample stores')
        pos = body.index(store, body.index(store) + len(store))
        body = body[:pos] + body[pos:].replace(store,
                    'temp.f32 = fnr3_crowd.remainder;\n\tREX_STORE_U32(ctx.r31.u32 + 832, temp.u32);', 1)
        return replace_exact(body, 'ctx.r11.s64 = ctx.r11.s64 + 2;',
                             'ctx.r11.s64 = ctx.r11.s64 + fnr3_crowd.samples;')
    if address == '822552E8':
        body = replace_exact(body, '\tuint32_t ea{};',
                             '\tuint32_t ea{};\n\tconst float fnr3_replay_scale = Fnr3ReplayTickScale(base);')
        call = '\tsub_82255148(ctx, base);'
        body = replace_exact(body, call,
                 '\tctx.f1.f64 = double(float(ctx.f1.f64 * fnr3_replay_scale));\n' + call, 2)
        decrement = 'ctx.r11.s64 = ctx.r11.s64 + -1;'
        if body.count(decrement) != 2:
            raise ValueError('822552E8: expected countdown and state-transition decrements')
        countdown = '\t// lwz r11,44(r31)'
        replace_exact(body, countdown, '', 2)
        pos = body.index(countdown, body.index('sub_82255148'))
        at = body.index(decrement, pos)
        body = body[:at] + body[at:].replace(decrement,
                   'ctx.r11.u64 = Fnr3ReplayCountdown(ctx.r31.u32,ctx.r11.u32,fnr3_replay_scale);', 1)
        return replace_exact(body, 'ctx.f0.f64 = double(float(ctx.f13.f64 + ctx.f0.f64));',
                   'ctx.f0.f64 = double(float(ctx.f13.f64 + ctx.f0.f64 * fnr3_replay_scale));')
    raise ValueError('Unknown hook: ' + address)


def find_units(source):
    units = {}
    found = {}
    for path in sorted(source.glob('fnr3_recomp.*.cpp')):
        text = path.read_text(encoding='utf-8')
        functions = list(FUNCTION.finditer(text))
        selected = []
        for i, match in enumerate(functions):
            address = match.group(1)
            if address not in TARGETS:
                continue
            if address in found:
                raise ValueError('Duplicate guest function: ' + address)
            found[address] = path.name
            end = functions[i + 1].start() if i + 1 < len(functions) else len(text)
            selected.append((address, match.start(), end))
        if selected:
            units[path.name] = (text, selected)
    if set(found) != set(TARGETS):
        raise ValueError('Missing guest functions: ' + ', '.join(sorted(set(TARGETS) - set(found))))
    return units


def transform(source, output):
    source, output = Path(source), Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Generated originals and transformed copies must be separate')
    # Complete validation before writing any output; partial transforms never compile.
    transformed = {}
    for name, (text, functions) in find_units(source).items():
        for address, start, end in reversed(functions):
            try:
                text = text[:start] + patch_function(address, text[start:end]) + text[end:]
            except ValueError as error:
                raise ValueError(f'{name} / {address}: {error}') from error
        transformed[name] = '#include "port_timing.h"\n' + text
    output.mkdir(parents=True, exist_ok=True)
    for name, text in transformed.items():
        path = output / name
        if not path.exists() or path.read_text(encoding='utf-8') != text:
            temporary = path.with_suffix(path.suffix + '.tmp')
            temporary.write_text(text, encoding='utf-8', newline='\n')
            temporary.replace(path)
    return sorted(transformed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--list', action='store_true', help='List affected units for CMake discovery')
    args = parser.parse_args()
    if args.list:
        print(';'.join(find_units(args.input)))
    elif args.output:
        transform(args.input, args.output)
    else:
        parser.error('--output is required unless --list is used')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(str(error))
