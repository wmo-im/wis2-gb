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

import json
import logging
from typing import Tuple
#from jsonschema import validate
from jsonschema.validators import Draft202012Validator
from wis2_relay.schema import MESSAGE_SCHEMA

LOGGER = logging.getLogger(__name__)

class WNMValidate:

    def __init__(self) -> None:
        if not MESSAGE_SCHEMA.exists():
            msg = 'Schema not found. Please run wis2-relay schema sync'
            LOGGER.error(msg)
            raise RuntimeError(msg)
    
        with open(MESSAGE_SCHEMA) as fh:
            self.schema = json.load(fh)
            self.validator = Draft202012Validator(self.schema, format_checker=Draft202012Validator.FORMAT_CHECKER)

    def validate_message(self, message: dict) -> Tuple[bool, str]:
        success = False
        error_message = None

        try:
            self.validator.validate(message)
            success = True
        except Exception as err:
            error_message = repr(err)

        return (success, error_message)
    
#        is_valid, errors = self.validator(message, Draft202012Validator.FORMAT_CHECKER)
#        is_valid, errors = self.validator.validate(message)
#        return ((is_valid, errors))
