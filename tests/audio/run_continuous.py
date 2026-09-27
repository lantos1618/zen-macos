#!/usr/bin/env python3
"""Exercise actual private audio state without creating a microphone queue."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--zen', type=Path, default=root.parent / 'zen/zen')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='zen-capture-state-') as directory:
    target = Path(directory)
    source = (root / 'src/audio.zen').read_text()
    checks = (root / 'tests/audio/continuous.zen').read_text()
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
    subprocess.run([str(target / 'check')], check=True, timeout=10)
