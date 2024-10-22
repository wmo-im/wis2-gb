#!/bin/bash

if [[ ${1} == "full" ]]
then
  rm wis2-gb.env docker-compose.yml docker-compose.override.yml
  ln -s wis2-gb.env.full wis2-gb.env
  ln -s docker-compose.yml.full docker-compose.yml
  ln -s docker-compose.override.yml.full docker-compose.override.yml
elif [[ ${1} == "brief" ]]
then
  rm wis2-gb.env docker-compose.yml docker-compose.override.yml
  ln -s wis2-gb.env.brief wis2-gb.env
  ln -s docker-compose.yml.brief docker-compose.yml
  ln -s docker-compose.override.yml.brief docker-compose.override.yml
elif [[ ${1} == "func" ]]
then
  rm wis2-gb.env docker-compose.yml docker-compose.override.yml
  ln -s wis2-gb.env.func wis2-gb.env
  ln -s docker-compose.yml.func docker-compose.yml
  ln -s docker-compose.override.yml.func docker-compose.override.yml
else
  echo "usage $0 [brief|full|func]"
fi

