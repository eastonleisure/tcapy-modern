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

### mysql-connector-python 8.0.19 -> 8.0.23

- **File:** `requirements.txt`
- **What changed:** `mysql-connector-python==8.0.19` -> `mysql-connector-python==8.0.23`.
- **Why:** 8.0.19 is no longer on PyPI, so `pip install` stopped with "No matching distribution found for
  mysql-connector-python==8.0.19". PyPI's list for this platform jumps from 8.0.5 to 8.0.23; 8.0.23 is the closest
  available release in the same 8.0 series.
- **How tested:** the image build gets past this package. In the running stack, tcapy connects to MySQL 8.0 with it:
  the sample trade/order CSVs load into `trade_database` and read back (184 trades, 89 orders), and TCA calculations
  that read trades from MySQL succeed in the web UI and from Python.

### eikon 1.1.2 -> 1.1.18

- **File:** `requirements.txt`
- **What changed:** `eikon==1.1.2` -> `eikon==1.1.18` (kept, not removed).
- **Why:** eikon 1.1.2 depends on `requests-async==0.6.2`, which is no longer on PyPI (only up to 0.2.4 remains), so
  `pip install` stopped with "No matching distribution found for requests-async==0.6.2". eikon 1.1.18 (Oct 2023, the
  last release) uses `httpx` instead and installs on Python 3.7. `findatapy` 0.1.19 also requires `eikon` (unpinned),
  so pip already installs 1.1.18 whenever the 1.1.2 pin is absent; this makes that explicit.
- **How tested:** the image builds with it, and `import eikon` works in the built image. Eikon is only used by the
  optional Refinitiv data source (`DatabaseSourceEikon` / `DatabasePopulatorEikon`, via findatapy); that path was
  **not** tested, as it needs a Refinitiv Eikon/Workspace login and API key.
