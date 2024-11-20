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

import click
import csv
import logging
from pathlib import Path
import shutil
import zipfile
from urllib.request import urlopen

from wis2_relay import cli_options

LOGGER = logging.getLogger(__name__)

TOPIC_SCHEMA_URL = 'https://wmo-im.github.io/wis2-topic-hierarchy/wth-bundle.zip'
TOPIC_SCHEMA_DIR = Path.home() / '.wis2-topic-hierarchy' # noqa
TOPIC_SCHEMA_FILE = TOPIC_SCHEMA_DIR / 'wis2-topic-hierarchy-bundled.zip'  # noqa
TOPIC_SCHEMA_ESD = TOPIC_SCHEMA_DIR/ 'earth-system-discipline.csv'  # noqa
TOPIC_SCHEMA_CENTRE = TOPIC_SCHEMA_DIR/ 'centre-id.csv'  # noqa

TOPIC_SCHEMA_WIS2 = [
    "origin/a/wis2/xxx/data/core",
    "origin/a/wis2/xxx/data/recommended",
    "origin/a/wis2/xxx/metadata",
    "origin/a/wis2/xxx/metadata/core",
    "origin/a/wis2/xxx/metadata/recommended",
    "cache/a/wis2/xxx/data/core",
    "cache/a/wis2/xxx/data/recommended",
    "cache/a/wis2/xxx/metadata",
    "cache/a/wis2/xxx/metadata/core",
    "cache/a/wis2/xxx/metadata/recommended"
    ]

class WIS2_Topic_Hierarchy():
    def __init__(self):
        self.centre_id = {}
        self.wis2_topic = {}
        self.earth_system = {}
        self.esd_topic_list = []

        if not TOPIC_SCHEMA_DIR.exists():
            TOPIC_SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
            LOGGER.debug('Downloading message schema')
            with TOPIC_SCHEMA_FILE.open('wb') as fh:
                fh.write(urlopen(TOPIC_SCHEMA_URL).read())
            with zipfile.ZipFile(TOPIC_SCHEMA_FILE, "r") as zip_ref:
                zip_ref.extractall(TOPIC_SCHEMA_DIR)

        self.centre_id = self.centre_id_to_dict(TOPIC_SCHEMA_CENTRE)
        self.centre_id = self.centre_id_to_dict(TOPIC_SCHEMA_CENTRE)
        self.wis2_topic = self.wis2_topic_to_dict(TOPIC_SCHEMA_WIS2)
        self.flatten_dict(self.esd_to_dict(TOPIC_SCHEMA_ESD),[])
        self.earth_system = self.list_to_dict(self.esd_topic_list)


    def get_esd(self, topic):
#        if topic[1] == "experimental" and len(topic) > 2:
        if topic[1] == "experimental":
            topic = topic[:2]
        if "/".join(topic) in self.earth_system:
            return True
        else:
            return False

    def get_wis2(self, topic):
        topic[3] = "xxx"
        if "/".join(topic) in self.wis2_topic:
            return True
        else:
            return False

    def get_centre_id(self, topic):
        if "/".join(topic) in self.centre_id:
            return True
        else:
            return False
        
    def wis2_topic_to_dict(self, wis2_list):
        result = {}
        for item in wis2_list:
            result[item] = {'pub': True}
        return result

    def centre_id_to_dict(self, filename):
        result = {}
        with open(filename, mode='r') as infile:
            reader = csv.reader(infile)
            next(reader)  # Skip header row
            for row in reader:
                result[row[0]] = {'pub': True}
        return result
    
    def esd_to_dict(self, filename):
        result = {}
        with open(filename, mode='r') as infile:
            for row in infile:
                dic = result
                tlist = row[:-1].split("/")
                for tkey in tlist:
                    if tkey not in dic:
                        dic[tkey] = {}
                    else:
                        dic = dic[tkey]
        return result

    def flatten_dict(self, adict, alist):
        level = len(alist)
        for dkey in adict:
            alist.append(dkey)
            if not bool(adict[dkey]):
                self.esd_topic_list.append(alist)
            else:
                self.flatten_dict(adict[dkey],alist)
            alist = alist[:level]

    def list_to_dict(self, list_of_lists):
        result = {}
        for item in list_of_lists:
            dkey = "/".join(item)
            result[dkey] = {"pub": True}
        return result

    def sync_topic(self) -> None:
        """
        Sync WIS2 notification schema
    
        :returns: `None`
        """
    
        LOGGER.debug('Syncing topic hierarchy schema')
    
        if TOPIC_SCHEMA_DIR.exists():
            shutil.rmtree(TOPIC_SCHEMA_DIR)
    
        TOPIC_SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    
        LOGGER.debug('Downloading message schema')
        with TOPIC_SCHEMA_FILE.open('wb') as fh:
            fh.write(urlopen(TOPIC_SCHEMA_URL).read())
        with zipfile.ZipFile(TOPIC_SCHEMA_FILE, "r") as zip_ref:
            zip_ref.extractall(TOPIC_SCHEMA_DIR)

        self.centre_id = self.centre_id_to_dict(TOPIC_SCHEMA_CENTRE)
        self.wis2_topic = self.wis2_topic_to_dict(TOPIC_SCHEMA_WIS2)
        self.flatten_dict(self.esd_to_dict(TOPIC_SCHEMA_ESD),[])
        self.earth_system = self.list_to_dict(self.esd_topic_list)

@click.group()
def topic():
    """Topic hierarchy schema management"""
pass


@click.command('sync')
@click.pass_context
@cli_options.OPTION_VERBOSITY
def sync(ctx, verbosity):
    """Sync WIS2 topic hierarchy schema"""

    click.echo('Syncing topic hierarchy schema')
    tpc_mgmt = WIS2_Topic_Hierarchy()
    tpc_mgmt.sync_topic()

topic.add_command(sync)
