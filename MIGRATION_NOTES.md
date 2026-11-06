# Migration notes

Changes made to get tcapy (cuemacro master `6a06f73`, tag `v0.1.2`) building and running again with Docker on
Ubuntu/WSL2. One entry per commit, in the order they were made.

Calculation-affecting changes are not listed here until approved; see `TCA_QUESTIONS.md`.

---

## Build fix

### Use archive.debian.org for Debian stretch packages

- **File:** `Dockerfile`
- **What changed:** before `apt-get update`, rewrite `/etc/apt/sources.list` to use `archive.debian.org` and drop the
  `stretch-updates` suite.
- **Why:** the base image `python:3.7.7-slim-stretch` is Debian 9 (stretch), which is end-of-life. Its packages were
  moved from `deb.debian.org`/`security.debian.org` to `archive.debian.org`, and `stretch-updates` no longer exists,
  so `apt-get update` fails with `404 Not Found` and the image can't be built.
- **How tested:** in an unmodified `python:3.7.7-slim-stretch` container, `apt-get update` fails with 404 for all
  three suites. After the rewrite it succeeds, and the image's `apt-get install` of the build dependencies completes.

### Let CMake 4 configure older packages built from source

- **File:** `Dockerfile`
- **What changed:** `ENV CMAKE_POLICY_VERSION_MINIMUM=3.5` before the `pip install` step.
- **Why:** `blosc==1.8.3` has no wheel for this platform, so pip compiles it with scikit-build, which downloads the
  latest CMake (4.x). CMake 4 removed compatibility with projects declaring a minimum CMake version below 3.5, and
  stops with "Compatibility with CMake < 3.5 has been removed". The environment variable is CMake's documented way to
  configure such projects anyway; it changes nothing for packages that don't use CMake.
- **How tested:** without it the image build failed with `Failed building wheel for blosc` and the CMake error above.
  With it, blosc compiles and installs, and `import blosc` works in the built image.
