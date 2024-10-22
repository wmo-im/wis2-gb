import threading
import queue
import json
import time
import logging
import random
import sys
import os

from typing import Union
from wis2_relay import cli_options
from wis2_relay import util
from wis2_relay.topic import WIS2_Topic_Hierarchy
from wis2_relay.env import SUB_BROKER_URL, SUB_TOPICS, SUB_CENTRE_ID
from wis2_relay.env import WIS2_GB_CENTRE_ID, WIS2_GB_BROKER_URL, WIS2_GB_BACKEND_URL
from wis2_relay.env import VERIFY_MESG, VERIFY_DATA, VERIFY_TOPIC, VERIFY_METADATA, VERIFY_CENTRE_ID
from wis2_relay.mqtt import MQTTPubSubClient

LOGGER = logging.getLogger(__name__)

FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60

class RelayMetric(threading.Thread):
    
    FIRST_RECONNECT_DELAY = 1
    RECONNECT_RATE = 2
    MAX_RECONNECT_COUNT = 12
    MAX_RECONNECT_DELAY = 60
    
    def on_pub_disconnect(self, client, userdata, disc_flags, rc, props):
        LOGGER.info(f"Disconnected from {userdata['centre_id']} with result code: {rc}")
        reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
        while reconnect_count < MAX_RECONNECT_COUNT:
            LOGGER.info(f'Reconnecting in {reconnect_delay} seconds')
            time.sleep(reconnect_delay)
            try:
                client.reconnect()
                LOGGER.info('Reconnected successfully!')
                return
            except Exception as errmsg:
                LOGGER.error(f'Reconnect failed. Retrying...', {errmsg})
            reconnect_delay *= RECONNECT_RATE
            reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
            reconnect_count += 1
        LOGGER.info(f'Reconnect failed after {reconnect_count} attempts.')

    def __init__(self, broker, options, metricq, priority=None):
        LOGGER.info(f"Setup Metrics Pub {broker} with options: {options}")
        threading.Thread.__init__(self)
        self.qos = options['qos']
        self.queue = metricq
        self.priority = priority
        self.client = MQTTPubSubClient(broker, options)
        self.client.bind('on_disconnect', self.on_pub_disconnect)

    def run(self):
        while True:
            topic, mesg = self.queue.get()
            self.client.pub(topic, json.dumps(mesg, default=util.json_serial), self.qos)
            self.queue.task_done()
