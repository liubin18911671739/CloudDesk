

import os
import signal
import threading
from distutils.util import strtobool
from time import sleep

from api._common.api_rest import ApiRest, is_ip
from api._common.storage_pool import DEFAULT_STORAGE_POOL_ID

# from api.libv2 import api_disks_watchdog
from flask import Flask

from api import app

storage_domain = os.environ.get("STORAGE_DOMAIN")
video_port = os.environ.get("VIEWER_BROWSER")
if storage_domain and storage_domain != "isard-storage":
    video_port = "" if not video_port else ":" + str(video_port)
    storage_base_url = "https://" + storage_domain + video_port + "/toolbox"
    verify_cert = False if is_ip(storage_domain) else True
    if not verify_cert:
        app.logger.warning(
            "Connection to this container from isard-api will ignore certificate validation as STORAGE_DOMAIN="
            + str(storage_domain)
            + " is not a valid DNS"
        )
else:
    storage_base_url = "http://isard-storage:5000/toolbox"
    verify_cert = False


def delete_node(*args, **kwargs):
    app.logger.info("App stopping")
    if hasattr(app, "storage_node_id"):
        app.logger.info(f"Deleting storage node {app.storage_node_id}")
        if not ApiRest().delete("/storage_node", data={"id": app.storage_node_id}):
            # Docker default stop timeout is 10s
            sleep(2)
            delete_node()
        else:
            app.logger.info(f"Deleted storage node {app.storage_node_id}")


def register_node():
    app.logger.info("Registering storage node")
    # Haproxy is configured with 5s as health check interval
    sleep(10)
    try:
        app.storage_node_id = ApiRest().post(
            "/storage_node",
            data={
                "id": f"{storage_base_url}/api/check",
                "storage_pools": os.environ.get(
                    "CAPABILITIES_STORAGE_POOLS", DEFAULT_STORAGE_POOL_ID
                ).split(","),
                "verify_cert": verify_cert,
            },
        )
    except:
        app.logger.error(
            "Unable to reach isard-api container at "
            + str(ApiRest().base_url)
            + " or isard-api could not reach this isard-storage container at "
            + storage_base_url
        )
    if hasattr(app, "storage_node_id"):
        app.logger.info(f"Storage node registered as {app.storage_node_id}")
    else:
        register_node()


if __name__ == "__main__":
    app.logger.info("Starting application")
    # api_disks_watchdog.start_disks_watchdog()
    debug = True if os.environ["LOG_LEVEL"] == "DEBUG" else False
    if strtobool(os.environ.get("CAPABILITIES_DISK", "true")):
        app.logger.info("Storage has disk capabilities")
        signal.signal(signal.SIGTERM, delete_node)
        signal.signal(signal.SIGINT, delete_node)
        signal.signal(signal.SIGQUIT, delete_node)
        threading.Thread(target=register_node).start()
    else:
        app.logger.warning(
            "Storage does not have disk capabilities. Not registering in system."
        )
    app.run(host="0.0.0.0", debug=debug, port=5000)
