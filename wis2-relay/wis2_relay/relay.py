import queue
import logging

import click

from wis2_relay import cli_options
from wis2_relay import util
from wis2_relay.relay_metric import RelayMetric
from wis2_relay.relay_message import RelayMessage
from wis2_relay.relay_sub import RelaySub
from wis2_relay import env

BUF_SIZE = 10000

LOGGER = logging.getLogger(__name__)

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

    pubbroker = env.WIS2_GB_BROKER_URL
    subbroker = env.SUB_BROKER_URL
    subscribe_topics = env.SUB_TOPICS.split()

    options = {
        'verify_certs': config.get('verify_certs', True),
        'certfile': config.get('certfile'),
        'keyfile': config.get('keyfile')
    }

    options['qos'] = int(config.get('qos', 0))
    options['centre_id'] = env.SUB_CENTRE_ID
    options['redis_server'] = env.WIS2_GB_BACKEND_URL
    options['gb_centre_id'] = env.WIS2_GB_CENTRE_ID
    options['validate_message'] = env.VERIFY_MESSAGE
    options['verify_data'] = env.VERIFY_DATA
    options['verify_topic'] = env.VERIFY_TOPIC
    options['verify_metadata'] = env.VERIFY_METADATA
    options['verify_cenre_id'] = env.VERIFY_CENTRE_ID
    options['clean_session'] = config.get('clean_session', True)

    sub_thread = RelaySub(subbroker, subscribe_topics, options,
                          mesgq, metricq, priority=None)
    mesg_thread = RelayMessage(pubbroker, options, mesgq, priority=None)
    metric_thread = RelayMetric(pubbroker, options, metricq, priority=None)

    mesg_thread.start()
    metric_thread.start()
    sub_thread.start()

    mesg_thread.join()
    metric_thread.join()
    sub_thread.join()
