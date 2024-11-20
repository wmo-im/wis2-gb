[![flake8](https://github.com/wmo-im/wis2-gb/workflows/flake8/badge.svg)](https://github.com/wmo-im/wis2-gb/actions)

# wis2-gb

### A Reference Implementation of a WIS2 Global Broker.

<a href="docs/GlobalBroker_C4.png"><img alt="WIS2 Global Broker C4 diagram" src="docs/GlobalBroker_C4.png" width="800"/></a>

## Workflow

- connects to a WIS2 Global Broker, subscribed to the following:
  - `origin/a/wis2/#`
  - `cache/a/wis2/#`
- connects to a WIS2 Global Cache, subscribed to the following:
  - `cache/a/wis2/#`
- connects to one or more WIS2 Nodes, subscribing to the following:
  - `origin/a/wis2/{centre_id}/#`
- on all notifications:
  - verfies message is WIS2 compliant
  - ensures the message is unique, not previously recieved from any other subscription
  - publishes the message to the Global Broker
  - performs metric accounting

## Installation

### Requirements

- [`Docker`](https://docker.com/)
- [`Docker Compose`](https://github.com/docker/compose/)
- python 3.10
- python requests==2.26.0
- python urllib3==1.26.0
- cmake
- docker plugin grafana/loki-docker-driver:2.9.2


### Dependencies
Dependencies are listed in [requirements.txt](requirements.txt). Dependencies
are automatically installed during pywis-pubsub installation.

### Installing wis2-gb

# clone codebase
git clone https://github.com/wmo-im/wis2-gb.git

# install system dependencies
cd wis2-gb
./platform-setup.sh

# select broker profile
./setup-links.sh brief

# build global broker containers
make build

# start global broker containers
make up


### Docker

The Docker setup uses Docker and Docker Compose to manage the following services:

- **redis**: [`Redis`](https://redis.io/docs/latest/get-started/) Data cache for de-duplication
- **global-broker**: [`Eclipse Misquitto`](https://mosquitto.org/) MQTT broker
- **wis2-relay**: MQTT subscription relay.  One container for each subscription to WIS2 participants, performs message verification and de-duplication and then publishes the message to the Global Broker.
- **grafana**: [`Grafana`](https://grafana.com/grafana/dashboards/) provides administrator dashboards, log monitoring and browsing prometheus metrics.
- **loki**: [`Grafana Loki`](https://grafana.com/docs/loki/latest/) provides administrator dashboards, log monitoring and browsing prometheus metrics.
- **prometheus**:[`Prometheus`](https://prometheus.io/) provides time-series metrics collections
- **metrics-collector**: Subscribes to message telemetry, complies metrics from Prometheus and exposes HTTP metric status endpoint.

See [`wis2-gb.env`](wis2-gb.env) for default environment variable settings.

Configurations for Wis2 Notification Message Verifiations are:

- **VERIFY_MESG**: Performs JSON Schema validation according to: [`wis2-notification-message`](https://github.com/wmo-im/wis2-notification-message)
- **VERIFY_DATA**: Notification messages with inline data exceeding 4096 bytes will have inline data truncated
- **VERIFY_TOPIC**: Perorms WIS2 topic validation according to: [`wis2-topic-hierarchy`](https://github.com/wmo-im/wis2-topic-hierarchy)  Must be "False" for GTS-to-WIS2 nodes.
- **VERIFY_METADATA**: Notification messages missing metadata will be discarded
- **VERIFY_CENTRE_ID**: Messages where the container assigned Centre-ID does not match the Centre-ID in the subscription topic.  

Several setups are pre-configured and implemented with soft links using **setup-links.sh**:

- **brief**: Small test configuration with global service participants
- **full**: Full compliment of WIS2 participants
- **func**: Functional test configuration compatible with [`Wis2-Global-Services-Testing`](https://github.com/wmo-im/wis2-global-services-testing/blob/main/global-services-testing/sections/testing/global-broker.adoc)


The [`Makefile`](Makefile) in the root directory provides options to manage the Docker Compose setup.

# build all images
make build

# build all images (no cache)
make force-build

# start all containers
make up

# start all containers in dev mode
make dev

# view all container logs in realtime
make logs

# login to the wis2-gb-management container
make login

# restart all containers
make restart

# shutdown all containers
make down

# remove all volumes
make rm

## Development

### Code Conventions

* [PEP8](https://www.python.org/dev/peps/pep-0008)

### Bugs and Issues

All bugs, enhancements and issues are managed on [GitHub](https://github.com/wmo-im/wis2-gb/issues).

## Contact

* [Tom Kralidis](https://github.com/tomkralidis)
* [Marc Giannoni](https://github.com/mgiannoni)
