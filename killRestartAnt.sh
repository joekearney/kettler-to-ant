#!/bin/bash
function killExisting() {
  ps -ef | grep -E "(tcp_ant_adapter|nc -kl 1234)" | grep -v grep | awk '{ print $2 }' | xargs kill -9
}

function start() {
  nc -kl 1234 | ./tcp_ant_adapter.py
}

killExisting
sleep 1
start
