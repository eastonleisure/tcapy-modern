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

### Pin yfinance to 0.1.63

- **File:** `requirements.txt`
- **What changed:** added `yfinance==0.1.63` (not listed before; `findatapy` 0.1.19 pulls it in unpinned).
- **Why:** pip picks the newest yfinance, which requires `curl_cffi>=0.17`. No `curl_cffi` that new exists for
  Python 3.7 (PyPI only offers up to 0.6.0b7 here), so the build stopped with
  "No matching distribution found for curl_cffi>=0.17". yfinance 0.1.63 (2021, the findatapy 0.1.19 era) has no
  `curl_cffi` dependency. tcapy itself doesn't use yfinance; it's an optional Yahoo data source inside findatapy.
- **How tested:** the image build failed at `curl_cffi` as above; with the pin it installs, and findatapy and tcapy's
  data modules import. The Yahoo download path itself was not exercised.

### Pin importlib-metadata to 4.13.0

- **File:** `requirements.txt`
- **What changed:** added `importlib-metadata==4.13.0` (not listed before; Celery/kombu pull it in unpinned on
  Python 3.7).
- **Why:** importlib-metadata 5.0 removed the dict-style `entry_points().get(...)` interface. Celery 5.0.5 and kombu
  still call it, so with the newest release (6.7.0 on Python 3.7) Celery can't even be imported:
  `AttributeError: 'EntryPoints' object has no attribute 'get'`. The Celery worker container crashed on start, and any
  TCA run that uses the workers failed. 4.13.0 is the last release before 5.0.
- **How tested:** a multithreaded TCA calculation dispatched through a Celery worker (isolated on its own Redis
  database) succeeds with 4.13.0, with the same results as single-threaded. With importlib-metadata 6.7.0 it fails as
  above with both kombu 5.0.2 and kombu 5.2.4, so the fix is this pin rather than a kombu version.

### Pin multitasking to 0.0.10

- **File:** `requirements.txt`
- **What changed:** added `multitasking==0.0.10` (not listed before; `pystore` and `yfinance` pull it in unpinned).
- **Why:** multitasking 0.0.12 and later import `typing.TypedDict`, which only exists from Python 3.8. pystore imports
  multitasking, and `tcapy.data.databasesource` imports pystore, so on Python 3.7 everything that loads tcapy's data
  layer failed: both web apps and the Celery worker crashed at start with
  `ImportError: cannot import name 'TypedDict' from 'typing'`.
- **How tested:** with each version installed in a copy of the working image, `import pystore` and the web app import
  (`tcapy_wsgi`) both fail on 0.0.12 and 0.0.13 and work on 0.0.10 and 0.0.11. 0.0.10 is pinned because the full test
  suite and web UI were run with it.

### Pin tzlocal to 2.1

- **File:** `requirements.txt`
- **What changed:** added `tzlocal==2.1` (not listed before; arctic pulls it in unpinned).
- **Why:** arctic 1.79.4 calls `tzlocal.get_localzone().zone`. tzlocal 3.0+ returns a `zoneinfo` timezone, which has no
  `.zone` attribute (only the pytz-based 2.x did), so pip's newest release (5.1 on Python 3.7) breaks arctic's
  TICK_STORE format: `AttributeError: 'backports.zoneinfo.ZoneInfo' object has no attribute 'zone'`. tcapy's default
  Arctic format is CHUNK_STORE, which isn't affected, but TICK_STORE is a supported setting (`arctic_lib_type` in
  `constants.py`) and the test suite's Arctic read/write tests use it. Only arctic uses tzlocal here.
- **How tested:** wrote one day of EURUSD ticks (35,443) to Arctic in all three formats against the running MongoDB.
  With tzlocal 2.1, CHUNK_STORE, TICK_STORE and VERSION_STORE all write and read back 35,443 ticks. With tzlocal 5.1,
  TICK_STORE fails as above. The full test suite's five Arctic tests failed with this error before the pin and pass
  with it.

### chartpy 0.1.8 -> 0.1.10

- **File:** `requirements.txt`
- **What changed:** `chartpy==0.1.8` -> `chartpy==0.1.10`.
- **Why:** both web apps import `chartpy.dashboard` (`tcapy/vis/app_imports.py`: `from chartpy.dashboard import
  CallbackManager, SessionManager`), which chartpy 0.1.8 doesn't have, so they failed at start with
  `ModuleNotFoundError: No module named 'chartpy.dashboard'`. The module first appears in 0.1.9. chartpy only draws
  charts; it isn't involved in TCA calculations.
- **How tested:** installed each release into a copy of the working image and imported `chartpy.dashboard`,
  `tcapy_wsgi` and `tcapyboard_wsgi`: all fail on 0.1.8 and all work on 0.1.9, 0.1.10, 0.1.11 and 0.1.12. 0.1.10 is
  pinned because the full test suite and every web page (charts included) were run with it.

### Recompile fastparquet against the installed numpy

- **File:** `Dockerfile`
- **What changed:** after the main `pip install`, reinstall `fastparquet==0.4.1` from source with
  `--no-build-isolation`, so it compiles against the numpy already installed in the image.
- **Why:** fastparquet 0.4.1 has no wheel here, so pip compiles it. pip builds in an isolated environment and fetches
  the newest numpy for the build (1.21), while the image runs numpy 1.19.5 (pinned above). The compiled module then
  doesn't match the runtime numpy, and fastparquet fails to import:
  `ValueError: numpy.ndarray size changed, may indicate binary incompatibility. Expected 88 from C header, got 80`.
  tcapy reads Parquet files through it, so loading market data from Parquet (eg. the bundled sample data) failed with
  "No valid data".
- **How tested:** without the rebuild, `import fastparquet` fails as above and reading
  `test/resources/small_test_market_df.parquet` returns nothing. After the rebuild, fastparquet imports and the file
  reads in full (4,369,664 rows); the sample market data then loads into Arctic (2,100,186 EURUSD ticks).

### Pin python-dateutil to 2.9.0.post0

- **File:** `requirements.txt`
- **What changed:** added `python-dateutil==2.9.0.post0` (not listed before; pandas pulls it in unpinned).
- **Why:** pip's legacy resolver picks python-dateutil 3.0.0 for pandas, but botocore (part of boto3, tcapy's AWS/S3
  library) requires `python-dateutil<3.0.0`, so every build ended with
  "botocore 1.33.13 has requirement python-dateutil<3.0.0,>=2.1, but you'll have python-dateutil 3.0.0 which is
  incompatible". 2.9.0.post0 is the newest release both accept.
- **How tested:** in this branch's built image, with dateutil 3.0.0 and with 2.9.0.post0: a boto3 S3 client can be
  created, both web apps import, and the reference TCA calculation (EURUSD, 1-12 May 2017) gives identical results -
  25 trades, mean slippage -0.000013700306, sum of arrival prices 27.2910554409. So this resolves a declared conflict;
  no behaviour difference was observed either way.

### Add requirements.lock and install from it

- **Files:** `requirements.lock` (new), `Dockerfile`, `.dockerignore`
- **What changed:**
  - `requirements.lock` lists the exact version of every package in the built image (including the ones pulled in
    indirectly), generated with `pip freeze` from this branch's image.
  - The Dockerfile copies it in and installs with `pip install -r requirements.txt -c requirements.lock`, so
    `requirements.txt` still says what tcapy needs and the lock fixes which exact versions are used.
  - `.dockerignore` whitelists files individually, so `!requirements.lock` was added to let it into the build.
  - Dropped the `rm /tmp/tcapy/requirements.txt` cleanup (both files are needed by the same RUN step; they're tiny).
- **Why:** most of tcapy's dependencies are unpinned, and every fix in this section was a package whose newest release
  no longer works with this Python 3.7 / pandas 1.0 stack. Without a lock, any future rebuild can break the same way
  as soon as some package releases a new version. With it, rebuilds install exactly what was verified.
- **How tested:** the lock was generated from a clean build of this branch (no pip conflicts reported). The image was
  then rebuilt from scratch using the lock, and `pip freeze` of the new image was compared with the lock: identical.
  Both web apps import, and the reference TCA calculation gives the same results as before (25 trades, mean slippage
  -0.000013700306, sum of arrival prices 27.2910554409).
- **Regenerating:** after changing `requirements.txt`, build the image and run
  `docker run --rm <image> pip freeze | grep -viE '^(pip|setuptools|wheel)=='` into `requirements.lock`
  (keep the header comment).

---

## Infrastructure

### nginx: resolve the app containers per request

- **File:** `tcapy/conf/tcapy_nginx_gunicorn_docker.conf`
- **What changed:** added `resolver 127.0.0.11` (Docker's built-in DNS) and put the upstream names in variables
  (`set $tcapy_upstream gunicorn_tcapy;` etc.), with `proxy_pass http://$tcapy_upstream:8090;` (and the same for
  tcapyboard on 8092). The existing `rewrite ... break` that strips the `/tcapy` / `/tcapyboard` prefix is unchanged.
- **Why:** with a plain host name in `proxy_pass`, nginx looks up the gunicorn containers' IP addresses once, when it
  starts, and keeps them. Whenever a gunicorn container is recreated (eg. `docker compose up -d` after a rebuild) it
  gets a new address, and nginx keeps sending requests to the old one, so both apps return **502 Bad Gateway** until
  nginx itself is restarted. Using a variable makes nginx resolve the name through Docker's DNS at request time
  (cached for 10s).
- **How tested:** before the change, recreating the gunicorn containers left `http://localhost:9500/tcapy/` and
  `/tcapyboard/` returning 502 until `docker compose restart nginx`. With it, after
  `docker compose up -d --force-recreate --no-deps gunicorn_tcapy gunicorn_tcapyboard` both return 200 with no nginx
  restart. Pages, Dash callbacks, assets and CSV downloads under both prefixes work through it (the full web UI was
  tested this way).

### nginx: allow trade CSV uploads larger than 1 MB on tcapyboard

- **File:** `tcapy/conf/tcapy_nginx_gunicorn_docker.conf`
- **What changed:** `client_max_body_size 100m;` in the `/tcapyboard/` location.
- **Why:** tcapyboard's whole purpose is uploading a trade CSV. Dash sends the file base64-encoded inside a JSON request,
  about 1.35x the file's size, and nginx's default request limit is 1 MB. So any trade file over roughly 750 KB was
  rejected by nginx with **413 Request Entity Too Large** before tcapy saw it. Only `/tcapyboard/` is raised; the
  main app's limit is unchanged.
- **How tested:** a 3.1 MB trade CSV posted the way Dash does through an nginx container with the previous config got
  `413 Request Entity Too Large`; with this setting the request was passed through to gunicorn. In the browser,
  uploading 2.05 MB and 2.14 MB trade CSVs to tcapyboard (with this setting) reached tcapy, which read the files and
  validated them. (Those files were the sample trades repeated to exceed 1 MB, so tcapy then rejected their duplicated
  timestamps; a normal upload of the unrepeated sample computes all charts.)

### docker-compose.yml: pin MySQL to 8.0

- **File:** `docker-compose.yml`
- **What changed:** `image: mysql` -> `image: mysql:8.0`.
- **Why:** the untagged `mysql` image means `mysql:latest`, which is now MySQL 26.10. That version removed the
  `--default-authentication-plugin` option this service starts with, so the container refuses to start:
  `[ERROR] [MY-000067] [Server] unknown variable 'default-authentication-plugin=mysql_native_password'` followed by
  `Aborting`. tcapy then has no trade database. MySQL 8.0 is the newest series that still accepts the option, and it
  works with tcapy's `mysql-connector-python` 8.0.23.
- **How tested:** started `mysql:latest` (26.10.0) and `mysql:8.0` (8.0.46) with the same command: 26.10 aborts as
  above, 8.0 reaches "ready for connections". The stack has run on `mysql:8.0` throughout: trades and orders load into
  `trade_database`, and the web UI and test suite read them.

### docker-compose.yml: pin MongoDB to 4.4

- **File:** `docker-compose.yml`
- **What changed:** `image: mongo:latest` -> `image: mongo:4.4`.
- **Why:** `latest` changes underneath you (it is MongoDB 9.0 at the time of writing), and MongoDB data directories
  can't be opened by a much newer or older major version, so an unpinned image can stop an existing install from
  starting after a pull. 4.4 is the version the whole stack was verified on: market data loading, the web UI on every
  page, and the test suite's Arctic tests. It matches the pymongo 3.12 / arctic 1.79 generation tcapy uses.
- **Note:** MongoDB 4.4 reached end of life in February 2024 (no further security fixes). MongoDB 9.0 also passed an
  Arctic write/read check in all three storage formats, so moving to a supported version later is possible; it needs
  the market data reloaded, because a 4.4 data directory can't be opened by 8.0+ directly.
- **How tested:** the stack has run on `mongo:4.4` throughout: 2,100,186 EURUSD ticks loaded and read back, all web
  pages calculate from it, and the full test suite's Arctic tests pass.

### docker-compose.yml: pin nginx, Redis, memcached and Adminer

- **File:** `docker-compose.yml`
- **What changed:** `nginx:latest` -> `nginx:1.27`, `redis:alpine` -> `redis:7.4-alpine`, `memcached` ->
  `memcached:1.6`, `adminer` -> `adminer:4`.
- **Why:** untagged or `latest` images change whenever a new release is published, so the same compose file can start
  different software from one day to the next (exactly what broke the MySQL service). These are the series the stack
  was verified with. Each tag still receives that series' patch releases.
- **How tested:** the running stack uses exactly these images (nginx 1.27.5, Redis 7.4.12, memcached 1.6.45,
  Adminer 4): the web UI on every page, Redis caching of results, Celery tasks via Redis, the Celery result backend in
  memcached, and the Adminer page (HTTP 200) all work on them. The nginx config was validated with `nginx -t` on
  `nginx:1.27`.

### docker-compose.yml: remove the obsolete `version` key

- **File:** `docker-compose.yml`
- **What changed:** removed the first line, `version: '3.6'`.
- **Why:** Compose v2 ignores this key and prints a warning on every `docker compose` command:
  "the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion".
  Only the old Python Compose v1 (end-of-life since July 2023) used it; with it gone, v1 would no longer read this file.
  Docker Desktop's `docker-compose` command (used by the `Makefile`) is Compose v2, so `make` is unaffected.
- **How tested:** `docker compose config` on the file without the key reports no warning and resolves all ten services
  (nginx, jupyter, gunicorn_tcapy, gunicorn_tcapyboard, celery, redis, memcached, mongo, mysql, adminer). The running
  stack has used the file without this key.

### docker-compose.yml: remove the trailing `&` from the gunicorn commands (tidy-up)

- **File:** `docker-compose.yml`
- **What changed:** both gunicorn `command:` strings ended in `... tcapy_wsgi:application & ` (and the same for
  tcapyboard); the trailing `& ` is removed.
- **Why:** no behaviour change - this is to stop the file being misleading. `&` means "run in the background" in a
  shell. Compose doesn't run commands through a shell and drops it, so it has no effect today. But if the command were
  ever run through a shell (eg. moved into a script or `sh -c`), gunicorn would be sent to the background, the
  container's main process would exit, and the container would stop immediately.
- **How tested:** `docker compose config` shows the resolved commands end at `tcapy_wsgi:application` /
  `tcapyboard_wsgi:application` both with and without the `&` (Compose already dropped it); gunicorn only reads the
  first positional argument (`self.app_uri = args[0]`). The running stack uses the commands without it.

### docker-compose.yml: separate gunicorn log files for tcapyboard

- **File:** `docker-compose.yml`
- **What changed:** the `gunicorn_tcapyboard` service now writes `log/gunicorn_tcapyboard_access.log` and
  `log/gunicorn_tcapyboard_error.log` instead of the same `gunicorn_tcapy_*.log` files as the main app.
- **Why:** both gunicorn services mount the same `./log` folder and were configured with the same two file names, so
  the main app's and tcapyboard's requests and errors were interleaved in one pair of files, with nothing on each line
  saying which app wrote it. That makes a failing request or startup error hard to attribute.
- **How tested:** in the running stack's `log/` folder, `gunicorn_tcapy_error.log` contains startup lines from both
  apps (8 x "Listening at: http://0.0.0.0:8090" and 4 x "...:8092", written before the split), while since the split
  `gunicorn_tcapyboard_error.log` contains only tcapyboard's (8092) and `gunicorn_tcapyboard_access.log` only
  tcapyboard's requests.

### docker-compose.yml: drop nginx's unused port 80

- **File:** `docker-compose.yml`
- **What changed:** removed `- 80:80` from the nginx service's `ports`.
- **Why:** nothing listens on port 80. The mounted `tcapy_nginx_gunicorn_docker.conf` replaces nginx's default site and
  only defines `listen 9500`, so the published port 80 accepted connections and immediately reset them. It also
  occupied port 80 on the host for no benefit (and can clash with anything else using it). Both apps are served on
  9500 (`/tcapy/`, `/tcapyboard/`).
- **How tested:** ran `nginx:1.27` with this config and both ports published: port 80 gives a connection reset
  (curl exit 56, no HTTP response) and the container's only nginx listening socket is 9500, while 9500 serves
  `/tcapy/` (HTTP 200).

### docker-compose.yml: publish every port on 127.0.0.1 only

- **File:** `docker-compose.yml`
- **What changed:** each of the nine published ports is now bound to `127.0.0.1` (eg. `- 6379:6379` ->
  `- 127.0.0.1:6379:6379`), with a comment at the top of the file explaining how to expose one deliberately.
- **Why:** `- 6379:6379` publishes on all network interfaces, so the services could be reachable from other machines
  on the network (subject to the host's firewall). Several have no authentication at all: Redis (6379; results cache
  and Celery queue - anyone reaching it can read or flush it), memcached (11211; Celery results), and the web apps
  (9500 via nginx, 8090/8092 directly; tcapy has no login). The others are protected only by the passwords/token in
  `.tcapy.env` (MySQL 3306, MongoDB 27017, Adminer 8080, Jupyter 8888). Binding to 127.0.0.1 keeps everything usable
  from this computer while closing it to the network. The containers still reach each other over Docker's internal
  network, which this doesn't affect.
- **How tested:** the running stack has used exactly these bindings (`docker compose ps` shows `127.0.0.1:<port>`
  for all nine): the web UI at `http://localhost:9500/tcapy/` and `/tcapyboard/`, Jupyter at `http://localhost:8888`,
  Adminer at `http://localhost:8080`, and every container-to-container connection (gunicorn/celery to MySQL, MongoDB,
  Redis, memcached; nginx to gunicorn) work. Access from another machine was not tested (no second machine available).

---

## MySQL

### Use MySQL 8's default authentication instead of mysql_native_password

- **File:** `docker-compose.yml`
- **What changed:** removed `command: --default-authentication-plugin=mysql_native_password` from the mysql service, so
  new MySQL accounts use MySQL 8.0's default `caching_sha2_password`.
- **Why:** both the option and the `mysql_native_password` plugin are deprecated in MySQL 8.0 (MySQL logs
  "'default_authentication_plugin' is deprecated" and "'mysql_native_password' is deprecated and will be removed in a
  future release" on every start), and the option no longer exists in newer MySQL - it's why the image had to be
  pinned to 8.0. It was originally needed for older MySQL clients; tcapy's `mysql-connector-python` 8.0.23 supports
  `caching_sha2_password`.
- **How tested:** started two fresh MySQL 8.0 containers, one with the option and one without, and ran tcapy's own trade
  write and read (`DatabaseSourceMySQL.convert_csv_to_table` + `fetch_trade_order_data`) against each: both succeed
  (52 EURUSD trades read back). Without the option, root and `tcapyuser` are created with `caching_sha2_password` and
  neither deprecation warning appears. (The only remaining "deprecated" line, `--skip-host-cache`, comes from the
  official image's own entrypoint.)
- **Existing installs:** this only affects accounts created from now on. Accounts already in an existing data
  directory keep `mysql_native_password` and continue to work on MySQL 8.0. To move them over (keeping their
  passwords), run inside the mysql container:
  ```
  docker compose exec mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "
    ALTER USER \"root\"@\"%\" IDENTIFIED WITH caching_sha2_password BY \"$MYSQL_ROOT_PASSWORD\";
    ALTER USER \"root\"@\"localhost\" IDENTIFIED WITH caching_sha2_password BY \"$MYSQL_ROOT_PASSWORD\";
    ALTER USER \"$MYSQL_USER\"@\"%\" IDENTIFIED WITH caching_sha2_password BY \"$MYSQL_PASSWORD\";"'
  ```
  This was done on the development stack, which has run on `caching_sha2_password` since (web UI, notebooks and test
  suite all read/write MySQL).

### Give the MySQL user access to trade_database_test_harness on first start

- **Files:** `docker/mysql-init/10-tcapy-test-harness.sh` (new), `docker-compose.yml`
- **What changed:** a script that creates `trade_database_test_harness` and grants `MYSQL_USER` all privileges on it,
  mounted into the mysql service at `/docker-entrypoint-initdb.d`. The official MySQL image runs scripts there once,
  when it initialises an empty data directory.
- **Why:** the MySQL image only gives `MYSQL_USER` access to `MYSQL_DATABASE` (`trade_database`). tcapy's notebooks
  (eg. `populating_databases_for_tcapy.ipynb`) and test configuration use `trade_database_test_harness`, so loading
  trade data there failed with
  `1044 (42000): Access denied for user 'tcapyuser'@'%' to database 'trade_database_test_harness'`.
- **How tested:** started fresh MySQL 8.0 containers with and without the script mounted and ran tcapy's trade write
  and read against `trade_database_test_harness`. Without it: the access-denied error above. With it: the entrypoint
  logs `running /docker-entrypoint-initdb.d/10-tcapy-test-harness.sh`, `SHOW GRANTS` lists
  `GRANT ALL PRIVILEGES ON trade_database_test_harness.* TO tcapyuser`, and the write and read succeed (52 EURUSD
  trades). On the development stack, the populating notebook's trade-data section ran with this grant in place.
- **Existing installs:** the script only runs on an empty data directory. To apply it to an existing one, run it once
  inside the mysql container:
  ```
  docker compose exec -T mysql bash -s < docker/mysql-init/10-tcapy-test-harness.sh
  ```

---

## Jupyter

### Add a `jupyter` stage to the Dockerfile

- **File:** `Dockerfile`
- **What changed:** a new `jupyter` build stage on top of `builder` (the tcapy image). It adds a `jovyan` user (UID
  1000), copies `tcapy_notebooks`, `tcapy_scripts`, `tcapy_examples`, `test` and `tcapy` into its home directory, and
  runs the classic Jupyter Notebook server on port 8888.
- **Why:** the jupyter service was built from `binder/Dockerfile`, whose base image `tschm/jupyter:1.2.0` has been
  removed from Docker Hub ("pull access denied ... repository does not exist"), so the service could not be built at
  all. Building on the tcapy image reuses its pinned packages - `notebook` 6.4.12, `nbconvert` 6.0.7, `jupyterlab`
  2.3.2 are already in `requirements.txt`/`requirements.lock` - so the notebooks run against exactly the same
  tcapy/pandas/numpy as the web apps. The copied folders recreate the repo-root layout the notebooks expect
  (`../test/resources/`, `../tcapy/vis/report/templates/`), as the old binder image did by copying the whole repo.
- **Access token:** Jupyter reads `JUPYTER_TOKEN` (eg. put `JUPYTER_TOKEN=<random string>` in `.tcapy.env`). Without
  it, Jupyter generates a token and prints the login URL in `docker compose logs jupyter`.
- **How tested:** see the next entry (tested together with the compose service).

### docker-compose.yml: build the jupyter service from the new stage

- **File:** `docker-compose.yml`
- **What changed:** the jupyter service's build now uses `dockerfile: Dockerfile`, `target: jupyter` instead of
  `dockerfile: binder/Dockerfile`, `target: builder`.
- **Why:** `binder/Dockerfile` can't be built (its base image no longer exists), so `docker compose up` / `build`
  failed for this service. `binder/Dockerfile` itself is left unchanged; it is no longer used by docker-compose.
- **How tested:** `docker compose build jupyter` builds; the container starts Jupyter Notebook 6.4.12 and serves the
  notebook list (`/tree`, HTTP 200 with the token; the login page without it). In a notebook kernel (run with
  `jupyter nbconvert --execute`), tcapy, pandas and plotly import, the sample market data reads from
  `../test/resources/`, and the running MongoDB and MySQL are reachable (market ticks and trades read back).

### docker-compose.yml: mount `test/` and `tcapy/` into the jupyter home directory

- **File:** `docker-compose.yml`
- **What changed:** two more volumes on the jupyter service: `./test:/home/jovyan/test` (read-write) and
  `./tcapy:/home/jovyan/tcapy:ro`, alongside the existing `tcapy_notebooks` and `tcapy_scripts` mounts.
- **Why:** the notebooks use relative paths into the repo: `../test/resources/` for sample data and
  `../tcapy/vis/report/templates/` for report templates. Without these mounts they failed with
  "CSV file not found ../test/resources/small_test_trade_df.csv". The image has copies, but mounting the live folders
  keeps them in step with the working tree (as is already done for the notebooks). `test/` is writable because
  `populating_databases_for_tcapy.ipynb` writes its dump files to `../test/resources/` (it failed with
  "Read-only file system" when mounted read-only); `tcapy/` is read-only.
- **How tested:** before the mounts, three notebooks stopped at "CSV file not found ../test/resources/...". With them,
  the notebooks get past those cells, and `populating_databases_for_tcapy.ipynb` loads the sample trades into MySQL,
  reads them back and writes its dump files to `test/resources/` (its market-data section then needs a Dukascopy
  download, see below).
- **Remaining notebook limits (not fixable here):** five notebooks download market data live from Dukascopy, which
  currently refuses findatapy's requests; `real_life_tcapy_case_study.ipynb` reads the original author's private file
  `e:/cuemacro/tcapy/external/trade_2017.csv`; `excel_xlwings_with_tcapy.ipynb` needs Microsoft Excel.

### docker-compose.yml: start the databases with the jupyter service

- **File:** `docker-compose.yml`
- **What changed:** the jupyter service's `depends_on` now also lists `mongo`, `mysql` and `memcached` (it had only
  `redis` and `celery`).
- **Why:** the notebooks read market data from MongoDB (Arctic), trades from MySQL, and use memcached as Celery's
  result store. With `docker compose up jupyter` on its own, Compose didn't start those, so notebook cells failed to
  connect. The tcapy web services already list the same dependencies.
- **How tested:** `docker compose config` shows the jupyter service depending on all five; from the jupyter container
  the notebook kernel reads from MongoDB and MySQL (see the build entry above).

---

## Corrections

### Pin numba to 0.53.1 (fixes market data writes broken since the build fix)

- **Files:** `requirements.txt`, `requirements.lock`
- **What changed:** `numba` -> `numba==0.53.1`; in the lock, `numba==0.56.4` -> `numba==0.53.1` and
  `llvmlite==0.39.1` -> `llvmlite==0.36.0` (numba 0.53.1 requires llvmlite < 0.37).
- **Why:** during the build fix, numba was left unpinned because a TCA calculation on already-loaded data gave
  identical results with numba 0.53.1 and 0.56.4 (see "Pin numpy to 1.19.5" above). That check never wrote market data.
  fastparquet 0.4.1 (which tcapy uses to write Parquet) is numba-compiled, and with numba 0.56.4 writing market data
  into Arctic from Parquet silently stores nothing: reading it back gives
  `NoDataFoundException: No data found for ['EURUSD-...']`, and the test suite's data fixture fails with
  `RuntimeError: numba jitted function aborted due to unresolved symbol`. So since the build fix, a fresh build could not
  load market data. numba 0.53.1 is the version the stack was originally verified with.
- **How tested:** loading the sample market data (`test/resources/small_test_market_df.parquet`) into Arctic and reading
  1 May back: fails with numba 0.56.4, returns 35,443 ticks with 0.53.1. A from-scratch rebuild with the updated lock
  matches it exactly (237 packages); both web apps import; the reference TCA calculation is unchanged (25 trades, mean
  slippage -0.000013700306, sum of arrival prices 27.2910554409). The full test suite was run with this fix (see the
  test stack section).

---

## Test stack (`docker-compose.test.yml`, Dockerfile `test` stage)

### Fix the test Redis startup option

- **File:** `docker-compose.test.yml`
- **What changed:** `redis-server --server_port 6379 --save ""` -> `redis-server --port 6379 --save ""`.
- **Why:** Redis has no `--server_port` option. The test Redis exited immediately with
  `*** FATAL CONFIG FILE ERROR *** Bad directive or wrong number of arguments` (exit code 1), so the test stack had no
  Redis - which tcapy uses for its results cache and as the Celery broker. `--port` is the correct option (and what
  the main `docker-compose.yml` uses).
- **How tested:** `redis-server --server_port 6379 --save ""` on `redis:7.4-alpine` exits with the error above;
  with `--port` Redis starts, and the test suite's Redis-backed tests run against it.
