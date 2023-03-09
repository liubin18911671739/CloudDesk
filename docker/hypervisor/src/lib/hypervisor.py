import json
import os
import sys
import traceback
from pprint import pprint
from time import sleep

from setup import DeleteHypervisor, EnableHypervisor, SetupHypervisor

# from wireguard import SetupWireguard

if not len(sys.argv):
    print("You should pass action: setup, enable, delete")
    exit(1)

### Setup hypervisor + certificates
if sys.argv[1] == "setup":
    try:
        SetupHypervisor()
    except:
        print(traceback.format_exc())
        exit(1)

if sys.argv[1] == "delete":
    try:
        DeleteHypervisor()
    except:
        print(traceback.format_exc())
        exit(1)

if sys.argv[1] == "enable":
    try:
        print(EnableHypervisor())
    except:
        print(traceback.format_exc())
        exit(1)
