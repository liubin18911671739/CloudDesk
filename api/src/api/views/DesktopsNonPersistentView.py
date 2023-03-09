

import json
import logging as log
import traceback

from flask import request

#!flask/bin/python
# coding=utf-8
from api import app

from .._common.api_exceptions import Error
from ..libv2.api_allowed import ApiAllowed
from ..libv2.api_templates import ApiTemplates

templates = ApiTemplates()
from ..libv2.quotas import Quotas

quotas = Quotas()
allowed = ApiAllowed()

from ..libv2.api_desktops_nonpersistent import ApiDesktopsNonPersistent

desktops = ApiDesktopsNonPersistent()

from .decorators import has_token, ownsDomainId


@app.route("/api/v3/nonpersistent", methods=["POST"])
@has_token
def api_v3_desktop_new(payload):
    try:
        user_id = payload["user_id"]
        template_id = request.form.get("template", type=str)
    except:
        raise Error("bad_request", "New desktop bad body data", traceback.format_exc())

    if user_id == None or template_id == None:
        raise Error(
            "bad_request",
            "New desktop missing body data",
            traceback.format_exc(),
            description_code="missing_required_data",
        )

    quotas.desktop_create(payload["user_id"])
    quotas.desktop_start(user_id, template_id)

    template = templates.Get(template_id)
    allowed.is_allowed(payload, template, "domains")

    # Leave only one nonpersistent desktop from this template
    desktops.DeleteOthers(user_id, template_id)

    # So now we have checked if desktop exists and if we can create and/or start it
    return (
        json.dumps({"id": desktops.New(user_id, template_id)}),
        200,
        {"Content-Type": "application/json"},
    )


@app.route("/api/v3/nonpersistent/<desktop_id>", methods=["DELETE"])
@has_token
def api_v3_nonpersistent_desktop_delete(payload, desktop_id):
    ownsDomainId(payload, desktop_id)
    desktops.Delete(desktop_id)
    return json.dumps({}), 200, {"Content-Type": "application/json"}
