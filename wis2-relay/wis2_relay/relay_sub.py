import sys
import threading
import json
import logging
from pathlib import Path
import random
import click
import redis
import time
import re

from typing import Union
from redis.cluster import RedisCluster
from wis2_relay import cli_options
from wis2_relay import util
from wis2_relay.topic import WIS2_Topic_Hierarchy
from wis2_relay.env import SUB_BROKER_URL, SUB_TOPICS, SUB_CENTRE_ID
from wis2_relay.env import WIS2_GB_CENTRE_ID, WIS2_GB_BROKER_URL, WIS2_GB_BACKEND_URL
from wis2_relay.env import VERIFY_MESG, VERIFY_DATA, VERIFY_TOPIC, VERIFY_METADATA, VERIFY_CENTRE_ID
from wis2_relay.mqtt import MQTTPubSubClient
from wis2_relay.verfy import WNMValidate

LOGGER = logging.getLogger(__name__)

class RelaySub(threading.Thread):
    
    def process_metric(self, metric_name: str, value: Union[str, int, float] = None):
        userdata = self.client.userdata
        LOGGER.debug(f'Publishing metric {metric_name}')
        message_payload = {'labels':[userdata['centre_id'], userdata['gb_centre_id']]}
        if value is not None:
            message_payload['value'] = value
        self.metricq.put((f'wis2-globalbroker/metrics/{metric_name}', message_payload))
    
    def process_mesg(self, topic, mesg_dict):
        userdata = self.client.userdata
        LOGGER.debug(f"Publishing message: {topic}")
        self.process_metric("published_total")
        self.process_metric("last_message_timestamp", round(time.time()))
        self.mesgq.put((topic, mesg_dict))
    
    def on_message_handler(self, client, userdata, msg):
    
        LOGGER.debug(f'Topic: {msg.topic}')
        LOGGER.debug(f'Message:\n{msg.payload}')
    
        msg_dict = json.loads(msg.payload)
    
        topic_check = msg.topic.split('/')
        if len(topic_check) < 5:
            LOGGER.error(f'Invalid WIS2 Topic Preamble {msg.topic}')
            LOGGER.error(f'Review Global Broker Client Subscriptions')
            self.process_metric("invalid_topic_total")
            return

        centre_id = topic_check[3]
    
        try:
            tpc_vfy = self.wnm_topic
            if not tpc_vfy.get_wis2(topic_check[:6]):
                LOGGER.error(f'Invalid WIS2 Topic Preamble {msg.topic}')
                LOGGER.error(f'Review Global Broker Client Subscriptions')
                self.process_metric("invalid_topic_total")
                return
            if userdata.get('verify_centre_id', False) and not tpc_vfy.get_centre_id(topic_check[3]):
                LOGGER.error(f'Invalid Centre-ID in Topic: {msg.topic}')
                self.process_metric("invalid_topic_total")
                return
            if userdata.get('verify_topic', False):
                if topic_check[4] == "metadata" and (len(topic_check) == 6 or len(topic_check) ==7):
                    LOGGER.error(f'Invalid WIS2 Topic Preamble {msg.topic}')
                    self.process_metric("invalid_topic_total")
                    return
                if topic_check[4] == "data" and len(topic_check) < 8:
                    LOGGER.error(f'Invalid WIS2 Topic Preamble {msg.topic}')
                    self.process_metric("invalid_topic_total")
                    return
                if len(topic_check) > 7 and not tpc_vfy.get_esd(topic_check[6:]):
                    LOGGER.error(f'Invalid Earth System Discipline Topic {msg.topic}')
                    self.process_metric("invalid_topic_total")
                    return
        except RuntimeError as errmsg:
            LOGGER.error(f'Problem With Topic Validation. Topic: {msg.topic} Error: {errmsg}')
    
        if userdata.get('verify_data', False) and "content" in msg_dict['properties'] and "value" in msg_dict['properties']['content']:
            inlinesize = len(msg_dict['properties']['content']['value'])
            if inlinesize > 4096:
                LOGGER.error(f'Message inline content too large. Centre: {centre_id} Size: {inlinesize}')
                self.process_metric("invalid_total")
                msg_dict['properties']['content']['value'] = 'Inline content too long... truncated'
                return
    
        if 'metadata_id' not in msg_dict['properties']:
            LOGGER.error(f'Message missing metadata.  Centre: {centre_id}')
            self.process_metric("no_metadata_total")
            if userdata.get('verify_metadata', False):
                return
    
        try:
            if userdata.get('validate_message', False):
                LOGGER.debug('Validating message')
                success, errmsg = self.wnm_schema.validate_message(msg_dict)
                if not success:
                    LOGGER.error(f'Message is not valid. Centre: {centre_id} Error: {errmsg}')
                    self.process_metric("invalid_format_total")
                    return
        except RuntimeError as errmsg:
            LOGGER.error(f'Cannot validate message: {errmsg}', exc_info=True)
            return
    
        redisclient = self.redis
        try: 
            if not redisclient.set(msg_dict['id'], centre_id, ex=3600, nx=True):
                LOGGER.info(f"WIS2 Message exists {centre_id} ID: {msg_dict['id']}")
                return
            else:
                LOGGER.info(f"WIS2 Message added {centre_id} ID: {msg_dict['id']}")
        except Exception as errmsg:
            LOGGER.error(f'Redis operation failed: {errmsg}', exc_info=True)
            return
    
        LOGGER.debug(f"Received message with Data_ID: {msg_dict['properties']['data_id']}")
        self.process_mesg(msg.topic, msg_dict)

    def __init__(self, broker, topics, options, mesgq, metricq, priority=None):
        LOGGER.info(f"Setup Message Sub {broker} with options: {options}")
        threading.Thread.__init__(self)
        self.wnm_topic = WIS2_Topic_Hierarchy()
        self.wnm_schema = WNMValidate()
        self.topics = topics
        self.mesgq = mesgq
        self.metricq = metricq
        self.qos = options['qos']
        self.priority = priority
    
        try:
            redisclient = RedisCluster(host=options['redis_server'], port=6379, ssl=False, ssl_cert_reqs="none")
        except Exception as errmsg:
            LOGGER.error(f"Redis connect failed: {errmsg} Redis Server Config: {options['redis_server']}", exc_info=True)
            exit

        self.redis = redisclient
        self.client = MQTTPubSubClient(broker, options)
        self.client.bind('on_message', self.on_message_handler)
        LOGGER.info(f'Connected to Subscribtion broker {self.client.broker_safe_url}')

    def run(self):
        LOGGER.info(f'Subscribing to subscribe_topics {self.topics}')
        self.process_metric("connected_flag", True)
        self.client.sub(self.topics, self.qos)

