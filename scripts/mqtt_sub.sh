#!/usr/bin/env bash
mosquitto_sub -h 192.168.8.5 -p 1883 -t "motion/#" -v