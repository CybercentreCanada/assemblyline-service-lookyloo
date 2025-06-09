#!/bin/bash

set -e
set -x

/usr/bin/supervisord -c /opt/al_service/lookyloo/supervisord.conf