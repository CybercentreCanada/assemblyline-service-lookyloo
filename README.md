# assemblyline-service-lookyloo
 This Assemblyline service extracts artifacts and captures from potentially malicious URLs. 

## Overview

This service deploys a local docker instance of [Lookyloo](https://github.com/Lookyloo/lookyloo) and utilizes [PyLookyloo](https://github.com/Lookyloo/PyLookyloo?tab=readme-ov-file) to extract and return artifacts from URLs to Assembyline.

It is developed to replace the [Proof of Concept](https://github.com/Government-of-Yukon-IT-Security/assemblyline-service-lacus) module that was created during GeekWeek 10. 

## Architecture

LookyLoo is deployed as per the official documentation and docker deployment on the project Github page. `supervisord` is used to ensure all dependent services remain online as expected. This essentially runs the AssemblyLine process handler and allows poetry to handle the Lookyloo instance. 

`PyLookyloo` is utilized for all calls to Lookyloo to ensure future compatibility is maintained with feature changes. 

## Installation

This service is available on Docker Hub for installation. 

You can update the `service_manifest.yml` with the following information to get the latest stable version:

```
...
docker_config:
  image: docker.io/tkdangyukon/assemblyline-service-lookyloo:$SERVICE_TAG
...
```

It is recommended that you review the code base and understand what this service is doing before adding it to your AssemblyLine instance. At the very least, you should be comfortable running it and understanding how it operates. 

## Development

The Dockerfile can be built locally using `make run`, this will also run the container in the foreground. `make stop` can be used to terminate and remove running instances. `make run_once` can be used to execute and print a single test run using the test.yml data. 

Warning: The test data is not copied on every `run_once` but is copied on build time, you will want to rebuild prior to executing a test.

## TODO

- Add all available artifacts
- Upload to docker hub/ghcr
- Add browser settings (user agent etc.)
