#!/bin/bash
# Wis2 Global Broker Platform  Installation
# Launch Template UserData
################################
sudo yum install -y docker
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
sudo systemctl enable docker
sudo systemctl start docker
sudo yum install -y python3.10 python3.10-pip unzip
sudo /usr/bin/pip3.10 install pip --upgrade
sudo /usr/bin/pip3.10 install pyopenssl --upgrade
sudo /usr/bin/pip3.10 install requests==2.26.0 urllib3==1.26.0
sudo yum -y install cmake
sudo docker plugin install grafana/loki-docker-driver:2.9.2 --alias loki --grant-all-permissions
sudo useradd --groups docker,wheel,systemd-journal wis2global
sudo chage -E -1 -I -1 -M -1 wis2global
sudo echo "wis2global:PassW0rd" | /usr/sbin/chpasswd
