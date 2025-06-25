FROM cccs/assemblyline-v4-service-base:stable

ENV SERVICE_PATH=lookyloo.lookyloo.LookyLoo 

# Build dependencies
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    supervisor git curl build-essential tcl python3 ffmpeg python3-dev

RUN pip3 install poetry

# Begin setting up
RUN mkdir -p /opt/al_service/app

WORKDIR /opt/al_service/app

# Install valkey
RUN git clone https://github.com/valkey-io/valkey
WORKDIR /opt/al_service/app/valkey
RUN git checkout 8.0
RUN make

# Get latest version of Lookyloo
WORKDIR /opt/al_service/app
RUN git clone https://github.com/Lookyloo/lookyloo.git

WORKDIR /opt/al_service/app/lookyloo

RUN mkdir -p cache user_agents scraped logs

RUN poetry install
RUN echo LOOKYLOO_HOME="'`pwd`'" > .env
RUN poetry run playwright install-deps
RUN chown -R assemblyline:assemblyline /opt/al_service

# Install the Lookyloo dependencies
USER assemblyline

WORKDIR /opt/al_service/app/lookyloo
RUN poetry install
RUN poetry run update --yes

# Copy the service files
USER root

WORKDIR /opt/al_service/
COPY . .
RUN chmod +x /opt/al_service/lookyloo/entrypoint.sh

RUN chown -R assemblyline:assemblyline /opt/al_service

# Clean up unnecessary files
RUN apt-get clean && apt-get autoremove -y 

# Set the user to assemblyline for running the service
USER assemblyline

WORKDIR /opt/al_service

# Install Python dependencies
RUN pip3 install --no-cache-dir --user --requirement requirements.txt && rm -rf ~/.cache/pip

# Set the entrypoint script
ENTRYPOINT ["/opt/al_service/lookyloo/entrypoint.sh"]