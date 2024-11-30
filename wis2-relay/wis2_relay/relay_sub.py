import threading
import json
import logging
import redis
import time

from typing import Union
from wis2_relay.topic import WIS2TopicHierarchy
from wis2_relay.mqtt import MQTTPubSubClient
from wis2_relay.verify import WNMValidate

LOGGER = logging.getLogger(__name__)


class RelaySub(threading.Thread):
    def process_metric(self, metric_name: str,
                       value: Union[str, int, float] = None):
        userdata = self.client.userdata
        LOGGER.debug(f'Publishing metric {metric_name}')
        message_payload = {
            'labels': [userdata['centre_id'], userdata['gb_centre_id']]
        }
        if value is not None:
            message_payload['value'] = value

        self.metricq.put((f'wis2-globalbroker/metrics/{metric_name}',
                          message_payload))

    def process_mesg(self, topic, mesg_dict):
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
            LOGGER.error('Review Global Broker Client Subscriptions')
            self.process_metric("invalid_topic_total")
            return

        centre_id = topic_check[3]

        try:
            if not self.redis.set(msg_dict['id'], centre_id, ex=3600, nx=True):
                LOGGER.info(f"WIS2 Message exists {centre_id} ID: {msg_dict['id']}")  # noqa
                return
            else:
                LOGGER.info(f"WIS2 Message received {centre_id} ID: {msg_dict['id']}")  # noqa
                self.process_metric("messages_received_total")
        except Exception as err:
            LOGGER.error(f'Redis operation failed: {err}', exc_info=True)
            return

        try:
            tpc_vfy = self.wnm_topic
            if not tpc_vfy.get_wis2(topic_check[:6]):
                LOGGER.error(f'Invalid WIS2 Topic Preamble {msg.topic}')
                LOGGER.error('Review Global Broker Client Subscriptions')
                self.process_metric("invalid_topic_total")
                return
            if userdata.get('verify_centre_id', False) and not tpc_vfy.get_centre_id(topic_check[3]):  # noqa
                LOGGER.error(f'Invalid Centre-ID in Topic: {msg.topic}')
                self.process_metric("invalid_topic_total")
                return
            if userdata.get('verify_topic', False):
                if topic_check[4] == 'metadata' and len(topic_check) in [6, 7]:
                    LOGGER.error(f'Invalid WIS2 Topic Preamble {msg.topic}')
                    self.process_metric("invalid_topic_total")
                    return
                if topic_check[4] == "data" and len(topic_check) < 8:
                    LOGGER.error(f'Invalid WIS2 Topic Preamble {msg.topic}')
                    self.process_metric("invalid_topic_total")
                    return
                if len(topic_check) > 7 and not tpc_vfy.get_esd(topic_check[6:]):  # noqa
                    LOGGER.error(f'Invalid Earth System Discipline Topic {msg.topic}')  # noqa
                    self.process_metric("invalid_topic_total")
                    return
        except RuntimeError as err:
            LOGGER.error('Problem With Topic Validation')
            LOGGER.error(f'Topic: {msg.topic} Error: {err}')

        if userdata.get('verify_data', False):
            try:
                inlinesize = len(msg_dict['properties']['content']['value'])
                if inlinesize > 4096:
                    LOGGER.error(f'Message inline content too large. Centre: {centre_id} Size: {inlinesize}')  # noqa
                    self.process_metric("invalid_total")
                    msg_dict['properties']['content']['value'] = 'Inline content too long... truncated'  # noqa

                    return
            except KeyError:
                LOGGER.debug('no inline data found')

        if 'metadata_id' not in msg_dict['properties']:
            LOGGER.error(f'Message missing metadata.  Centre: {centre_id}')
            self.process_metric("no_metadata_total")
            if userdata.get('verify_metadata', False):
                return

        try:
            if userdata.get('validate_message', False):
                LOGGER.debug('Validating message')
                success, err = self.wnm_schema.validate_message(msg_dict)
                if not success:
                    LOGGER.error(f'Message is not valid. Centre: {centre_id} Error: {err}')  # noqa
                    self.process_metric("invalid_format_total")
                    return
        except RuntimeError as err:
            LOGGER.error(f'Cannot validate message: {err}', exc_info=True)
            return

        LOGGER.debug(f"Received message with Data_ID: {msg_dict['properties']['data_id']}")  # noqa
        self.process_mesg(msg.topic, msg_dict)

    def __init__(self, broker, topics, options, mesgq, metricq, priority=None):
        LOGGER.info(f"Setup Message Sub {broker} with options: {options}")
        threading.Thread.__init__(self)
        self.wnm_topic = WIS2TopicHierarchy()
        self.wnm_schema = WNMValidate()
        self.topics = topics
        self.mesgq = mesgq
        self.metricq = metricq
        self.qos = options['qos']
        self.priority = priority

        try:
            self.redis = redis.Redis(host=options['redis_server'], port=6379,
                                     ssl=True, ssl_cert_reqs="none")
        except Exception as err:
            LOGGER.error(f"Redis connect failed: {err} Redis Server Config: {options['redis_server']}", exc_info=True)  # noqa
            exit

        self.client = MQTTPubSubClient(broker, options)
        self.client.bind('on_message', self.on_message_handler)
        LOGGER.info(f'Connected to broker {self.client.broker_safe_url}')

    def run(self):
        LOGGER.info(f'Subscribing to subscribe_topics {self.topics}')
        self.process_metric("connected_flag", True)
        self.client.sub(self.topics, self.qos)
