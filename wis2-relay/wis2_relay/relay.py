import queue
import sys
import json
import logging
from pathlib import Path
import random
import click
import time
import re

from typing import Union
from wis2_relay import cli_options
from wis2_relay import util
from wis2_relay.relay_metric import RelayMetric
from wis2_relay.relay_mesg import RelayMesg
from wis2_relay.relay_sub import RelaySub
from wis2_relay.env import SUB_BROKER_URL, SUB_TOPICS, SUB_CENTRE_ID
from wis2_relay.env import WIS2_GB_CENTRE_ID, WIS2_GB_BROKER_URL, WIS2_GB_BACKEND_URL
from wis2_relay.env import VERIFY_MESG, VERIFY_DATA, VERIFY_TOPIC, VERIFY_METADATA, VERIFY_CENTRE_ID

BUF_SIZE = 10000
mesgq = queue.Queue(BUF_SIZE)
metricq = queue.Queue(BUF_SIZE)

@click.command()
@click.pass_context
@cli_options.OPTION_CONFIG
@cli_options.OPTION_VERBOSITY

def relay(ctx, config, verbosity='NOTSET'):
    """Subscribe to a broker/topic, relay to another broker/topic"""

    if config is None:
        raise click.ClickException('missing --config')
    config = util.yaml_load(config)

    pubbroker = WIS2_GB_BROKER_URL
    subbroker = SUB_BROKER_URL
    subscribe_topics = SUB_TOPICS.split()
    env_verify_mesg = VERIFY_MESG
    env_verify_data = VERIFY_DATA
    env_verify_topic = VERIFY_TOPIC
    env_verify_metadata = VERIFY_METADATA
    env_verify_centre_id = VERIFY_CENTRE_ID

    options = {
        'verify_certs': config.get('verify_certs', True),
        'certfile': config.get('certfile'),
        'keyfile': config.get('keyfile')
    }

    options['qos'] = int(config.get('qos', 0))
    options['centre_id'] = SUB_CENTRE_ID
    options['redis_server'] = WIS2_GB_BACKEND_URL
    options['gb_centre_id'] = WIS2_GB_CENTRE_ID
    options['validate_message'] = VERIFY_MESG.lower() in ("true", "yes")
    options['verify_data'] = VERIFY_DATA.lower() in ("true", "yes")
    options['verify_topic'] = VERIFY_TOPIC.lower() in ("true", "yes")
    options['verify_metadata'] = VERIFY_METADATA.lower() in ("true", "yes")
    options['verify_cenre_id'] = VERIFY_CENTRE_ID.lower() in ("true", "yes")
    options['clean_session'] = config.get('clean_session', True)

    sub_thread = RelaySub(subbroker, subscribe_topics, options, mesgq, metricq, priority=None)
    mesg_thread = RelayMesg(pubbroker, options, mesgq, priority=None)
    metric_thread = RelayMetric(pubbroker, options, metricq, priority=None)

    mesg_thread.start()
    metric_thread.start()
    sub_thread.start()

    mesg_thread.join()
    metric_thread.join()
    sub_thread.join()
