

import json
import logging
import os
import time
import traceback
from datetime import datetime, timedelta

import requests
from jose import jwt

from .api_exceptions import Error


def header_auth():
    token = jwt.encode(
        {
            "exp": datetime.utcnow() + timedelta(seconds=20),
            "kid": "isardvdi",
            "data": {
                "role_id": "admin",
                "category_id": "*",
            },
        },
        os.environ["API_ISARDVDI_SECRET"],
        algorithm="HS256",
    )
    return {"Authorization": "Bearer " + token}


def is_ip(ip):
    try:
        parts = ip.split(".")
        if len(parts) != 4:
            return False
        for x in parts:
            if not x.isdigit():
                return False
            i = int(x)
            if i < 0 or i > 255:
                return False
    except:
        return False
    return True


container_base_path = {
    "isard-api": "/api/v3",
    "isard-scheduler": "/scheduler",
}


class ApiRest:
    def __init__(self, service="isard-api", base_url=None):
        if base_url:
            self.base_url = base_url
            self.verify_cert = False if base_url.startswith("http://") else True
        else:
            if service == "isard-api":
                actual_server = os.environ.get("API_DOMAIN")
            if service == "isard-scheduler":
                actual_server = "isard-scheduler"

            if actual_server:
                if actual_server == "localhost" or actual_server.startswith("isard-"):
                    self.base_url = (
                        "http://"
                        + actual_server
                        + ":5000"
                        + container_base_path[service]
                    )
                    self.verify_cert = False
                else:
                    self.base_url = (
                        "https://" + actual_server + container_base_path[service]
                    )
                    self.verify_cert = False if is_ip(actual_server) else True
            else:
                self.base_url = (
                    "http://" + service + ":5000" + container_base_path[service]
                )
                self.verify_cert = False
        self.service = service
        logging.info("Api base url for service " + service + " set to " + self.base_url)

    def wait_for(self, max_retries=-1, timeout=1):
        while max_retries:
            try:
                logging.info(
                    "Check connection to "
                    + self.service
                    + " container at "
                    + self.base_url
                )
                self.get()
                max_retries = 0
            except:
                logging.error(
                    "Unable to reach " + self.service + " container at " + self.base_url
                )
                time.sleep(timeout)
                if max_retries >= 0:
                    max_retries -= 1

    def get(self, url=""):
        try:
            resp = requests.get(
                self.base_url + url, headers=header_auth(), verify=self.verify_cert
            )
            if resp.status_code == 200:
                return json.loads(resp.text)
            raise Error(
                "bad_request",
                "Bad request while contacting " + self.base_url + url + " method GET",
            )
        except:
            raise Error(
                "internal_server",
                "Could not contact " + self.base_url + url + " method GET",
                traceback.format_exc(),
            )

    def post(self, url, data={}):
        try:
            resp = requests.post(
                self.base_url + url,
                json=data,
                headers=header_auth(),
                verify=self.verify_cert,
            )
            if resp.status_code == 200:
                return json.loads(resp.text)
            raise Error(
                "bad_request",
                "Bad request while contacting " + self.base_url + url + " method POST",
            )
        except:
            raise Error(
                "internal_server",
                "Could not contact " + self.base_url + url + " method POST",
                traceback.format_exc(),
            )

    def put(self, url, data={}):
        try:
            resp = requests.put(
                self.base_url + url,
                json=data,
                headers=header_auth(),
                verify=self.verify_cert,
            )
            if resp.status_code == 200:
                return json.loads(resp.text)
            raise Error(
                "bad_request",
                "Bad request while contacting " + self.base_url + url + " method PUT",
            )
        except:
            raise Error(
                "internal_server",
                "Could not contact " + self.base_url + url + " method PUT",
                traceback.format_exc(),
            )

    def delete(self, url, data={}):
        try:
            resp = requests.delete(
                self.base_url + url,
                json=data,
                headers=header_auth(),
                verify=self.verify_cert,
            )
            if resp.status_code == 200:
                return json.loads(resp.text)
            raise Error(
                "bad_request",
                "Bad request while contacting "
                + self.base_url
                + url
                + " method DELETE",
            )
        except:
            raise Error(
                "internal_server",
                "Could not contact " + self.base_url + url + " method DELETE",
                traceback.format_exc(),
            )
