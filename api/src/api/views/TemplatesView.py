

import json
import logging as log
import traceback

from flask import request
from rethinkdb import RethinkDB

#!flask/bin/python
# coding=utf-8
from api import app

from ..libv2.flask_rethink import RDB

r = RethinkDB()
db = RDB(app)
db.init_app(app)

from .._common.api_exceptions import Error
from ..libv2.helpers import gen_payload_from_user
from ..libv2.quotas import Quotas

quotas = Quotas()

from ..libv2.api_users import ApiUsers

users = ApiUsers()

from ..libv2.api_templates import ApiTemplates

templates = ApiTemplates()

from ..libv2.api_allowed import ApiAllowed

allowed = ApiAllowed()

from ..libv2.validators import _validate_item, check_user_duplicated_domain_name
from .decorators import (
    allowedTemplateId,
    checkDuplicate,
    has_token,
    itemExists,
    ownsDomainId,
)


@app.route("/api/v3/templates/new/check_quota", methods=["GET"])
@has_token
def api_v3_templates_check_quota(payload):
    quotas.template_create(payload["user_id"])
    return (
        json.dumps({}),
        200,
        {"Content-Type": "application/json"},
    )


@app.route("/api/v3/template", methods=["POST"])
@has_token
def api_v3_template_new(payload):
    quotas.template_create(payload["user_id"])
    data = request.get_json(force=True)
    data["user_id"] = payload["user_id"]
    data = _validate_item("template", data)
    ownsDomainId(payload, data["desktop_id"])
    if data["name"] == None or data["desktop_id"] == None:
        raise Error(
            "bad_request",
            "New template bad body data",
            traceback.format_exc(),
            description_code="new_template_bad_body_data",
        )

    check_user_duplicated_domain_name(data["name"], data["user_id"], "template")
    templates.New(
        payload["user_id"],
        data["template_id"],
        data["name"],
        data["desktop_id"],
        data["allowed"],
        description=data["description"],
        enabled=data["enabled"],
    )

    return (
        json.dumps({"id": data["id"]}),
        200,
        {"Content-Type": "application/json"},
    )


@app.route("/api/v3/template/duplicate/<template_id>", methods=["POST"])
@has_token
def api_v3_template_duplicate(payload, template_id):
    ownsDomainId(payload, template_id)
    data = request.get_json(force=True)
    if data.get("user_id"):
        payload = gen_payload_from_user(data["user_id"])
    data["user_id"] = payload["user_id"]
    data = _validate_item("template_duplicate", data)

    check_user_duplicated_domain_name(
        data["name"],
        payload["user_id"],
        "template",
        template_id,
    )

    new_template_id = templates.Duplicate(
        payload,
        template_id,
        data["name"],
        data["allowed"],
        description=data.get("description", ""),
        enabled=data.get("enabled", False),
    )
    return (
        json.dumps({"id": new_template_id}),
        200,
        {"Content-Type": "application/json"},
    )


@app.route("/api/v3/template/<template_id>", methods=["GET"])
@has_token
def api_v3_template(payload, template_id):
    template = templates.Get(template_id)
    allowed.is_allowed(payload, template, "domains")
    return (
        json.dumps(templates.Get(template_id)),
        200,
        {"Content-Type": "application/json"},
    )


@app.route("/api/v3/template/<template_id>", methods=["DELETE"])
@has_token
def api_v3_template_delete(payload, template_id):
    ownsDomainId(payload, template_id)
    templates.Delete(template_id)
    return json.dumps({}), 200, {"Content-Type": "application/json"}


# Disable or enable template
@app.route("/api/v3/template/update", methods=["PUT"])
@has_token
def api_v3_template_update(payload):
    data = request.get_json(force=True)
    template_id = data.pop("id")
    ownsDomainId(payload, template_id)
    _validate_item("template_update", data)
    if data.get("enabled"):
        quotas.template_create(payload["user_id"])
    return (
        json.dumps(templates.UpdateTemplate(template_id, data)),
        200,
        {"Content-Type": "application/json"},
    )


@app.route("/api/v3/user/templates", methods=["GET"])
@has_token
def api_v3_user_templates(payload):
    with app.app_context():
        group = r.table("groups").get(payload["group_id"])["uid"].run(db.conn)
    if group == None:
        raise Error(
            "not_found",
            "Group not found",
            traceback.format_exc(),
            description_code="ot_found",
        )
    dropdown_templates = [
        {
            "id": t["id"],
            "name": t["name"],
            "category": t["category"],
            "group": group,
            "user_id": t["user"],
            "icon": t["icon"],
            "image": t["image"],
            "allowed": t["allowed"],
            "description": t["description"],
            "enabled": t["enabled"],
            "desktop_size": (
                r.table("storage")
                .get(t["create_dict"]["hardware"]["disks"][0]["storage_id"])
                .pluck({"qemu-img-info": {"actual-size"}})
                .run(db.conn)
            )["qemu-img-info"]["actual-size"]
            if t["create_dict"]["hardware"].get("disks", [{}])[0].get("storage_id")
            else 0,
        }
        for t in users.Templates(payload)
    ]
    return json.dumps(dropdown_templates), 200, {"Content-Type": "application/json"}


@app.route("/api/v3/user/templates/allowed/<kind>", methods=["GET"])
@has_token
def api_v3_user_templates_allowed(payload, kind):
    if kind == "shared":
        query_filter = (
            lambda templates: r.not_(templates["user"] == payload["user_id"])
            & templates["enabled"]
        )
    elif kind == "all":
        query_filter = {"enabled": True, "status": "Stopped"}
    templates = allowed.get_items_allowed(
        payload=payload,
        table="domains",
        query_pluck=[
            "id",
            "name",
            "kind",
            "category",
            "category_name",
            "group",
            "group_name",
            "icon",
            "image",
            "user",
            "description",
        ],
        query_filter=query_filter,
        index_key="kind",
        index_value="template",
        order="name",
        query_merge=True,
    )
    return (
        json.dumps(templates),
        200,
        {"Content-Type": "application/json"},
    )
