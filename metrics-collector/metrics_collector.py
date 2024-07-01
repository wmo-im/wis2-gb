###############################################################################
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
###############################################################################

import csv
import json
import logging
import os
import sys
from urllib.parse import urlparse
import paho.mqtt.client as mqtt_client

from prometheus_client import (
    disable_created_metrics,
    Counter, Gauge, Info, 
    start_http_server, REGISTRY, GC_COLLECTOR,
    PLATFORM_COLLECTOR, PROCESS_COLLECTOR
)

REGISTRY.unregister(GC_COLLECTOR)
REGISTRY.unregister(PLATFORM_COLLECTOR)
REGISTRY.unregister(PROCESS_COLLECTOR)

BROKER_URL = os.environ['WIS2_GB_BROKER_URL']
CENTRE_ID = os.environ['WIS2_GB_CENTRE_ID']
CENTRE_ID_CSV = os.environ['WIS2_GB_CENTRE_ID_CSV']
LOGGING_LEVEL = os.environ['WIS2_GB_LOGGING_LEVEL']
##GB = os.environ['WIS2_GB_GB']
#GB_TOPIC = os.environ['WIS2_GB_GB_TOPIC']
HTTP_PORT = 8006

logging.basicConfig(stream=sys.stdout)
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOGGING_LEVEL)

# sets metrics as per https://github.com/wmo-im/wis2-metric-hierarchy/blob/main/metric-hierarchy/gdc.csv  # noqa

#METRIC_INFO = Info(
#    'wis2_gb_metrics',
#    'WIS2 National Weather Service Global Broker metrics'
#)

METRIC_PUBLISHED = Counter(
    'wmo_wis2_gb_messages_published_total',
    'Number of WIS2 messages published',
    ['centre_id', 'report_by']
)

METRIC_INVALID = Counter(
    'wmo_wis2_gb_messages_invalid_total',
    'Number of WIS2 messages failed validation',
    ['centre_id', 'report_by']
)

METRIC_RECEIVED = Counter(
    'wmo_wis2_gb_messages_received_total',
    'Number of WIS2 messages recieved',
    ['centre_id', 'report_by']
)

METRIC_NO_METADATA = Counter(
    'wmo_wis2_gb_messages_no_metadata_total',
    'Number of WIS2 messages missing recommended metadata',
    ['centre_id', 'report_by']
)

METRIC_TIMESTAMP_SECONDS = Gauge(
    'wmo_wis2_gb_last_message_timestamp_seconds',
    'Timestamp in seconds for last message recieved',  # noqa
    ['centre_id', 'report_by']
)

METRIC_CONNECTED_FLAG = Gauge(
    'wmo_wis2_gb_connected_flag',
    'WIS2 Node connection status',
    ['centre_id', 'report_by']
)

def get_gb_centre_id() -> str:
    """
    Derive GB centre id from WIS2_GB_GB_LINK environment variables

    :returns: centre-id of matching GB
    """
    return CENTRE_ID

    for key, value in os.environ.items():
        if key.startswith('WIS2_GB_GB_LINK'):
            centre_id, url, title = value.split(',', 2)
            if GB == url:
                return centre_id

def init_metrics() -> None:
    """
    Initializes metrics on startup

    :returns: `None`
    """

    disable_created_metrics()

#    gb_centre_id = get_gb_centre_id()
#
#    METRIC_INFO.info({
#        'centre_id': CENTRE_ID,
#        'url': 'http://localhost',
#        'subscribed_to': f'{gb_centre_id}'
#    })
#
#    METRIC_CONNECTED_FLAG.labels(centre_id=gb_centre_id, report_by=CENTRE_ID).inc(1)
#
#    with open(CENTRE_ID_CSV) as fh:
#        reader = csv.DictReader(fh)
#        for row in reader:
#            labels = [row['Name'], CENTRE_ID]
#
#            METRIC_PUBLISHED.labels(*labels).inc(0)
#            METRIC_INVALID.labels(*labels).inc(0)
#            METRIC_RECEIVED.labels(*labels).inc(0)
#            METRIC_NO_METADATA.labels(*labels).inc(0)

def collect_metrics() -> None:
    """
    Subscribe to MQTT wis2-globalbroker/metrics and collect metrics

    :returns: `None`
    """

    def _sub_connect(client, userdata, flags, rc):
        LOGGER.info('Subscribing to topic wis2-globalbroker/metrics/#')
        client.subscribe('wis2-globalbroker/metrics/#', qos=0)

    def _sub_message(client, userdata, msg):
        LOGGER.debug('Processing message')
        topic = msg.topic
        payload = json.loads(msg.payload)
        labels = payload['labels']
        value = payload.get('value')
        LOGGER.debug(f'Topic: {topic}')
        LOGGER.debug(f"Labels: {payload['labels']}")
        LOGGER.debug(f"Value: {payload.get('labels')}")
        if topic == 'wis2-globalbroker/metrics/published_total':
            METRIC_PUBLISHED.labels(*labels).inc()
        elif topic == 'wis2-globalbroker/metrics/invalid_total':
            METRIC_INVALID.labels(*labels).inc()
        elif topic == 'wis2-globalbroker/metrics/received_total':
            METRIC_RECEIVED.labels(*labels).inc()
        elif topic == 'wis2-globalbroker/metrics/no_metadata_total':
            METRIC_NO_METADATA.labels(*labels).inc()
        elif topic == 'wis2-globalbroker/metrics/last_message_timestamp':
            METRIC_TIMESTAMP_SECONDS.labels(*labels).set(value)
        elif topic == 'wis2-globalbroker/metrics/connected_flag':
            METRIC_CONNECTED_FLAG.labels(*labels).set(value)

    url = urlparse(BROKER_URL)

    client_id = 'metrics_collector'

    try:
        LOGGER.info('Setting up MQTT client')
        client = mqtt_client.Client(client_id)
        client.on_connect = _sub_connect
        client.on_message = _sub_message
        client.username_pw_set(url.username, url.password)
        LOGGER.info(f'Connecting to {url.hostname}')
        client.connect(url.hostname, url.port)
        client.loop_forever()
    except Exception as err:
        LOGGER.error(err)


if __name__ == '__main__':
    LOGGER.info(f'Starting metrics collector server on port {HTTP_PORT}')
    start_http_server(HTTP_PORT)
    init_metrics()
    collect_metrics()
