#!/usr/bin/env python3
"""Inject AudioQueue failures and verify callback lifetime; never opens microphone."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--zen', type=Path, default=root.parent / 'zen/zen')
parser.add_argument('--negative-control', action='store_true')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='zen-capture-state-') as directory:
    target = Path(directory)
    source = (root / 'src/audio.zen').read_text()
    checks = (root / 'tests/audio/disposal.zen').read_text()
    header = str(root / 'tests/audio/disposal.h')
    if args.negative_control:
        source = source.replace('token.to<Ptr<State>>().write(0, null_ptr<State>());', '();')
    source = source.replace('"AudioToolbox/AudioToolbox.h"', json.dumps(header))
    source = source.replace('"stdlib.h"', json.dumps(header))
    source = source.replace('AudioQueue', 'TestAudioQueue')
    source = source.replace('malloc*', 'test_malloc*').replace('free*', 'test_free*')
    source = source.replace('CallbackMemory.malloc', 'CallbackMemory.test_malloc')
    source = source.replace('CallbackMemory.free', 'CallbackMemory.test_free')
    checks = checks.replace('DISPOSAL_HEADER', header).replace('CallbackMemory.free', 'CallbackMemory.test_free')
    (target / 'main.zen').write_text(source + '\n' + checks)
    (target / 'build.zen').write_text('''Builder, BuildError = std.build
build = (b :: Builder) Res<(), BuildError> {
    macos = b.lib("macos", {src: Path(%s), libs: ["objc"], paths: []}).try();
    b.exe("check", {src: Path("main.zen"), deps: [macos], language: "objective-c",
        frameworks: ["AudioToolbox", "CoreFoundation"], out: Ok(Path("check"))}).try();
    Ok(())
}
''' % json.dumps(str(root / 'src/macos.zen')))
    env = dict(os.environ, ZEN_STD=str(root.parent / 'zen/src'))
    subprocess.run([str(args.zen.resolve()), 'build', '.'], cwd=target, env=env,
                   check=True, timeout=120)
    result = subprocess.run([str(target / 'check')], timeout=10)
    if args.negative_control:
        assert result.returncode != 0, 'negative control unexpectedly passed'
        print('missing callback detachment rejected')
    else:
        result.check_returncode()
