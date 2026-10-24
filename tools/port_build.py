"""Isolated Linux/Windows production build. Project: djultra64.

Never launches the game or updates accepted baseline builds.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = 'Fight Night Round 3 Recomp'
VERSION = '1.0.1'
EXTRACT_XISO_PIN = '3f5b62cfe68f000b0e3c8a30104973f3a297948e'
PIN = 'f5337cdc947ff6d4c4196737e2c807a48f2a1fc2'
PATCHES = (
    'rexglue-sdk-indirect-buffer.patch',
    'rexglue-sdk-vulkan-texture-exponent.patch',
    'rexglue-sdk-fnr3-optimizations.patch',
    'rexglue-sdk-frame-stats.patch',
    'rexglue-sdk-pipeline-storage-pacing.patch',
    'rexglue-sdk-fnr3-xmp-delay.patch',
    'rexglue-fnr3-direct-resolve.patch',
    'rexglue-sdk-posix-wait-deadline.patch',
    'rexglue-sdk-posix-multiwait-notify.patch',
    'rexglue-sdk-fnr3-audio-pacing.patch',
    'rexglue-sdk-fnr3-xma-no-lookahead.patch',
    'rexglue-sdk-posix-mapping-lifetime.patch',
    'rexglue-sdk-sdl-connected-discovery.patch',
    'rexglue-sdk-xma-drain-pending.patch',
    'rexglue-sdk-xma-split-frame-header.patch',
    'rexglue-sdk-texture-watch-retirement.patch',
    'rexglue-sdk-vulkan-shared-memory-sync.patch',
    'rexglue-sdk-d3d12-queue-fence-result.patch',
    'rexglue-sdk-mnk-capture-coalescing.patch',
    'tools/port-input/rexglue-native-glyphs.patch',
    'tools/port-input/rexglue-sdl-observer-abi.patch',
    'tools/port-input/rexglue-native-glyph-diagnostics.patch',
    'tools/port-input/rexglue-native-glyph-bc2.patch',
    'rexglue-sdk-fnr3-texture-bake-readback.patch',
    'rexglue-sdk-vulkan-readback-source-range.patch',
)
TARGETS = {'Linux': 'linux-amd64', 'Windows': 'win-amd64'}
MSVC_REDISTRIBUTABLES = frozenset({
    'concrt140.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
    'msvcp140_atomic_wait.dll', 'msvcp140_codecvt_ids.dll',
    'vcruntime140.dll', 'vcruntime140_1.dll', 'vcruntime140_threads.dll',
})


def patch_file(name):
    return ROOT / name if name.startswith('tools/') else ROOT / 'patches' / name


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def files_manifest(directory, source=False):
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            if not source:
                raise ValueError(f'Symlink not permitted in manifest: {path}')
            result[path.relative_to(directory).as_posix()] = 'symlink:' + os.readlink(path)
            continue
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = sha(path)
    return result


def run(command, flatpak=False, cwd=None):
    command = list(map(str, command))
    if flatpak:
        command = ['flatpak', 'run', '--user', '--filesystem=' + str(ROOT),
                   '--command=env', 'org.freedesktop.Sdk//25.08',
                   'PATH=/usr/lib/sdk/llvm20/bin:/usr/bin:/bin', *command]
    print(subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT if cwd is None else cwd, check=True)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def verify_inputs(root=ROOT):
    manifest = json.loads((root / 'config/input-manifest.json').read_text())
    xex = root / manifest['xex']['path']
    if sha(xex) != manifest['xex']['sha256']:
        raise ValueError('Original XEX differs from the supported edition')
    return manifest


def layout(target, root=ROOT):
    home = root / '.cache/production' / target
    return home, home / 'sdk', home / 'project', root / 'build/production' / target


def apply_sdk_patches(sdk):
    # Git otherwise treats a nested source export as a subdirectory of the
    # parent repository and silently skips git-format patch paths outside it.
    directory = '--directory=' + sdk.relative_to(ROOT).as_posix()
    for name in PATCHES:
        command = ['git', 'apply', directory]
        patch = patch_file(name)
        applied = subprocess.run([*command, '--reverse', '--check', str(patch)],
                                 cwd=ROOT, capture_output=True)
        if applied.returncode:
            run([*command, '--check', patch])
            run([*command, patch])
        run([*command, '--reverse', '--check', patch])


def prepare(target):
    verify_inputs()
    home, sdk, project, build = layout(target)
    base = ROOT / '.cache/rexglue-source'
    revision = subprocess.check_output(['git', '-C', str(base), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != PIN:
        raise ValueError('Unexpected source SDK revision')
    patch_hashes = {name: sha(patch_file(name)) for name in PATCHES}
    seed = {'sdk_commit': PIN, 'patches': patch_hashes,
            'patch_application': 'explicit-directory-v1',
            'pipeline_cache_file': sha(ROOT / 'tools/xenos-optimized/pipeline_cache_file.h'),
            'readback_buffer_range': sha(ROOT / 'tools/xenos-optimized/readback_buffer_range.h')}
    marker = home / 'sdk-prepared.json'
    if sdk.exists():
        if not marker.is_file() or json.loads(marker.read_text()) != seed:
            raise ValueError('Prepared SDK differs; remove only the isolated production SDK and marker to rebuild it')
        source_record = json.loads((home / 'sdk-inputs.json').read_text())
        for name, digest in source_record['files'].items():
            path = sdk / name
            actual = 'symlink:' + os.readlink(path) if path.is_symlink() else sha(path)
            if actual != digest:
                raise ValueError('Prepared SDK source changed: ' + name)
    else:
        home.mkdir(parents=True, exist_ok=True)
        temporary = home / 'sdk-preparing'
        if temporary.exists():
            raise ValueError('Incomplete preparation: remove isolated sdk-preparing before retrying')
        temporary.mkdir()
        data = subprocess.check_output(['git', '-C', str(base), 'archive', PIN])
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall(temporary, filter='data')
        # Verify every initialized submodule against the pinned superproject.
        # Copies have no hardlinks: build outputs cannot modify accepted sources.
        entries = subprocess.check_output(['git', '-C', str(base), 'ls-tree', '-r', PIN], text=True)
        submodules = {}
        for line in entries.splitlines():
            mode, _, rest = line.split(' ', 2)
            if mode != '160000':
                continue
            revision, name = rest.split('\t', 1)
            source = base / name
            actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
            if actual != revision:
                raise ValueError(f'Submodule revision differs: {name}')
            dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no'], text=True)
            if dirty:
                raise ValueError(f'Submodule has modified tracked inputs: {name}')
            # Export tracked files only; local ignored/untracked outputs never
            # become inputs of a supposedly pinned SDK build.
            module_data = subprocess.check_output(['git', '-C', str(source), 'archive', revision])
            with tarfile.open(fileobj=io.BytesIO(module_data)) as archive:
                archive.extractall(temporary / name, filter='data')
            # SDK's source-export check requires a .git marker. This inert
            # marker carries only the verified pin, never a pointer into the baseline.
            (temporary / name / '.git').write_text('verified source archive: ' + revision + '\n')
            submodules[name] = revision
        apply_sdk_patches(temporary)
        shutil.copy2(ROOT / 'tools/xenos-optimized/pipeline_cache_file.h',
                     temporary / 'include/rex/graphics/vulkan/pipeline_cache_file.h')
        shutil.copy2(ROOT / 'tools/xenos-optimized/readback_buffer_range.h',
                     temporary / 'include/rex/graphics/vulkan/fnr3_readback_buffer_range.h')
        # Hash all source inputs before compilation (including submodules).
        write_json(home / 'sdk-inputs.json', {'submodules': submodules,
                   'files': files_manifest(temporary, source=True)})
        temporary.rename(sdk)
        write_json(marker, seed)
    project.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / 'src', project / 'src', dirs_exist_ok=True)
    (project / 'generated').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'generated/rexglue.cmake', project / 'generated/rexglue.cmake')
    first_codegen = not (project / 'generated/default/sources.cmake').is_file()
    if first_codegen:
        if (ROOT / 'generated/default').is_dir():
            shutil.copytree(ROOT / 'generated/default', project / 'generated/default', dirs_exist_ok=True)
        else:
            (project / 'generated/default').mkdir(parents=True, exist_ok=True)
    (project / 'tools/port-build').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'tools/port-build/native60_transform.py',
                 project / 'tools/port-build/native60_transform.py')
    shutil.copy2(ROOT / 'tools/port-build/sdk_loader_paths.cmake',
                 project / 'tools/port-build/sdk_loader_paths.cmake')
    bridge = project / 'tools/port-input/input_glyph_bridge.h'
    bridge.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'tools/port-input/input_glyph_bridge.h', bridge)
    if sha(bridge) != sha(sdk / 'include/rex/graphics/fnr3_input_glyph_bridge.h'):
        raise ValueError('Host/GPU glyph bridge ABI headers differ')
    for name in ('CMakeLists.txt', 'fnr3_analysis.toml'):
        shutil.copy2(ROOT / name, project / name)
    manifest = (ROOT / 'fnr3_manifest.toml').read_text()
    manifest = manifest.replace('game_root = "assets"', 'game_root = ' + json.dumps((ROOT / 'assets').as_posix()))
    manifest = manifest.replace('file_path = "assets/default.xex"', 'file_path = ' + json.dumps((ROOT / 'assets/default.xex').as_posix()))
    manifest_path = project / 'fnr3_manifest.toml'
    if not manifest_path.exists() or manifest_path.read_text() != manifest:
        manifest_path.write_text(manifest)
    # Only the initial copied dependency paths belong to the root tree. Later
    # builds preserve isolated codegen outputs and let its real inputs decide
    # whether regeneration is needed (a host-only edit must not rebuild PPC).
    if first_codegen:
        for name in ('codegen.build.stamp', 'codegen.d'):
            (project / 'generated/default' / name).unlink(missing_ok=True)
    return sdk, project, build


def inspect_dependencies(stage, target):
    """Read loader metadata without executing packaged binaries."""
    windows = target == 'win-amd64'
    tool = shutil.which('llvm-readobj' if windows else 'readelf')
    if tool is None:
        raise ValueError('Dependency audit requires ' + ('llvm-readobj' if windows else 'readelf'))
    result = {}
    for path in ([stage] if stage.is_file() else sorted(stage.iterdir())):
        command = [tool, '--coff-imports', str(path)] if windows else [tool, '-d', str(path)]
        output = subprocess.check_output(command, text=True)
        dependencies = re.findall(r'Name: ([^\r\n]+)', output) if windows else re.findall(r'\(NEEDED\).*?\[([^]]+)\]', output)
        result[path.name] = {'needed': sorted(set(dependencies))}
        if not windows:
            result[path.name]['search_paths'] = re.findall(r'\((?:RPATH|RUNPATH)\).*?\[([^]]*)\]', output)
    return result


def bundle_windows_crt(stage, redist=None):
    """Stage imported Release CRTs from the licensed VS redist directory only."""
    root = Path(redist or os.environ.get('VCToolsRedistDir', ''))
    copied = {}
    while True:
        imports = {name.lower() for info in inspect_dependencies(stage, 'win-amd64').values()
                   for name in info['needed']}
        crt = {name for name in imports if name.startswith(('msvcp140', 'vcruntime140', 'concrt140'))}
        if crt - MSVC_REDISTRIBUTABLES:
            raise ValueError('Unsupported or non-Release MSVC runtime: ' + ', '.join(sorted(crt - MSVC_REDISTRIBUTABLES)))
        present = {path.name.lower() for path in stage.iterdir()}
        missing = crt - present
        if not missing:
            return {'publisher': 'Microsoft Corporation', 'version': root.name,
                    'files': copied} if copied else None
        if not redist and not os.environ.get('VCToolsRedistDir'):
            raise ValueError('MSVC runtime staging requires the Visual Studio developer environment (VCToolsRedistDir)')
        directories = list((root / 'x64').glob('Microsoft.VC*.CRT'))
        if len(directories) != 1:
            raise ValueError('Expected one x64 Release CRT directory under VCToolsRedistDir')
        sources = {path.name.lower(): path for path in directories[0].iterdir() if path.is_file()}
        for name in sorted(missing):
            if name not in sources or sources[name].is_symlink():
                raise ValueError('Imported MSVC runtime missing from approved redist directory: ' + name)
            shutil.copy2(sources[name], stage / sources[name].name)
            copied[sources[name].name] = sha(sources[name])


def build_port(target, jobs, flatpak=False, sdk_only=False):
    sdk, project, build = prepare(target)
    sdk_recipe = json.loads((sdk.parent / 'sdk-prepared.json').read_text())
    sdk_inputs_digest = sha(sdk.parent / 'sdk-inputs.json')
    windows = target == 'win-amd64'
    # Match the pinned SDK's own Windows/Linux compiler drivers.
    compiler = 'clang++'
    configure_command = ['cmake', '-S', project, '-B', build, '-G', 'Ninja',
         '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_BUILD_WITH_INSTALL_RPATH=ON',
         '-DCMAKE_C_COMPILER=clang',
         '-DCMAKE_CXX_COMPILER=' + compiler, '-DREXSDK_DIR=' + str(sdk),
         '-DCMAKE_PROJECT_ReXGlue_INCLUDE=' + str(project / 'tools/port-build/sdk_loader_paths.cmake'),
         '-DCMAKE_C_FLAGS=-march=x86-64-v2', '-DCMAKE_CXX_FLAGS=-march=x86-64-v2',
         '-DREXGLUE_USE_VULKAN=ON', '-DREXGLUE_USE_D3D12=' + ('ON' if windows else 'OFF'),
         '-DREXGLUE_ENABLE_TRACY=OFF', '-DREXGLUE_ENABLE_PERF_COUNTERS=OFF',
         '-DREXGLUE_BUILD_TESTS=OFF']
    run(configure_command, flatpak)
    if not sdk_only and not (project / 'generated/default/sources.cmake').is_file():
        # A clean checkout intentionally has no proprietary generated PPC code.
        # Build its generator and verified local guest first, then reconfigure
        # so CMake sees the emitted source list before compiling the host.
        run(['cmake', '--build', build, '--target', 'fnr3_codegen', '-j', jobs], flatpak)
        run(configure_command, flatpak)
    if sdk_only:
        run(['cmake', '--build', build, '--target', 'rexruntime', 'rexgpu-xenos', 'rexglue', '-j', jobs], flatpak)
        return
    # Build only the production host and its runtime/GPU/codegen dependencies.
    run(['cmake', '--build', build, '--target', 'fnr3_stage_gpu', '-j', jobs], flatpak)
    home = sdk.parent
    if json.loads((home / 'sdk-prepared.json').read_text()) != sdk_recipe or sha(home / 'sdk-inputs.json') != sdk_inputs_digest:
        raise ValueError('SDK inputs changed during compilation; rebuild before recording artifacts')
    record = {'schema': 1, 'owner': 'djultra64', 'target': target,
              'sdk': json.loads((home / 'sdk-prepared.json').read_text()),
              'sdk_inputs_sha256': sha(home / 'sdk-inputs.json'),
              'recipe_sha256': sha(Path(__file__)),
              'host_platform': platform.platform(),
              'compiler_detection': {str(p.relative_to(build)): p.read_text()
                  for p in (build / 'CMakeFiles').glob('*/CMakeCXXCompiler.cmake')},
              'project_inputs': files_manifest(project), 'configuration': 'Release',
              'backend': 'Vulkan', 'clock': 'native60-phase-preserved',
              'cmake_cache_sha256': sha(build / 'CMakeCache.txt')}
    stage = build / 'stage'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    executable = 'fnr3.exe' if windows else 'fnr3'
    shutil.copy2(build / executable, stage / executable)
    # SDK output directory is unique to this production source checkout.
    for directory in (sdk / 'out' / target, build):
        for path in sorted(directory.iterdir()):
            if path.is_file() and (path.suffix.lower() == '.dll' if windows else '.so' in path.name):
                shutil.copy2(path, stage / path.name)
    required = ['rexruntime.dll', 'rexgpu-xenos.dll'] if windows else ['librexruntime.so', 'librexgpu-xenos.so']
    if not all((stage / name).is_file() for name in required):
        raise ValueError('Missing production runtime or GPU plugin')
    if windows:
        redistributables = bundle_windows_crt(stage)
        if redistributables:
            record['runtime_redistributables'] = redistributables
    record['loader_dependencies'] = inspect_dependencies(stage, target)
    if not windows:
        for info in record['loader_dependencies'].values():
            if any(entry.startswith('/') for paths in info['search_paths'] for entry in paths.split(':')):
                raise ValueError('Nonportable absolute loader search path in production artifact')
    record['artifacts'] = files_manifest(stage)
    write_json(build / 'build-record.json', record)
    print('Production artifacts recorded:', stage)


def validate_stage(stage, record):
    if record.get('owner') != 'djultra64' or record.get('sdk', {}).get('sdk_commit') != PIN:
        raise ValueError('Unknown build provenance')
    if record.get('configuration') != 'Release' or record.get('clock') != 'native60-phase-preserved':
        raise ValueError('Unsupported build profile')
    if record['sdk'].get('patch_application') != 'explicit-directory-v1':
        raise ValueError('Unverified SDK patch application method')
    if set(record['sdk'].get('patches', {})) != set(PATCHES):
        raise ValueError('Incomplete accepted SDK patchset')
    for info in record.get('loader_dependencies', {}).values():
        if any(entry.startswith('/') for paths in info.get('search_paths', []) for entry in paths.split(':')):
            raise ValueError('Nonportable absolute loader search path')
    actual = files_manifest(stage)
    if actual != record.get('artifacts'):
        raise ValueError('Artifact hash mismatch or unrecorded package input')
    target = record['target']
    if target not in TARGETS.values():
        raise ValueError('Unsupported artifact target')
    expected = {'fnr3.exe', 'rexruntime.dll', 'rexgpu-xenos.dll'} if target == 'win-amd64' else {'fnr3', 'librexruntime.so', 'librexgpu-xenos.so'}
    if not expected.issubset(actual):
        raise ValueError('Incomplete production artifacts')
    for name in actual:
        if '/' in name or name not in expected and not (name.lower().endswith('.dll') if target == 'win-amd64' else '.so' in name):
            raise ValueError('Forbidden package input: ' + name)
    return actual


def build_extractor(target, flatpak=False, compiler=None):
    source = ROOT / '.cache/extract-xiso'
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if revision != EXTRACT_XISO_PIN:
        raise ValueError('Unexpected extract-xiso source revision')
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=no'], text=True)
    if dirty:
        raise ValueError('extract-xiso has modified tracked source')
    build = ROOT / 'build/iso-extractor' / target
    if target == 'win-amd64':
        compiler = compiler or shutil.which('x86_64-w64-mingw32-gcc')
        if not compiler:
            raise ValueError('Windows extractor requires native MinGW-w64; pass --extractor-compiler <gcc.exe or clang.exe>')
        compiler = str(Path(compiler).resolve())
        triple = subprocess.check_output([compiler, '-dumpmachine'], text=True).strip().lower()
        if not triple.startswith('x86_64') or not any(name in triple for name in ('mingw', 'windows-gnu')):
            raise ValueError('The extractor compiler must target x86-64 MinGW-w64: ' + triple)
        configure = ['cmake', '-S', ROOT / 'tools/port-build/extractor', '-B', build / 'mingw',
                     '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
                     '-DCMAKE_C_COMPILER=' + compiler,
                     '-DFNR3_EXTRACT_XISO_SOURCE=' + str(source),
                     '-DCMAKE_RUNTIME_OUTPUT_DIRECTORY=' + str(build)]
        compile_directory = build / 'mingw'
    else:
        configure = ['cmake', '-S', source, '-B', build, '-G', 'Ninja', '-DCMAKE_BUILD_TYPE=Release',
                     '-DCMAKE_POLICY_VERSION_MINIMUM=3.5']
        compile_directory = build
    run(configure, flatpak)
    run(['cmake', '--build', compile_directory, '--target', 'extract-xiso'], flatpak)
    extractor = build / ('extract-xiso.exe' if target == 'win-amd64' else 'extract-xiso')
    if target == 'win-amd64':
        imports = inspect_dependencies(extractor, target)[extractor.name]['needed']
        if any(name.lower().startswith(('msvcp140', 'vcruntime140', 'concrt140', 'libgcc',
                                       'libstdc++', 'libwinpthread', 'libssp', 'msys-',
                                       'libc++', 'libunwind')) for name in imports):
            raise ValueError('The nested ISO extractor must use static compiler runtimes')
        # MSYS2's native MinGW distributions keep the notices for embedded CRT,
        # header helpers and libgcc (with its runtime exception) here.
        license_root = Path(compiler).parent.parent / 'share/licenses'
        notices = build / 'licenses'
        for component in ('crt', 'headers', 'gcc'):
            source_notices = list((license_root / component).glob('COPYING*'))
            if not source_notices:
                raise ValueError('Missing MinGW runtime notices under ' + str(license_root / component))
            destination = notices / ('mingw-' + component)
            destination.mkdir(parents=True, exist_ok=True)
            for path in source_notices:
                shutil.copy2(path, destination / path.name)
        write_json(build / 'extractor-record.json', {
            'schema': 1, 'owner': 'djultra64', 'source_commit': EXTRACT_XISO_PIN,
            'compiler': {'target': triple, 'version': subprocess.check_output(
                [compiler, '--version'], text=True).splitlines()[0]},
            'compiler_runtimes': 'static', 'system_imports': imports,
            'artifacts': {extractor.name: sha(extractor)},
            'licenses': files_manifest(notices)})
    return extractor


def bundle_installer(output, target, licenses):
    for name in ('install.py', 'install.sh', 'install.cmd'):
        shutil.copy2(ROOT / 'tools/port-build' / name, output / name)
    (output / 'install.sh').chmod(0o755)
    extractor = ROOT / 'build/iso-extractor' / target / ('extract-xiso.exe' if target == 'win-amd64' else 'extract-xiso')
    if not extractor.is_file():
        raise ValueError('Build the pinned ISO extractor before packaging')
    support = output / 'support'
    support.mkdir(exist_ok=True)
    shutil.copy2(extractor, support / extractor.name)
    shutil.copy2(ROOT / '.cache/extract-xiso/LICENSE.TXT', licenses / 'extract-xiso-LICENSE.TXT')
    if target == 'win-amd64':
        build = extractor.parent
        extractor_record = json.loads((build / 'extractor-record.json').read_text())
        if extractor_record['artifacts'] != {extractor.name: sha(extractor)}:
            raise ValueError('ISO extractor differs from its build record')
        if extractor_record['licenses'] != files_manifest(build / 'licenses'):
            raise ValueError('ISO extractor license notices differ from the build record')
        shutil.copy2(build / 'extractor-record.json', support / 'extractor-build.json')
        shutil.copytree(build / 'licenses', licenses / 'extract-xiso-runtime')
        for name in ('getopt.c', 'dirent.c'):
            # Keep the complete upstream notices with the small compatibility
            # sources so licenses at either end of a file remain intact.
            shutil.copy2(ROOT / '.cache/extract-xiso/win32' / name,
                         licenses / ('extract-xiso-win32-' + name))


def package_port(target, output, dry_run=False):
    home, sdk, _, build = layout(target)
    record = json.loads((build / 'build-record.json').read_text())
    if record['target'] != target:
        raise ValueError('Target mismatch')
    artifacts = validate_stage(build / 'stage', record)
    for name, digest in record['sdk']['patches'].items():
        if sha(patch_file(name)) != digest:
            raise ValueError('Patch changed since build: ' + name)
    if sha(home / 'sdk-inputs.json') != record['sdk_inputs_sha256']:
        raise ValueError('SDK source provenance changed since build')
    if dry_run:
        print(json.dumps({'target': target, 'artifacts': artifacts,
                          'game_assets_included': False, 'output': str(output)}, indent=2))
        return
    if output.exists():
        raise ValueError('Package destination already exists')
    output.mkdir(parents=True)
    for name in artifacts:
        shutil.copy2(build / 'stage' / name, output / name)
    # Public provenance deliberately excludes compiler dumps, absolute paths,
    # private generated guest file lists and source SDK workstation records.
    public_record = {key: record[key] for key in (
        'owner', 'target', 'sdk', 'sdk_inputs_sha256', 'configuration', 'clock',
        'artifacts', 'runtime_redistributables') if key in record}
    public_record.update({'product': PRODUCT, 'version': VERSION, 'channel': 'release',
                          'backend': record.get('backend', 'Vulkan'), 'simulation_hz': 60,
                          'loader_dependencies': record.get('loader_dependencies', {})})
    write_json(output / 'build-record.json', public_record)
    licenses = output / 'licenses'
    licenses.mkdir()
    shutil.copy2(ROOT / 'patches/ReXGlue-LICENSE', licenses / 'ReXGlue-LICENSE')
    if record.get('runtime_redistributables'):
        (licenses / 'Microsoft-Visual-C-Runtime-NOTICE.txt').write_text(
            'Microsoft Visual C++ Runtime Libraries\n'
            'Copyright (c) Microsoft Corporation. All rights reserved.\n'
            'Release redistributable files from the licensed Visual Studio installation.\n'
            'Redistribution information and applicable product license terms:\n'
            'https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files\n'
            'https://visualstudio.microsoft.com/license-terms/\n', encoding='utf-8')
    # Preserve third-party licenses, including those embedded in SDK dependencies.
    for path in sorted((sdk / 'thirdparty').rglob('*')):
        if path.is_file() and path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
            destination = licenses / path.relative_to(sdk / 'thirdparty')
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
    for name in ('tools/frontend_overrides.py', 'tools/port-input/build_glyph_overrides.py',
                 'tools/port-input/original-glyph-hashes.json'):
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    shutil.copy2(ROOT / 'tools/port-build/launch.py', output / 'launch.py')
    bundle_installer(output, target, licenses)
    if target == 'win-amd64':
        (output / 'launch.cmd').write_text(
            '@echo off\nrem Project work: djultra64\n'
            'where py >nul 2>nul\nif errorlevel 1 goto fallback_python\n'
            'py -3 "%~dp0launch.py" %*\nexit /b %errorlevel%\n'
            ':fallback_python\npython "%~dp0launch.py" %*\nexit /b %errorlevel%\n',
            encoding='utf-8', newline='\r\n')
    else:
        launcher = output / 'launch.sh'
        launcher.write_text(
            '#!/bin/sh\n# Project work: djultra64\n'
            'scriptdir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd) || exit 1\n'
            'exec python3 "$scriptdir/launch.py" "$@"\n', encoding='utf-8')
        launcher.chmod(0o755)
    (output / 'support').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'config/input-manifest.json', output / 'support/input-manifest.json')
    if target == 'win-amd64':
        launch_command = 'launch.cmd'
        platform_help = (
            'Windows 10/11 x64: run install.cmd to import your own local ISO, then launch.cmd.\n'
            'Install a current Vulkan 1.3 graphics driver for your graphics card.\n'
            'Required Microsoft Visual C++ Release runtime DLLs are included beside the game.\n')
    else:
        launch_command = './launch.sh'
        platform_help = (
            'Linux: run ./install.sh to import your own local ISO, then ./launch.sh.\n'
            'Requires glibc 2.38+, libstdc++ providing GLIBCXX_3.4.32 (GCC 13.2+), libgcc and libm.\n'
            'Requires libX11-xcb.so.1, libX11.so.6, libxcb.so.1 and libwayland-client.so.0.\n'
            'Install the Vulkan loader and a working Vulkan 1.3 GPU driver.\n'
            'Desktop display/audio/input services are provided by your Linux system.\n')
    (output / 'README.txt').write_text(
        PRODUCT + ' v1.0.1\nProject work: djultra64\n'
        'ReXGlue and dependencies retain their respective authors and licenses.\n'
        'Native 60 Hz gameplay with original game speed and slow motion. ' + public_record['backend'] + ' renderer.\n'
        'Original game assets are not included. Supply your verified supported USA game data.\n'
        'Requires Python 3.12+ and an x86-64-v2 CPU.\n'
        + platform_help +
        'First launch also offers installation; no game data is downloaded.\n'
        'Existing extracted data: ' + launch_command + ' --game-data-root <absolute path>.\n'
        'Use --prepare-only to generate private overrides without opening the game.\n'
        'The supplied prep scripts verify original asset pins; derived assets remain private.\n'
        'Keep saves/settings and shader caches outside this package.\n'
        'The runtime, Xenos GPU plugin, SDL3 and ISO extractor are bundled.\n'
        'Build and package hashes are recorded.\n', encoding='utf-8')
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md',
                 'docs/beta/release-notes-1.0.1.md', 'docs/beta/installation.md'):
        destination = output / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    with (output / 'README.txt').open('a', encoding='utf-8') as readme:
        readme.write('This product includes software developed by in <in@fishtank.com>.\n')
        if target == 'win-amd64':
            readme.write('This product includes software developed by the Apache Software Foundation (http://www.apache.org/).\n')
    write_json(output / 'package-manifest.json', {'schema': 1, 'target': target,
               'product': PRODUCT, 'version': VERSION, 'channel': 'release',
               'iso_extractor_commit': EXTRACT_XISO_PIN,
               'owner': 'djultra64', 'game_assets_included': False,
               'files': files_manifest(output)})
    print('Package created:', output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'sdk-build', 'build', 'package'])
    parser.add_argument('--target', choices=sorted(TARGETS.values()))
    parser.add_argument('--jobs', type=int, default=2)
    parser.add_argument('--flatpak', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--extractor-compiler', help='Native MinGW-w64 C compiler for the Windows ISO extractor')
    args = parser.parse_args()
    target = args.target or TARGETS.get(platform.system())
    if target is None or args.jobs < 1:
        parser.error('Linux/Windows x86-64 and positive --jobs required')
    if args.action != 'package' and (TARGETS.get(platform.system()) != target or platform.machine().lower() not in {'amd64', 'x86_64'}):
        parser.error('Build on the native target OS and architecture')
    if args.flatpak and target != 'linux-amd64':
        parser.error('Flatpak is Linux only')
    if args.dry_run and args.action != 'package':
        parser.error('--dry-run applies only to package')
    if args.action == 'prepare':
        prepare(target)
    elif args.action in {'build', 'sdk-build'}:
        build_port(target, args.jobs, args.flatpak, sdk_only=args.action == 'sdk-build')
        if args.action == 'build':
            build_extractor(target, args.flatpak, args.extractor_compiler)
    else:
        output = args.output or ROOT / 'dist' / ('fight-night-round-3-recomp-v1.0.1-' + target)
        package_port(target, output.resolve(), args.dry_run)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
