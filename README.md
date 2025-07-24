[![Discord](https://img.shields.io/badge/chat-on%20discord-7289da.svg?sanitize=true)](https://discord.gg/GUAy9wErNu)
[![](https://img.shields.io/discord/908084610158714900)](https://discord.gg/GUAy9wErNu)
[![Static Badge](https://img.shields.io/badge/github-assemblyline-blue?logo=github)](https://github.com/CybercentreCanada/assemblyline)
[![Static Badge](https://img.shields.io/badge/github-assemblyline\_service\_lookyloo-blue?logo=github)](https://github.com/CybercentreCanada/assemblyline-service-lookyloo)
[![GitHub Issues or Pull Requests by label](https://img.shields.io/github/issues/CybercentreCanada/assemblyline/service-lookyloo)](https://github.com/CybercentreCanada/assemblyline/issues?q=is:issue+is:open+label:service-lookyloo)
[![License](https://img.shields.io/github/license/CybercentreCanada/assemblyline-service-lookyloo)](./LICENSE)
# Lookyloo Service

This Assemblyline service extracts artifacts and captures from potentially malicious URLs using Lookyloo.

## Overview

This service deploys a local docker instance of [Lookyloo](https://github.com/Lookyloo/lookyloo) and utilizes [PyLookyloo](https://github.com/Lookyloo/PyLookyloo?tab=readme-ov-file) to extract and return artifacts from URLs to Assembyline.

It is developed to replace the [Proof of Concept](https://github.com/Government-of-Yukon-IT-Security/assemblyline-service-lacus) module that was created during GeekWeek 10.

`PyLookyloo` is utilized for all calls to Lookyloo to ensure future compatibility is maintained with feature changes.

### Acknowledgements

This service is based on the heavy work done by the following people, which can be found in [this repository](https://github.com/Government-of-Yukon-IT-Security/assemblyline-service-lookyloo).

- [Government of Yukon/Thomas Dang](https://github.com/litobro)
- [CIRCL/Raphaël Vinot](https://github.com/Rafiot)
- [CCCS Assemblyline Team](https://github.com/cybercentrecanada)

## Image variants and tags

Assemblyline services are built from the [Assemblyline service base image](https://hub.docker.com/r/cccs/assemblyline-v4-service-base),
which is based on Debian 11 with Python 3.11.

Assemblyline services use the following tag definitions:

| **Tag Type** | **Description**                                                                                  |      **Example Tag**       |
| :----------: | :----------------------------------------------------------------------------------------------- | :------------------------: |
|    latest    | The most recent build (can be unstable).                                                         |          `latest`          |
|  build_type  | The type of build used. `dev` is the latest unstable build. `stable` is the latest stable build. |     `stable` or `dev`      |
|    series    | Complete build details, including version and build type: `version.buildType`.                   | `4.5.stable`, `4.5.1.dev3` |

## Running this service

This is an Assemblyline service. It is designed to run as part of the Assemblyline framework.

If you would like to test this service locally, you can run the Docker image directly from the a shell:

    docker run \
        --name Lookyloo \
        --env SERVICE_API_HOST=http://`ip addr show docker0 | grep "inet " | awk '{print $2}' | cut -f1 -d"/"`:5003 \
        --network=host \
        cccs/assemblyline-service-lookyloo

To add this service to your Assemblyline deployment, follow this
[guide](https://cybercentrecanada.github.io/assemblyline4_docs/developer_manual/services/run_your_service/#add-the-container-to-your-deployment).

## Documentation

General Assemblyline documentation can be found at: https://cybercentrecanada.github.io/assemblyline4_docs/

# Service Lookyloo

Ce service d'Assemblyline extrait les différents éléments et capture les informations des URLs potentiellement malicieuses en utilisant Lookyloo.

## Aperçu

Ce service déploie une instance locale de [Lookyloo](https://github.com/Lookyloo/lookyloo) et utilise [PyLookyloo](https://github.com/Lookyloo/PyLookyloo?tab=readme-ov-file) pour extraire et renvoyer les artefacts des URLs à Assembyline.

Il est développé pour remplacer la [preuve de concept](https://github.com/Government-of-Yukon-IT-Security/assemblyline-service-lacus) qui a été créée pendant GeekWeek 10.

`PyLookyloo` est utilisé pour tous les appels à Lookyloo pour s'assurer que la compatibilité sera maintenue avec les futurs changements de fonctionnalités.

### Remerciements

Ce service est basé sur le travail considérable effectué par les personnes suivantes, qui peuvent être trouvées dans [ce dépôt](https://github.com/Government-of-Yukon-IT-Security/assemblyline-service-lookyloo).

- [Gouvernement du Yukon/Thomas Dang](https://github.com/litobro)
- [CIRCL/Raphaël Vinot](https://github.com/Rafiot)
- [Équipe d'Assemblyline du CCCS](https://github.com/cybercentrecanada)

## Variantes et étiquettes d'image

Les services d'Assemblyline sont construits à partir de l'image de base [Assemblyline service](https://hub.docker.com/r/cccs/assemblyline-v4-service-base),
qui est basée sur Debian 11 avec Python 3.11.

Les services d'Assemblyline utilisent les définitions d'étiquettes suivantes:

| **Type d'étiquette** | **Description**                                                                                                |  **Exemple d'étiquette**   |
| :------------------: | :------------------------------------------------------------------------------------------------------------- | :------------------------: |
|   dernière version   | La version la plus récente (peut être instable).                                                               |          `latest`          |
|      build_type      | Type de construction utilisé. `dev` est la dernière version instable. `stable` est la dernière version stable. |     `stable` ou `dev`      |
|        série         | Détails de construction complets, comprenant la version et le type de build: `version.buildType`.              | `4.5.stable`, `4.5.1.dev3` |

## Exécution de ce service

Ce service est spécialement optimisé pour fonctionner dans le cadre d'un déploiement d'Assemblyline.

Si vous souhaitez tester ce service localement, vous pouvez exécuter l'image Docker directement à partir d'un terminal:

    docker run \
        --name Lookyloo \
        --env SERVICE_API_HOST=http://`ip addr show docker0 | grep "inet " | awk '{print $2}' | cut -f1 -d"/"`:5003 \
        --network=host \
        cccs/assemblyline-service-lookyloo

Pour ajouter ce service à votre déploiement d'Assemblyline, suivez ceci
[guide](https://cybercentrecanada.github.io/assemblyline4_docs/fr/developer_manual/services/run_your_service/#add-the-container-to-your-deployment).

## Documentation

La documentation générale sur Assemblyline peut être consultée à l'adresse suivante: https://cybercentrecanada.github.io/assemblyline4_docs/
