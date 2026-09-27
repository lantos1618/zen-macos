#!/usr/bin/env python3
"""Build/run the Zen hot loop; Python only orchestrates and summarizes batches."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone

root = Path(__file__).resolve().parents[1]
audio = root.name == 'zen-audio'
parser = argparse.ArgumentParser()
parser.add_argument('--zen', type=Path, default=root.parent / 'zen/zen')
parser.add_argument('--runs', type=int, default=3)
parser.add_argument('--notes', default='Shared desktop; background tasks not controlled.')
args = parser.parse_args()
if args.runs < 1:
    parser.error('--runs must be positive')
compiler = args.zen.resolve()
logs = root / 'build/benchmarks'
logs.mkdir(parents=True, exist_ok=True)
source = root / 'src/audio.zen'
def cpu_name():
    if os.environ.get('ZEN_BENCH_CPU'):
        return os.environ['ZEN_BENCH_CPU']
    result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True, capture_output=True)
    return result.stdout.strip() if result.returncode == 0 else 'unavailable; architecture recorded'

metadata = {
    'utc': datetime.now(timezone.utc).isoformat(),
    'os': platform.platform(), 'architecture': platform.machine(),
    'cpu': cpu_name(),
    'clang': subprocess.check_output(['/usr/bin/clang', '--version'], text=True).strip(),
    'zen': str(compiler), 'zen_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(),
    'library_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'background_work': args.notes,
    'runs': args.runs, 'batches_per_run': 31, 'iterations_per_batch': 1000,
    'warmup_iterations_per_run': 1000,
}
(logs / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
results = []
with tempfile.TemporaryDirectory(prefix='zen-hot-benchmark-') as directory:
    target = Path(directory)
    main = (root / 'benchmarks/main.zen').read_text()
    if not audio:
        main = source.read_text() + '\n' + main
    (target / 'main.zen').write_text(main)
    dependency = 'audio' if audio else 'macos'
    dependency_source = source if audio else root / 'src/macos.zen'
    frameworks = ['QuartzCore'] if audio else ['QuartzCore', 'AudioToolbox', 'CoreFoundation']
    (target / 'build.zen').write_text('''Builder, BuildError = std.build
build = (b :: Builder) Res<(), BuildError> {
    lib = b.lib(%s, {src: Path(%s), libs: [%s], paths: []}).try();
    b.exe("bench", {src: Path("main.zen"), deps: [lib], language: "objective-c",
        frameworks: %s, out: Ok(Path("bench"))}).try();
    Ok(())
}
''' % (json.dumps(dependency), json.dumps(str(dependency_source)),
       json.dumps('m' if audio else 'objc'), json.dumps(frameworks)))
    wrapper = target / 'compiler.py'
    wrapper.write_text('''import json, os, subprocess, sys
with open(os.environ['ZEN_BENCH_COMMAND_LOG'], 'a') as output:
    output.write(json.dumps(['/usr/bin/clang'] + sys.argv[1:]) + '\\n')
raise SystemExit(subprocess.call(['/usr/bin/clang'] + sys.argv[1:]))
''')
    for optimization in ['-O0', '-O2']:
        label = optimization[1:]
        command_log = logs / (label + '-commands.jsonl')
        command_log.write_text('')
        env = dict(os.environ)
        env.update(ZEN_STD=str(root.parent / 'zen/src'), CFLAGS=optimization + ' -Wno-parentheses-equality',
                   CC=shlex.join(['python3', str(wrapper)]), ZEN_BENCH_COMMAND_LOG=str(command_log))
        env.pop('ZEN_BUILD_OUTPUT', None)
        env.pop('ZEN_BUILD_DIR', None)
        with (logs / (label + '-build.log')).open('w') as output:
            subprocess.run([str(compiler), 'build', '.'], cwd=target, env=env,
                           stdout=output, stderr=subprocess.STDOUT, check=True, timeout=120)
        values = []
        for run in range(args.runs):
            result = subprocess.run([str(target / 'bench')], text=True, capture_output=True,
                                    check=True, timeout=180)
            (logs / ('%s-run%d.log' % (label, run + 1))).write_text(result.stdout + result.stderr)
            batch = [float(line.split()[1]) for line in result.stdout.splitlines() if line.startswith('batch_us ')]
            if len(batch) != 31 or any(not math.isfinite(x) or x <= 0 for x in batch):
                raise RuntimeError('invalid timing output: ' + result.stdout)
            values.extend(batch)
        ordered = sorted(values)
        median = statistics.median(values)
        p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
        row = {'optimization': optimization, 'batch_samples': len(values), 'median_us': median,
               'p95_us': p95, 'median_60hz_percent': median / (1e6 / 60) * 100}
        results.append(row)
        print(json.dumps(row), flush=True)
(logs / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
workload = ('1024-point FFT → 32 voice bands → smoothing, 16 kHz mixed 1/3 kHz input; '
            'caller-owned f64 buffers, fixed 1/60-second smoothing step.' if audio else
            'Append 256 float32 samples to the production capture state, then discard 256 while '
            'retaining 160000 samples (10 seconds). Every iteration shifts the retained 640 KB prefix. '
            'This intentionally stresses discard frequency; real segmented consumers discard less often.')
lines = ['# Measured baseline', '', workload, '',
         'Measured ' + metadata['utc'] + ' on ' + metadata['cpu'] + ' (' + metadata['architecture'] + ').',
         metadata['os'], '', 'Compiler: `' + metadata['zen'] + '`; SHA-256 `' + metadata['zen_sha256'] + '`.',
         'Library SHA-256: `' + metadata['library_sha256'] + '`.',
         metadata['clang'].replace('\n', ' / '), '',
         '| CFLAGS optimization | Samples | Median µs/iteration | p95 µs/iteration | Median of 16.67 ms frame budget |',
         '|---|---:|---:|---:|---:|']
for row in results:
    lines.append('| %s | %d | %.3f | %.3f | %.3f%% |' % (row['optimization'], row['batch_samples'], row['median_us'], row['p95_us'], row['median_60hz_percent']))
lines += ['', 'Background workload: ' + metadata['background_work'], '', 'Each sample is a 1000-iteration batch mean, not a single-call latency. '
          'Each of %d processes warms 1000 iterations, then reports 31 batches. '
          'p95 is nearest-rank over the combined batch means.' % args.runs,
          'Timed sections allocate no buffers and print only after each batch. A checksum and validity checks keep results observable.',
          'The live app was not stopped. These measurements are from a shared desktop and are not a real-time guarantee. '
          'They exclude device capture, GPU presentation, model inference, actor transport, and end-to-end UI latency.',
          '', 'Reproduce: `python3 benchmarks/run.py --zen ' + shlex.quote(os.path.relpath(compiler, root)) + '`.',
          'Exact compiler argv, raw batches, metadata, and JSON results are in ignored `build/benchmarks/`.', '']
(root / 'benchmarks/RESULTS.md').write_text('\n'.join(lines))
