ARG branch=latest
FROM cccs/assemblyline-v4-service-base:$branch

# Python path to the service class from your service directory
ENV SERVICE_PATH=lookyloo.lookyloo.Lookyloo

# Install apt dependencies
USER root
COPY pkglist.txt /tmp/setup/
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    $(grep -vE "^\s*(#|$)" /tmp/setup/pkglist.txt | tr "\n" " ") && \
    rm -rf /tmp/setup/pkglist.txt /var/lib/apt/lists/*

# Create folders for valkey and lookyloo
RUN cd /opt && mkdir valkey lookyloo && chown -R assemblyline:assemblyline valkey lookyloo

USER assemblyline

RUN pip install poetry

RUN cd /opt && \
    # Install valkey 8.0
    git clone https://github.com/valkey-io/valkey && \
    cd valkey && \
    git checkout 8.0 && \
    make && \
    cd /opt && \
    # Install latest version of Lookyloo
    git clone https://github.com/Lookyloo/lookyloo.git && \
    cd lookyloo && \
    mkdir -p cache user_agents scraped logs && \
    # Install the venv in project for easy root access
    poetry config virtualenvs.in-project true && \
    poetry install --no-interaction --no-ansi && \
    echo LOOKYLOO_HOME="'`pwd`'" > .env && \
    cp /opt/lookyloo/config/modules.json.sample /opt/lookyloo/config/modules.json && \
    # Disable all modules!
    sed -i 's/"enabled": true,/"enabled": false,/g' /opt/lookyloo/config/modules.json && \
    poetry run update --init

USER root
RUN /opt/lookyloo/.venv/bin/playwright install-deps

# Install python dependencies
USER assemblyline
COPY requirements.txt requirements.txt
RUN pip install \
    --no-cache-dir \
    --user \
    --requirement requirements.txt && \
    rm -rf ~/.cache/pip

# Copy service code
WORKDIR /opt/al_service
COPY . .

# Patch version in manifest
ARG version=1.0.0.dev1
USER root
RUN sed -i -e "s/\$SERVICE_TAG/$version/g" service_manifest.yml

# Switch to assemblyline user
USER assemblyline
