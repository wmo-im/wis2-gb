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

import os
from typing import Any


def str2bool(value: Any) -> bool:
    """
    helper function to return Python boolean
    type (source: https://stackoverflow.com/a/715468)

    :param value: value to be evaluated

    :returns: `bool` of whether the value is boolean-ish
    """

    value2 = False

    if isinstance(value, bool):
        value2 = value
    else:
        value2 = value.lower() in ('yes', 'true', 't', '1', 'on')

    return value2


SUB_BROKER_URL = os.environ.get('SUB_BROKER_URL', 'None')
SUB_TOPICS = os.environ.get('SUB_TOPICS', 'None')
SUB_CENTRE_ID = os.environ.get('SUB_CENTRE_ID', 'None')
WIS2_GB_CENTRE_ID = os.environ.get('WIS2_GB_CENTRE_ID', 'None')
WIS2_GB_BACKEND_URL = os.environ.get('WIS2_GB_BACKEND_URL', 'None')
WIS2_GB_BROKER_URL = os.environ.get('WIS2_GB_BROKER_URL', 'None')
VERIFY_MESSAGE = str2bool(os.environ.get('VERIFY_MESSAGE', False))
VERIFY_DATA = str2bool(os.environ.get('VERIFY_DATA', False))
VERIFY_TOPIC = str2bool(os.environ.get('VERIFY_TOPIC', False))
VERIFY_METADATA = str2bool(os.environ.get('VERIFY_METADATA', False))
VERIFY_CENTRE_ID = str2bool(os.environ.get('VERIFY_CENTRE_ID', False))

GB_LINKS = []

if None in [SUB_BROKER_URL, SUB_TOPICS, SUB_CENTRE_ID,
            WIS2_GB_CENTRE_ID, WIS2_GB_BACKEND_URL, WIS2_GB_BROKER_URL,
            VERIFY_MESSAGE, VERIFY_DATA, VERIFY_TOPIC, VERIFY_METADATA,
            VERIFY_CENTRE_ID]:

    raise EnvironmentError('Environment variables not set!')
