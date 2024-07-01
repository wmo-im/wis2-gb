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

import sys
import json
import logging
from pathlib import Path
import random
import click
#import redis
import time
import re

from redis.cluster import RedisCluster
from typing import Union
from pywis_pubsub import cli_options
from pywis_pubsub import util
from pywis_pubsub.env import SUB_BROKER_URL, SUB_TOPICS, SUB_CENTRE_ID, WIS2_GB_CENTRE_ID, WIS2_GB_BACKEND_URL, WIS2_GB_BROKER_URL
from pywis_pubsub.geometry import is_message_within_bbox
from pywis_pubsub.hook import load_hook
from pywis_pubsub.message import get_link, get_data
from pywis_pubsub.mqtt import MQTTPubSubClient
from pywis_pubsub.storage import STORAGES
from pywis_pubsub.validation import validate_message
from pywis_pubsub.verification import data_verified

LOGGER = logging.getLogger(__name__)

FIRST_RECONNECT_DELAY = 1
RECONNECT_RATE = 2
MAX_RECONNECT_COUNT = 12
MAX_RECONNECT_DELAY = 60

def on_sub_disconnect(client, userdata, rc):
    LOGGER.info(f"Disconnected from {userdata['client_id']} with result code: {rc}")
    process_metric(userdata, "connected_flag", userdata['client_id'], False)

def on_sub_connect(client, userdata, rc):
    LOGGER.info(f"Connected to {userdata['pubclient']}")
    process_metric(userdata, "connected_flag", userdata['client_id'], True)

def on_pub_disconnect(client, userdata, rc):
    LOGGER.info(f"Disconnected from {userdata['client_id']} with result code: {rc}")
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
    exit

def process_metric(userdata, metric_name: str, centre_id: str, value: Union[str, int, float] = None):

    message_payload = {'labels':[centre_id, userdata['gb_centre_id']]}

    if value is not None:
        message_payload['value'] = value

    if userdata.get('pubclient') is not None:
        client = userdata['pubclient']
        try:
            LOGGER.debug(f'Publishing metric {metric_name}')
            client.pub(f'wis2-globalbroker/metrics/{metric_name}', json.dumps(message_payload, default=util.json_serial), 0)
        except Exception as errmsg:
            LOGGER.error(f'Metric publish failed: {errmsg}', exc_info=True)

def on_message_handler(client, userdata, msg):

    LOGGER.debug(f'Topic: {msg.topic}')
    LOGGER.debug(f'Message:\n{msg.payload}')

    msg_dict = json.loads(msg.payload)

#    import pdb; pdb.set_trace()

    fulltopic = re.compile(r"^origin|cache/a/wis2/([A-Za-z0-9_-]+)/data|metadata/.*$")
    brieftopic = re.compile(r"^wis2/([A-Za-z0-9_-]+)/data|metadata/.*$")
    centreonly = re.compile(r"^([A-Za-z_-]+)/data|metadata/.*$")

    if brieftopic.match(msg_dict['properties']['data_id']) is not None:
        centre_id = msg_dict['properties']['data_id'].split('/')[1]
    elif centreonly.match(msg_dict['properties']['data_id']) is not None:
        centre_id = msg_dict['properties']['data_id'].split('/')[0]
    elif fulltopic.match(msg_dict['properties']['data_id'])is not None:
        centre_id = msg_dict['properties']['data_id'].split('/')[3]
    else:
        LOGGER.error(f"Invalid Data-ID: Cannot determine Centre-ID: {msg_dict['properties']['data_id']}")
        return

    process_metric(userdata, "received_total", centre_id)

    redisclient = userdata['redis']
    try: 
        if not redisclient.set(msg_dict['id'], centre_id, ex=3600, nx=True):
            LOGGER.info(f"WIS2 Message exists {centre_id} ID: {msg_dict['id']}")
            return
        else:
            LOGGER.info(f"WIS2 Message added {centre_id} ID: {msg_dict['id']}")
    except Exception as errmsg:
        LOGGER.error(f'Redis operation failed: {errmsg}', exc_info=True)
        return

    if 'content' in msg_dict['properties'] and 'value' in msg_dict['properties']['content']:
        inlinesize = len(msg_dict['properties']['content']['value'])
        if inlinesize > 8192:
            LOGGER.error(f'Message inline content too large. Centre: {centre_id} Size: {inlinesize}', exc_info=True)
            process_metric(userdata, "invalid_total", centre_id)
            msg_dict['properties']['content']['value'] = 'Inline content too long... truncated'

    if 'metadata_id' not in msg_dict['properties']:
        LOGGER.error(f'Message missing metadata.  Centre: {centre_id}', exc_info=True)
        process_metric(userdata, "no_metadata_total", centre_id)

    try:
        if userdata.get('validate_message', False):
            LOGGER.debug('Validating message')
            success, errmsg = validate_message(msg_dict)
            if not success:
                LOGGER.error(f'Message is not valid. Centre: {centre_id} Error: {errmsg}', exc_info=True)
                process_metric(userdata, "invalid_total", centre_id)
    except RuntimeError as errmsg:
        LOGGER.error(f'Cannot validate message: {errmsg}', exc_info=True)

    if userdata.get('bbox') and msg_dict.get('geometry') is not None:
        LOGGER.debug('Performing spatial filtering')
        if not bool(msg_dict['geometry']):
            LOGGER.error(f"Invalid geometry: {msg_dict['geometry']}", exc_info=True)
            return
        if is_message_within_bbox(msg_dict['geometry'], userdata['bbox']):
            LOGGER.debug('Message geometry is within bbox')
        else:
            LOGGER.debug('Message geometry not within bbox; skipping')
            return

    LOGGER.debug(f"Received message with Data_ID: {msg_dict['properties']['data_id']}")

    if userdata.get('storage') is not None:
        LOGGER.debug('Saving data')
        clink = get_link(msg_dict['links'])
        try:
            LOGGER.debug('Downloading data')
            data = get_data(msg_dict, userdata.get('verify_certs'))
        except Exception as errmsg:
            LOGGER.error(f'Error saving data: {errmsg}', exc_info=True)
            return
        if ('integrity' in msg_dict['properties'] and
                userdata.get('verify_data', True)):
            LOGGER.debug('Verifying data')

            method = msg_dict['properties']['integrity']['method']
            value = msg_dict['properties']['integrity']['value']
            if 'content' in msg_dict['properties']:
                size = msg_dict['properties']['content']['size']
            else:
                size = clink['length']

            LOGGER.debug(method)
            if not data_verified(data, size, method, value):
                LOGGER.error('Data verification failed; not saving')
                return
            else:
                LOGGER.debug('Data verification passed')

        filepath = userdata['storage']['options'].get('filepath', 'data_id')
        LOGGER.debug(f'Using {filepath} for naming filepath')

        link = get_link(msg_dict['links'])

        if filepath == 'link':
            LOGGER.debug('Using link as filepath')
            # fetch link and use local path, stripping slashes
            filename = link['href'].split('/', 3)[-1].strip('/')
        elif filepath == 'combined':
            LOGGER.debug('Using combined data_id+link extension as filepath')
            filename = msg_dict['properties']['data_id']
            suffix = Path(link).suffix
            if suffix != '':
                LOGGER.debug(f'File extension found: {suffix}')
                filename = f'{filename}{suffix}'
            else:
                LOGGER.debug('File extension not found. Trying media type')
                media_type = link.get('type')
                if media_type is not None:
                    suffix = util.guess_extension(media_type)
                    if suffix is not None:
                        filename = f'{filename}{suffix}'
                    else:
                        LOGGER.debug('No extension found. Giving up / using data_id')  # noqa
                else:
                    LOGGER.debug('No media type found. Giving up / using data_id')  # noqa
        else:
            LOGGER.debug('Using data_id as filepath')
            filename = msg_dict['properties'].get('data_id')
            if filename is None:
                LOGGER.error('no data_id found')
                return

        LOGGER.debug(f'filename: {filename}')

        content_type = link.get('type', 'applcation/octet-stream')

        storage_class = STORAGES[userdata.get('storage').get('type')]
        storage_object = storage_class(userdata['storage'])

        if not msg_dict['properties'].get('cache', True):
            LOGGER.debug(f'No caching requested; not saving {filename}')
            return

        if link.get('rel') == 'deletion':
            LOGGER.debug('Delete specified')
            storage_object.delete(filename)
        elif link.get('rel') == 'update':
            LOGGER.debug('Update specified')
            storage_object.save(data, filename, content_type)
        else:
            if storage_object.exists(filename):
                LOGGER.debug('Duplicate detected; not saving')
                return

            LOGGER.debug('Saving')
            storage_object.save(data, filename, content_type)

    if userdata.get('hook') is not None:
        LOGGER.debug(f"Hook detected: {userdata['hook']}")
        try:
            hook = load_hook(userdata['hook'])
            LOGGER.debug('Executing hook')
            hook.execute(msg.topic, msg_dict)
        except Exception as errmsg:
            LOGGER.error(f'Hook failed: {errmsg}', exc_info=True)

    if userdata.get('pubclient') is not None:
        client = userdata['pubclient']
        LOGGER.debug(f"Relay detected: {userdata}")
        try:
            LOGGER.debug(f'Publishing message')
            client.pub(msg.topic, json.dumps(msg_dict, default=util.json_serial), 0)
            process_metric(userdata, "published_total", centre_id)
            process_metric(userdata, "last_message_timestamp", centre_id, round(time.time()))
        except Exception as errmsg:
            LOGGER.error(f'Relay falied {errmsg}', exc_info=True)
    else:
        LOGGER.error(f'Relay falied: no pub_client connection', exc_info=True)

@click.command()
@click.pass_context
@cli_options.OPTION_CONFIG
@cli_options.OPTION_VERBOSITY
@click.option('--bbox', '-b', help='Bounding box filter')
@click.option('--download', '-d', is_flag=True, help='Download data')
def relay(ctx, config, download, bbox=[], verbosity='NOTSET'):
    """Subscribe to a broker/topic, relay to another broker/topic, and optionally download data"""

    if config is None:
        raise click.ClickException('missing --config')
    config = util.yaml_load(config)

    subbroker = SUB_BROKER_URL
    pubbroker = WIS2_GB_BROKER_URL
    redis_server = WIS2_GB_BACKEND_URL
    subscribe_topics = SUB_TOPICS.split()
    verify_certs = config.get('verify_certs', True)
    certfile = config.get('certfile')
    keyfile = config.get('keyfile')
    qos = int(config.get('qos', 1))

    options = {
        'verify_certs': verify_certs,
        'certfile': certfile,
        'keyfile': keyfile
    }

    options['client_id'] = SUB_CENTRE_ID
    options['gb_centre_id'] = WIS2_GB_CENTRE_ID
    options['clean_session'] = config.get('clean_session', True)

    if bbox:
        options['bbox'] = [float(i) for i in bbox.split(',')]

    if download:
        options['storage'] = config['storage']

    options['verify_data'] = config.get('verify_data', True)
    options['validate_message'] = config.get('validate_message', True)
    options['hook'] = config.get('hook')

    try:
        redisclient = RedisCluster(host=redis_server, port=6379)
    except Exception as errmsg:
        LOGGER.error(f'Redis connect failed: {errmsg} Redis Server Config: {redis_server}', exc_info=True)
        exit

    pubclient = MQTTPubSubClient(pubbroker, options)
    pubclient.userdata['pubclient'] = pubclient
    pubclient.bind('on_disconnect', on_pub_disconnect)
    click.echo(f'Connected to Publish broker {pubclient.broker_safe_url}')

    process_metric(pubclient.userdata, "connected_flag", SUB_CENTRE_ID, False)

    subclient = MQTTPubSubClient(subbroker, options)
    subclient.userdata['redis'] = redisclient
    subclient.userdata['pubclient'] = pubclient
    subclient.bind('on_message', on_message_handler)
    subclient.bind('on_disconnect', on_sub_disconnect)
    subclient.bind('on_connect', on_sub_connect)

    click.echo(f'Connected to Subscribtion broker {subclient.broker_safe_url}')
    click.echo(f'Subscribing to subscribe_topics {subscribe_topics}')
    process_metric(pubclient.userdata, "connected_flag", SUB_CENTRE_ID, True)
    subclient.sub(subscribe_topics, qos)
