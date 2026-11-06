# Set the base image to Ubuntu, use a public image
FROM python:3.7.7-slim-stretch as builder

# To build tests run
# docker-compose -f docker-compose.test.yml build

# File Author / Maintainer
# MAINTAINER Thomas Schmelzer "thomas.schmelzer@gmail.com"

# requirements.txt lists what tcapy needs; requirements.lock pins every package (including transitive ones) to the
# versions this image was verified with, so rebuilds don't silently pick up releases that break Python 3.7
COPY requirements.txt requirements.lock /tmp/tcapy/

# Dependencies for pystore and weasyprint in buildDeps
# If we don't want to use weasyprint we
# build-essential libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info
# Packages pip builds from source (eg. blosc) ship CMake files that CMake 4 refuses to configure without this
ENV CMAKE_POLICY_VERSION_MINIMUM=3.5

# Debian stretch is end-of-life, so its packages now live on archive.debian.org (and stretch-updates is gone)
RUN sed -i -e 's|deb.debian.org|archive.debian.org|g' -e 's|security.debian.org|archive.debian.org|g' \
        -e '/stretch-updates/d' /etc/apt/sources.list && \
    buildDeps='gcc g++ libsnappy-dev unixodbc-dev build-essential libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info' && \
    apt-get update && apt-get install -y $buildDeps --no-install-recommends && \
    pip install --no-cache-dir -r /tmp/tcapy/requirements.txt -c /tmp/tcapy/requirements.lock
    # && \
    #apt-get purge -y --auto-remove $buildDeps

# fastparquet 0.4.1 is built from source; pip's isolated build compiles it against a newer numpy than the
# pinned runtime one (ndarray size mismatch), so rebuild it against the installed numpy
RUN pip install --no-cache-dir --no-build-isolation --no-binary fastparquet --force-reinstall --no-deps fastparquet==0.4.1

# Copy to /
COPY ./tcapy /tcapy/tcapy
COPY ./tcapygen /tcapy/tcapygen
COPY ./tcapyuser /tcapy/tcapyuser
COPY ./test /tcapy/test
COPY ./test /test

# Make sure tcapy on the PYTHONPATH
ENV PYTHONPATH "${PYTHONPATH}:/tcapy"

#### Jupyter notebook server with tcapy (replaces binder/Dockerfile's base image, tschm/jupyter:1.2.0, which no longer
#### exists). The notebook packages (notebook, nbconvert, jupyterlab, ...) are already in requirements.txt / the lock.
FROM builder as jupyter

ARG NB_USER=jovyan
ARG NB_UID=1000
ENV NB_USER=${NB_USER} HOME=/home/${NB_USER}

RUN useradd -m -s /bin/bash -u ${NB_UID} ${NB_USER}

# Same layout as the repo root, which the notebooks rely on (eg. ../test/resources/, ../tcapy/vis/report/templates/)
COPY --chown=${NB_UID} ./tcapy_notebooks ${HOME}/tcapy_notebooks
COPY --chown=${NB_UID} ./tcapy_scripts ${HOME}/tcapy_scripts
COPY --chown=${NB_UID} ./tcapy_examples ${HOME}/tcapy_examples
COPY --chown=${NB_UID} ./test ${HOME}/test
COPY --chown=${NB_UID} ./tcapy ${HOME}/tcapy

USER ${NB_USER}
WORKDIR ${HOME}

EXPOSE 8888

# Access token: set JUPYTER_TOKEN (eg. in .tcapy.env); otherwise Jupyter generates one and prints it in the log
CMD ["jupyter", "notebook", "--ip=0.0.0.0", "--port=8888", "--no-browser"]

#### Here's the test-configuration
FROM builder as test

# We install some extra libraries purely for testing
RUN pip install --no-cache-dir httpretty pytest pytest-cov pytest-html sphinx mongomock requests-mock

WORKDIR /tcapy

# For temp caching for the tests
RUN mkdir -p /tmp/csv
RUN mkdir -p /tmp/tcapy

CMD echo "${RUN_PART}"

# Run the pytest
# If RUN_PART is not defined, we're not running on GitHub CI, we're running tests locally
# Otherwise if RUN_PART is defined, it's likely we're running on GitHub, so we avoid running multithreading tests which run
# out of memory (machines have limited memory)
CMD if [ "${RUN_PART}" = 1 ]; \
    then py.test --cov=tcapy  --cov-report html:artifacts/html-coverage --cov-report term --html=artifacts/html-report/report.html --ignore-glob='*multithreading*.py'; \
    else py.test --cov=tcapy  --cov-report html:artifacts/html-coverage --cov-report term \
        --html=artifacts/html-report/report.html; \
    fi

# Run everything
# CMD py.test --cov=tcapy  --cov-report html:artifacts/html-coverage --cov-report term \
#        --html=artifacts/html-report/report.html

# Example to run a specific test script
# CMD py.test --cov=tcapy  --cov-report html:artifacts/html-coverage --cov-report term \
#    --html=artifacts/html-report/report.html test/test_tcapy/test_tca_multithreading.py

# Example to run an individual test function
# CMD py.test --cov=tcapy  --cov-report html:artifacts/html-coverage --cov-report term \
#    --html=artifacts/html-report/report.html test/test_tcapy/test_data_read_write.py::test_write_trade_data_sql

# For debugging to keep container going
# CMD tail -f /dev/null
