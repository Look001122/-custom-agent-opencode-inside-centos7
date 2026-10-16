# Third-party software and source access

The original r1 kit keeps the upstream executable and runtime libraries unmodified.
The repository's MIT license covers the added scripts and documentation;
each third-party component retains its upstream license.

| Component | Version | License / notice |
|---|---|---|
| OpenCode official linux-x64-musl executable | 1.19.0 | [OpenCode MIT notice](licenses/OpenCode-LICENSE.txt) |
| musl | 1.2.5, Alpine revision r12 | [musl copyright and notices](licenses/musl-COPYRIGHT.txt) |
| libgcc / libstdc++ | GCC 14.2.0, Alpine revision r6 | [GPLv3](licenses/GCC-COPYING3.txt) and [GCC Runtime Library Exception 3.1](licenses/GCC-COPYING.RUNTIME.txt) |

## Obtaining corresponding source and packaging recipes

The runtime binary download URLs, package revisions, Alpine commit IDs,
corresponding source URLs, and packaging recipe directories are provided
alongside the binaries in `sources.lock.json` and `SOURCES.json`.

- OpenCode: https://github.com/anomalyco/opencode/tree/v1.19.0
- musl source archive: https://musl.libc.org/releases/musl-1.2.5.tar.gz
- GCC source archive, including libgcc and libstdc++:
  https://ftp.gnu.org/gnu/gcc/gcc-14.2.0/gcc-14.2.0.tar.xz
- For Alpine-specific patches and build instructions, open each runtime's
  `source_recipe` URL in `sources.lock.json`. Use the recorded commit and
  all files in its `main/musl` or `main/gcc` directory, not the latest branch.
- Upstream compiler/runtime dependencies inside the OpenCode executable
  remain part of the official distribution; consult the tagged OpenCode
  source, lockfile, and their upstream notices when rebuilding it.

The build script downloads prebuilt, hash-checked upstream components;
it packages them without recompilation or binary patching.

## XunChi source customization

The `xunchi-agent-centos7/` directory contains source modifications against a
pinned OpenCode commit, deployment helpers and tests. A rebuilt XunChi engine
is a modified OpenCode executable, unlike the original r1 kit. This repository
update does not include that internal binary bundle. Preserve OpenCode's MIT
notice and all applicable runtime notices when assembling one.

Company logos and derived branding graphics retain their respective ownership;
the code license does not grant company trademark or brand identity rights.
See `xunchi-agent-centos7/THIRD_PARTY_NOTICES.md` and `assets/NOTICE.md` there.
