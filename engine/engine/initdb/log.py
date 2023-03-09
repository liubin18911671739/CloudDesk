

#!/usr/bin/env python
# coding=utf-8

import configparser
import logging as log
import os

from .lib import loadConfig

try:
    LOG_LEVEL = loadConfig().cfg["LOG_LEVEL"]
except Exception as e:
    LOG_LEVEL = "INFO"

# LOG FORMATS
LOG_FORMAT = "%(asctime)s %(msecs)d - %(levelname)s - %(threadName)s: %(message)s"
LOG_DATE_FORMAT = "%Y/%m/%d %H:%M:%S"
LOG_LEVEL_NUM = log.getLevelName(LOG_LEVEL)
log.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT, level=LOG_LEVEL_NUM)
