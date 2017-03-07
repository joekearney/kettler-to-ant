#!/bin/bash
function killExisting() {
  ps -ef | grep -E "(send_to_ant|nc -kl 1234)" | grep -v grep | awk '{ print $2 }' | xargs kill -9
}

function start() {
  nc -kl 1234 | ./send_to_ant.py
}

killExisting
sleep 1
start
