FROM python:3.12-slim AS base 
#sets py optimized , not root user and depenciees

#stops .pyc to disk keep container clean 
ENV PYTHONDONTWRITEBYTECODE=1

ENV PYTHONUNBUFFERED=1 
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
# create user and grp , never run web server as root 
RUN groupadd -g 1000 lms && \
    useradd -u 1000 -g lms -m -s /bin/bash lms

COPY requirements.txt ./
COPY wheels/ ./wheels/

#install run time dependency 
RUN if [ -n "$(find ./wheels -name '*.whl' 2>/dev/null)" ]; then \
        echo "Found offline wheels; installing without network..." && \
        pip install --no-cache-dir --no-index --find-links=wheels/ -r requirements.txt; \
    else \
        echo "No offline wheels found; installing from PyPI..." && \
        pip install --no-cache-dir -r requirements.txt; \
    fi

#=====runtime tagret : clean container img used to run live app===== 
FROM base AS runtime

#copy source 
COPY --chown=lms:lms . .

#ensure logs are not writable 
RUN mkdir -p instance logs && \
    chown -R lms:lms instance logs
    
USER lms

EXPOSE 5000

#health check , uses internal py urllib not winget or curl 
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request as u; u.urlopen('http://127.0.0.1:5000/', timeout=2)" || exit 1
#run dev server 
CMD ["flask", "--app", "app", "run", "--host", "0.0.0.0", "--port", "5000"]

#==test target ====
#used to automate offline test suite 

FROM base AS test

USER root

COPY requirements-dev.txt ./

# Install developer dependencies
RUN if [ -n "$(find ./wheels -name '*.whl' 2>/dev/null)" ]; then \
        pip install --no-cache-dir --no-index --find-links=wheels/ -r requirements-dev.txt; \
    else \
        pip install --no-cache-dir -r requirements-dev.txt; \
    fi

# Install Chromium browser for Playwright without failing on obsolete Debian package names
RUN playwright install chromium

# Copy remaining source code and tests
COPY --chown=lms:lms . .

# Switch back to non-root user
USER lms

# Default test command
CMD ["pytest", "tests/unit", "tests/integration", "-q"]
#debug

# RUN echo "[DEBUG] pip freeze (first 20):" && pip freeze | head -20     (keep as a commented line, enable when debugging builds)
# OFFLINE DOCKER TEST CASES:
# - docker build --target runtime . succeeds with the network disabled after wheels were vendored.
# - docker run --rm <image> id -u prints 1000 (non-root).
# - docker build --target test . then docker run --network none <image> python -c "import app" exits 0.
