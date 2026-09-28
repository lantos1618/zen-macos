#!/usr/bin/env python3
"""Compile real playback plus synthetic state checks; never opens audio hardware."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
workspace = root.parent
parser = argparse.ArgumentParser()
parser.add_argument('--zen', type=Path, default=workspace / 'zen-actor-runtime/zen')
parser.add_argument('--std', type=Path, help='defaults to the compiler sibling src directory')
parser.add_argument('--platform', choices=['macos', 'ios', 'both'], default='both')
parser.add_argument('--ios-sdk', action='store_true', help='also syntax-check generated C against arm64 iPhoneOS SDK')
parser.add_argument('--negative-control', choices=['prefill', 'fade'], help='expect a deliberately broken implementation to fail')
args = parser.parse_args()
compiler = args.zen.resolve()
std = args.std.resolve() if args.std else compiler.parent / 'src'
platforms = ['macos', 'ios'] if args.platform == 'both' else [args.platform]
fixture = (Path(__file__).parent / 'state.zen').read_text()
for platform in platforms:
    source = (workspace / ('zen-' + platform) / 'src/voice_output.zen').read_text()
    playout = (workspace / 'zen-audio/src/playout.zen').read_text()
    if args.negative_control:
        old, new = {
            'prefill': ('PREFILL_PACKETS*: usize = 4', 'PREFILL_PACKETS*: usize = 1'),
            'fade': ('sample = sample * gain;', 'sample = sample;'),
        }[args.negative_control]
        assert old in playout, 'negative-control target missing'
        playout = playout.replace(old, new, 1)
    with tempfile.TemporaryDirectory(prefix='zen-playback-state-') as directory:
        target = Path(directory)
        (target / 'playout.zen').write_text(playout)
        (target / 'audio.zen').write_text('playout* = playout\n')
        (target / 'main.zen').write_text(source + '\n' + fixture)
        (target / 'build.zen').write_text('''Builder, BuildError = std.build
build = (b :: Builder) Res<(), BuildError> {
    macos = b.lib("macos", {src: Path(%s), libs: ["objc"], paths: []}).try();
    audio = b.lib("audio", {src: Path("audio.zen"), libs: [], paths: []}).try();
    b.exe("check", {src: Path("main.zen"), deps: [macos, audio], language: "objective-c",
        frameworks: ["AudioToolbox", "CoreFoundation"], out: Ok(Path("check"))}).try();
    Ok(())
}
''' % json.dumps(str(root / 'src/macos.zen')))
        subprocess.run([str(compiler), 'build', '.'], cwd=target,
                       env=dict(os.environ, ZEN_STD=str(std)), check=True, timeout=120)
        result = subprocess.run([str(target / 'check')], timeout=10)
        if args.negative_control:
            assert result.returncode == 1, f'expected assertion failure, got {result.returncode}'
            print(f'{platform}: rejected {args.negative_control} negative control')
        else:
            result.check_returncode()
            print(f'{platform}: playback state checks passed')
        if args.ios_sdk:
            sdk = subprocess.check_output(['xcrun', '--sdk', 'iphoneos', '--show-sdk-path'], text=True).strip()
            subprocess.run(['xcrun', '--sdk', 'iphoneos', 'clang', '-target', 'arm64-apple-ios17.0',
                            '-isysroot', sdk, '-fsyntax-only', '-x', 'objective-c',
                            str(target / 'build/.zen/check/program.c')], check=True, timeout=60)
            print(f'{platform}: arm64 iPhoneOS syntax check passed')
