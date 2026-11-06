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

### Pin the Flask 1.1 web stack

- **File:** `requirements.txt`
- **What changed:** `jinja2` -> `Jinja2==2.11.3`; added `Flask==1.1.4`, `Werkzeug==0.16.1`, `MarkupSafe==2.0.1`,
  `itsdangerous==1.1.0`, `click<8`.
- **Why:** tcapy's web apps run on Dash 1.20 / Flask 1.1, and its REST API on flask-restplus 0.13. Unpinned, pip installs
  newer releases that removed APIs these use. Each pin was tested by upgrading just that package:

  | Unpinned to | Result |
  |---|---|
  | Werkzeug 1.x | REST API fails: `cannot import name 'cached_property' from 'werkzeug'` |
  | Werkzeug 2.x | both web apps fail: `cannot import name 'BaseResponse' from 'werkzeug.wrappers'` |
  | MarkupSafe 2.1 | both web apps fail: `cannot import name 'soft_unicode' from 'markupsafe'` |
  | Jinja2 3.x | both web apps fail: `cannot import name 'escape' from 'jinja2'` |
  | itsdangerous 2.x | both web apps fail: `cannot import name 'json' from 'itsdangerous'` |
  | Flask 2.x | both web apps fail: `unexpected keyword argument 'unbound_message'` |

  `click<8` matches what Flask 1.1.4 (`click<8.0`) and Celery 5.0.5 (`click<8.0`) declare.
- **How tested:** with these pins both web apps (`tcapy_wsgi`, `tcapyboard_wsgi`) and `flask_restplus` import, and the
  web UI serves and runs TCA calculations on all pages. The failures above come from upgrading one package at a time
  in a copy of the working image.

### Pin SQLAlchemy to 1.3.24

- **File:** `requirements.txt`
- **What changed:** `sqlalchemy` -> `SQLAlchemy==1.3.24`.
- **Why:** unpinned, pip installs SQLAlchemy 2.0 (2.0.57 on Python 3.7), which removed APIs tcapy's SQL data sources
  use. Against the running MySQL, both directions fail:
  - writing trade data (`convert_csv_to_table`): `TypeError: __init__() got an unexpected keyword argument 'bind'`
  - reading trade data (`fetch_trade_order_data`): the query returns nothing and fails with
    `TypeError: object of type 'NoneType' has no len()`
- **How tested:** with 1.3.24, writing the sample orders to MySQL and reading the trades back both work (52 EURUSD trades
  for 1-12 May 2017), and the full test suite and web UI ran on it. SQLAlchemy 1.4.54 also passed this read/write check,
  but 1.3.24 is the version the full test suite was run with.

### Pin pymongo to 3.12.3

- **File:** `requirements.txt`
- **What changed:** added `pymongo==3.12.3` (it was not listed; arctic pulls it in unpinned).
- **Why:** arctic 1.79.4, which tcapy uses to store market tick data in MongoDB, requires pymongo but doesn't cap its
  version, so pip installs pymongo 4.x (4.7.3 on Python 3.7). pymongo 4 removed and changed APIs arctic relies on:
  writing market data to Arctic fails with `InvalidOperation: Cannot use MongoClient after close`.
- **How tested:** against the running MongoDB (4.4): with pymongo 3.12.3, writing one day of EURUSD ticks (35,443) to a
  new Arctic library and reading them back returns all 35,443; the full test suite's Arctic read/write tests pass. With
  pymongo 4.7.3 the same write fails as above (reads alone still work, which is why it isn't obvious at first).

### Pin numpy to 1.19.5

- **File:** `requirements.txt`
- **What changed:** `numpy` -> `numpy==1.19.5`.
- **Why:** unpinned, pip installs numpy 1.21.6 (the last release for Python 3.7). tcapy's pinned `pyarrow==2.0.0`
  can't convert numpy 1.20+ arrays, so TCA calculations fail when market data is converted:
  `ArrowTypeError: ('Did not pass numpy.dtype object', 'Conversion failed for column bid with type float32')`.
  numpy 1.20.3 fails the same way; 1.19.5 is the last 1.19 release and the newest that works with pyarrow 2.0.
- **How tested:** a detailed TCA calculation on the sample data (EURUSD, 1-12 May 2017, slippage vs arrival) runs with
  numpy 1.19.5 and fails with 1.20.3 and 1.21.6 as above. The full test suite and web UI ran on 1.19.5.
- **Note on results:** this is a library version, not a change to tcapy's calculation code. The original repo can't be
  built, so there's no earlier result to compare with. On 1.19.5 that calculation gives 25 trades, mean slippage
  -0.000013700306 and sum of arrival prices 27.2910554409 - identical with or without the Celery workers and with
  numba 0.53.1 or 0.56.4.

### Pin dask, distributed, cloudpickle and fsspec as a compatible set

- **File:** `requirements.txt`
- **What changed:** `dask` -> `dask==2.30.0`, `distributed` -> `distributed==2.30.1`, `cloudpickle==1.3.0` ->
  `cloudpickle==1.6.0`, `fsspec==0.3.3` -> `fsspec==0.8.7`.
- **Why:** these are used by pystore (tcapy's optional Parquet-on-disk market data store; `tcapy.data.databasesource`
  imports it, and it needs `dask.distributed`). The original file pinned `cloudpickle` and `fsspec` to old releases but
  left `dask` and `distributed` unpinned, so pip installs dask/distributed 2022.2.0, which need cloudpickle >= 1.5 and
  fsspec >= 0.6. pip reports both conflicts, and pystore then can't write:
  `AttributeError: 'LocalFileSystem' object has no attribute 'expand_path'`.
  The four are pinned together to one release set that works with each other and with pandas 1.0.5.
- **How tested:** with these pins, pystore writes and reads back a test series, `tcapy.data.databasesource` imports, and
  the full test suite and web UI ran on them. With the original pins, pip reports the two conflicts and the pystore write
  fails as above. (Leaving all four unpinned also passed the pystore check, but was not run through the full test suite.)

### Pin thrift to 0.16.0

- **File:** `requirements.txt`
- **What changed:** added `thrift==0.16.0` (not listed before; `fastparquet` pulls it in unpinned).
- **Why:** pip picks the newest thrift (0.25.0 at the time of the fix), which is source-only and declares a build
  requirement of `setuptools>=69`. setuptools 69 needs Python 3.8+, so on Python 3.7 the build stopped with
  "No matching distribution found for setuptools>=69". thrift 0.16.0 still builds on Python 3.7.
- **How tested:** the image build failed at thrift as above; with the pin it installs, and fastparquet (which uses it to
  read Parquet metadata) reads the sample market data file.
