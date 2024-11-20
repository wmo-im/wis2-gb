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
import random
import string
import os
import sys
import ssl
from urllib.parse import urlparse
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
import time
from datetime import datetime, timezone, timedelta

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
HTTP_PORT = 8006

logging.basicConfig(stream=sys.stdout)
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(LOGGING_LEVEL)

# sets metrics as per https://github.com/wmo-im/wis2-metric-hierarchy/blob/main/metric-hierarchy/gdc.csv  # noqa

METRIC_NO_METADATA = Counter(
    'wmo_wis2_gb_messages_no_metadata_total',
    'Number of WIS2 messages missing recommended metadata',
    ['centre_id', 'report_by']
)

METRIC_INVALID = Counter(
    'wmo_wis2_gb_messages_invalid_topic_total',
    'Number of WIS2 messages published to invalid topic',
    ['centre_id', 'report_by']
)

METRIC_INVALID = Counter(
    'wmo_wis2_gb_messages_invalid_format_total',
    'Number of WIS2 messages failed validation',
    ['centre_id', 'report_by']
)

METRIC_PUBLISHED = Counter(
    'wmo_wis2_gb_messages_published_total',
    'Number of WIS2 messages published',
    ['centre_id', 'report_by']
)

METRIC_RECEIVED = Counter(
    'wmo_wis2_gb_messages_received_total',
    'Number of WIS2 messages recieved',
    ['centre_id', 'report_by']
)

METRIC_CONNECTED_FLAG = Gauge(
    'wmo_wis2_gb_connected_flag',
    'WIS2 Node connection status',
    ['centre_id', 'report_by']
)

METRIC_TIMESTAMP_SECONDS = Gauge(
    'wmo_wis2_gb_last_message_timestamp_seconds',
    'Timestamp in seconds for last message recieved',  # noqa
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

def collect_metrics() -> None:
    """
    Subscribe to MQTT wis2-globalbroker/metrics and collect metrics

    :returns: `None`
    """

    def _sub_connect(client, userdata, flags, rc, properties=None):
        LOGGER.info('Subscribing to topic wis2-globalbroker/metrics/#')
        client.subscribe('wis2-globalbroker/metrics/#', qos=0)

    def _sub_subscribe(client, userdata, flags, rc, properties=None):
        LOGGER.info('Subscribed to topic wis2-globalbroker/metrics/#')

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
        elif topic == 'wis2-globalbroker/metrics/invalid_topic_total':
            METRIC_INVALID.labels(*labels).inc()
        elif topic == 'wis2-globalbroker/metrics/invalid_format_total':
            METRIC_INVALID.labels(*labels).inc()
        elif topic == 'wis2-globalbroker/metrics/messages_received_total':
            METRIC_RECEIVED.labels(*labels).inc()
        elif topic == 'wis2-globalbroker/metrics/no_metadata_total':
            METRIC_NO_METADATA.labels(*labels).inc()
        elif topic == 'wis2-globalbroker/metrics/last_message_timestamp':
            METRIC_TIMESTAMP_SECONDS.labels(*labels).set(value)
        elif topic == 'wis2-globalbroker/metrics/connected_flag':
            METRIC_CONNECTED_FLAG.labels(*labels).set(value)

    
    def setup_mqtt_client(connection_info: str, verify_cert: bool):
        randstring = ''.join(random.choice(string.hexdigits) for i in range(6))
        rand_id = "metrics-collector" + randstring
        LOGGER.info(f'Setting up MQTT client: {rand_id}')
        connection_info = urlparse(connection_info)
        if connection_info.scheme in ['ws', 'wss']:
            client = mqtt.Client(client_id=rand_id, transport='websockets', protocol=mqtt.MQTTv5, userdata={'received_messages': []})
        else:
            client = mqtt.Client(client_id=rand_id, transport='tcp', protocol=mqtt.MQTTv5, userdata={'received_messages': []})
        client.on_connect = _sub_connect
        client.on_subscribe = _sub_subscribe
        client.on_message = _sub_message
        client.username_pw_set(connection_info.username, connection_info.password)
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = 300  # seconds
        if connection_info.port in [443, 8883]:
            tls_settings = { 'tls_version': 2 }
            if not verify_cert:
                tls_settings['cert_reqs'] = ssl.CERT_NONE
            client.tls_set(**tls_settings)
        try:
            LOGGER.info(f'Connecting to {connection_info.hostname}')
            client.connect(host=connection_info.hostname, port=connection_info.port, properties=properties)
        except Exception as e:
            LOGGER.error(f"Connection error: {e}")
            LOGGER.error(f"Parsed connection string components:")
            LOGGER.error(f"  Scheme: {connection_info.scheme}")
            LOGGER.error(f"  Hostname: {connection_info.hostname}")
            LOGGER.error(f"  Port: {connection_info.port}")
            LOGGER.error(f"  Username: {connection_info.username}")
            LOGGER.error(f"  Password: {connection_info.password}")
            raise
        return client
    

    try:
        client = setup_mqtt_client(BROKER_URL, False)
        client.loop_forever()
    except Exception as err:
        LOGGER.error(err)


if __name__ == '__main__':
    LOGGER.info(f'Starting metrics collector server on port {HTTP_PORT}')
    start_http_server(HTTP_PORT)
    init_metrics()
    collect_metrics()
