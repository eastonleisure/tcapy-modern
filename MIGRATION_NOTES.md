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

### Remove dtale and jupyter_contrib_nbextensions

- **File:** `requirements.txt`
- **What changed:** removed `dtale` and `jupyter_contrib_nbextensions` (both were unpinned).
- **Why:** both pull in web-framework versions that tcapy's Flask 1.1 / Dash 1.20 web apps can't run with:
  - `dtale` (latest for Python 3.7 is 3.22.0) upgrades Werkzeug to 2.2.3; Flask 1.1.4 needs Werkzeug < 2.0, and both
    web apps then fail at import with `cannot import name 'BaseResponse' from 'werkzeug.wrappers'`.
  - `jupyter_contrib_nbextensions` upgrades Jinja2 to 3.1.6; Flask 1.1.4 needs Jinja2 < 3.0, and the web apps fail.
  Nothing in tcapy, its scripts, examples or notebooks imports either package.
- **How tested:** installed each package on its own into a copy of the working image, then imported both web apps
  (`tcapy_wsgi`, `tcapyboard_wsgi`): both fail with each package, and both import fine without them.
  For comparison, `jupyter-dash` and `bqplot` were tested the same way, caused no conflicts, and are kept.

### Pin jupyterlab, jupyter_nbextensions_configurator and RISE to Jinja2 2.x-compatible releases

- **File:** `requirements.txt`
- **What changed:** `jupyterlab` -> `jupyterlab==2.3.2`, `jupyter_nbextensions_configurator` -> `==0.6.3`,
  `RISE` -> `RISE==5.7.1`, and added `notebook==6.4.12`, `nbconvert==6.0.7`, `nbclient==0.5.13`, `mistune==0.8.4`.
- **Why:** unpinned, these resolve to JupyterLab 3.6 / Notebook 6.5 / nbconvert 7.6, which require Jinja2 >= 3.0.
  tcapy's web stack (Flask 1.1, Dash 1.20) needs Jinja2 < 3.0, so pip keeps Jinja2 2.11 and these tools install
  broken: importing RISE or the configurator fails with
  `ContextualVersionConflict: Jinja2 2.11.3 ... Requirement.parse('jinja2>=3.0'), {'nbconvert'}`.
  The pinned releases are the newest that work with Jinja2 2.11, so the packages are kept rather than removed.
- **How tested:** in a copy of the working image (which has the Jinja2 2.11 / Flask 1.1 pins): installed the pinned
  set with no pip conflicts; both web apps still import; RISE and the configurator import; `jupyter lab` and
  `jupyter notebook` both start and serve their main pages (`/lab` and `/tree` return 200). The unpinned set was tested
  the same way and reproduced the conflict above.
