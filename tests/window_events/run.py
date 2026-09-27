#!/usr/bin/env python3
"""Exercise the real Objective-C close delegate without displaying a window."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix="zen-window-events-") as folder:
    work = Path(folder)
    (work / "main.zen").write_text((Path(__file__).parent / "main.zen").read_text())
    (work / "build.zen").write_text('''Builder, BuildError = std.build
build = (b :: Builder) Res<(), BuildError> {
    macos = b.lib("macos", {src: Path(%s), libs: ["objc"], paths: []}).try();
    b.exe("check", {src: Path("main.zen"), deps: [macos], language: "objective-c",
        frameworks: ["AppKit", "Foundation", "QuartzCore", "Metal", "AVFoundation", "AudioToolbox", "CoreFoundation"], out: Ok(Path("check"))}).try();
    Ok(())
}
''' % json.dumps(str(ROOT / "src/macos.zen")))
    env = dict(os.environ, ZEN_STD=str(ROOT.parent / "zen/src"),
               CFLAGS="-O2 -Wno-parentheses-equality")
    subprocess.run([str(ROOT.parent / "zen/zen"), "build", "."], cwd=work,
                   env=env, check=True, timeout=120)
    subprocess.run([str(work / "check")], env=env, check=True, timeout=15)
