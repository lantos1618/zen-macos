# Atomic file replacement

Run `python3 tests/file/run.py` from zen-macos. The headless native test checks
new-file creation, replacement, executable permissions and extended attributes,
fresh modification time, empty content, missing parents/sources, existing-file
collision, symlink refusal, and staging-file cleanup on successful and failed
publication. It neither launches UI nor accesses user documents.

`macos.file.replace(a, path, bytes, existing)` stages beside the destination,
writes and fsyncs the staged file, closes it, then publishes it. Pass a
short-lived scratch arena: temporary memory remains owned by that allocator
until its arena is destroyed. Native descriptors and staging paths are cleaned
up before return. New-file mode
uses an exclusive hardlink so an existing destination cannot be overwritten.
Existing-file mode preserves permissions, ACLs and extended attributes using
Darwin fcopyfile, refreshes access/modification time, then renames atomically.
New files start with mkstemp's private 0600 permissions. The parent must exist.
Final-component symlinks are refused, including dangling symlinks.

Applications must check external edits before calling this helper. Existing-file
rename still has a check-to-publication race with concurrent writers; it is not
compare-and-swap. Parent directories are resolved normally, and parent-directory
symlinks are allowed. It is not a security boundary against malicious directory
replacement. Directory fsync is not performed, so power-loss durability is not
promised. Filesystem write/sync failures report errors and retain the original
unless atomic publication already succeeded. Tests exercise practical native
failure paths but do not inject disk-full, short-write or fsync failures.
