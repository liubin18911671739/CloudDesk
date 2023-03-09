

import json
import logging as log

#!flask/bin/python
# coding=utf-8
from api import app

from .._common.api_exceptions import Error
from ..libv2.quotas import Quotas
from .decorators import maintenance

quotas = Quotas()

from ..libv2.api_desktops_common import ApiDesktopsCommon

common = ApiDesktopsCommon()


@app.route("/api/v3/direct/<token>", methods=["GET"])
def api_v3_viewer(token):
    maintenance()
    viewers = common.DesktopViewerFromToken(token)
    if not viewers:
        return
    vmState = viewers.pop("vmState", None)
    return (
        json.dumps(
            {
                "desktopId": viewers.pop("desktopId", None),
                "jwt": viewers.pop("jwt", None),
                "vmName": viewers.pop("vmName", None),
                "vmDescription": viewers.pop("vmDescription", None),
                "vmState": vmState,
                "scheduled": viewers.pop("scheduled", None),
                "viewers": viewers,
                "needs_booking": viewers.pop("needs_booking", False),
                "next_booking_start": viewers.pop("next_booking_start", None),
                "next_booking_end": viewers.pop("next_booking_end", None),
            }
        ),
        200,
        {"Content-Type": "application/json"},
    )
