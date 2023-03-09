

import json
import logging as log
from functools import wraps

from flask import request
from rethinkdb import RethinkDB

from api import app

from .._common.api_exceptions import Error

r = RethinkDB()
import traceback

from flask import abort, request

from ..libv2.flask_rethink import RDB

db = RDB(app)
db.init_app(app)

from .._common.tokens import (
    Error,
    get_auto_register_jwt_payload,
    get_header_jwt_payload,
)
from ..libv2.maintenance import Maintenance


def maintenance():
    if Maintenance.enabled:
        abort(503)


def has_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload = get_header_jwt_payload()
        if payload.get("role_id") != "admin":
            maintenance()
        kwargs["payload"] = payload
        return f(*args, **kwargs)

    return decorated


def is_register(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload = get_header_jwt_payload()
        if payload.get("type", "") == "register":
            maintenance()
            kwargs["payload"] = payload
            return f(*args, **kwargs)
        raise Error(
            "forbidden",
            "Invalid register type token",
            traceback.format_exc(),
        )

    return decorated


def is_auto_register(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload = get_auto_register_jwt_payload()
        if payload.get("type", "") == "register":
            maintenance()
            kwargs["payload"] = payload
            return f(*args, **kwargs)
        raise Error(
            "forbidden",
            "Invalid auto register type token",
            traceback.format_exc(),
        )

    return decorated


def is_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload = get_header_jwt_payload()
        if payload["role_id"] == "admin":
            kwargs["payload"] = payload
            return f(*args, **kwargs)
        raise Error(
            "forbidden",
            "Not enough rights.",
            traceback.format_exc(),
        )

    return decorated


def is_admin_or_manager(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload = get_header_jwt_payload()
        if payload.get("role_id") != "admin":
            maintenance()
        if payload["role_id"] == "admin" or payload["role_id"] == "manager":
            kwargs["payload"] = payload
            return f(*args, **kwargs)
        raise Error(
            "forbidden",
            "Not enough rights.",
            traceback.format_exc(),
        )

    return decorated


def is_admin_or_manager_or_advanced(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload = get_header_jwt_payload()
        if payload.get("role_id") != "admin":
            maintenance()
        if (
            payload["role_id"] == "admin"
            or payload["role_id"] == "manager"
            or payload["role_id"] == "advanced"
        ):
            kwargs["payload"] = payload
            return f(*args, **kwargs)
        raise Error(
            "forbidden",
            "Not enough rights.",
            traceback.format_exc(),
        )

    return decorated


def is_not_user(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload = get_header_jwt_payload()
        if payload["role_id"] != "user":
            kwargs["payload"] = payload
            return f(*args, **kwargs)
        raise Error(
            "forbidden",
            "Not enough rights.",
            traceback.format_exc(),
        )

    return decorated


def is_hyper(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        payload = get_header_jwt_payload()
        if payload["role_id"] in ["hypervisor", "admin"]:
            return f(*args, **kwargs)
        raise Error(
            {"error": "forbidden", "description": "Not enough rights" " token."}, 403
        )

    return decorated


def owns_table_item_id(fn):
    @wraps(fn)
    def decorated_view(table, *args, **kwargs):
        payload = get_header_jwt_payload()
        if payload["role_id"] == "admin":
            return fn(payload, table, *args, **kwargs)
        try:
            myargs = request.get_json(force=True)
        except:
            myargs = request.form.to_dict()
        try:
            id = kwargs["id"]
        except:
            try:
                id = myargs["pk"]
            except:
                id = myargs["id"]

        if table == "users":
            ownsUserId(payload, id)
        if table == "domains":
            ownsDomainId(payload, id)
        if table == "categories":
            ownsCategoryId(payload, id)
        if table == "deployments":
            ownsDeploymentId(payload, id)
        return fn(payload, table, *args, **kwargs)

    return decorated_view


### Helpers
def ownsUserId(payload, user_id):
    if payload["role_id"] == "admin":
        return True
    if payload["role_id"] == "manager":
        with app.app_context():
            user = r.table("users").get(user_id).pluck("category", "role").run(db.conn)
        if user["category"] == payload["category_id"] and user["role"] != "admin":
            return True
    if payload["user_id"] == user_id:
        return True
    raise Error(
        "forbidden",
        "Not enough access rights for this user_id " + str(user_id),
        traceback.format_exc(),
    )


def ownsCategoryId(payload, category_id):
    if payload["role_id"] == "admin":
        return True
    if payload["role_id"] == "manager" and category_id == payload["category_id"]:
        return True
    raise Error(
        "forbidden",
        "Not enough access rights for this category_id: " + str(category_id),
        traceback.format_exc(),
    )


def CategoryNameGroupNameMatch(category_name, group_name):
    with app.app_context():
        category = list(
            r.table("categories").filter({"name": category_name.strip()}).run(db.conn)
        )
    if not len(category):
        raise Error(
            "bad_request",
            "Category name " + category_name + " not found",
            traceback.format_exc(),
        )

    with app.app_context():
        group = list(
            r.table("groups")
            .get_all(category[0]["id"], index="parent_category")
            .filter({"name": group_name.strip()})
            .run(db.conn)
        )

    if not len(group):
        raise Error(
            "bad_request",
            "Group name " + group_name + " not found",
            traceback.format_exc(),
        )

    if group[0]["parent_category"] == category[0]["id"]:
        return {
            "category_id": category[0]["id"],
            "category": category[0]["name"],
            "group_id": group[0]["id"],
            "group": group[0]["name"],
        }

    raise Error(
        "bad_request",
        "Category name "
        + category_name
        + " does not have child group name "
        + group_name,
        traceback.format_exc(),
    )


def ownsDomainId(payload, domain_id):
    # User is admin
    if payload.get("role_id", "") == "admin":
        return True

    with app.app_context():
        domain = (
            r.table("domains")
            .get(domain_id)
            .pluck("user", "category", "tag")
            .run(db.conn)
        )

    # User is owner
    if domain["user"] == payload["user_id"]:
        return True

    # User is advanced and the desktop is from one of its deployments
    if payload.get("role_id", "") == "advanced" and domain.get("tag", False):
        with app.app_context():
            if payload["user_id"] == r.table("deployments").get(domain["tag"]).pluck(
                "user"
            )["user"].run(db.conn):
                return True

    # User is manager and the desktop is from its categories
    if payload["role_id"] == "manager":
        with app.app_context():
            if payload.get("category_id", "") == domain["category"]:
                return True

    raise Error(
        "unauthorized",
        "Not enough access rights to access this desktop_id " + str(domain_id),
        traceback.format_exc(),
        description_code="not_enough_rights_desktop" + str(domain_id),
    )


def ownsMediaId(payload, media_id):
    # User is admin
    if payload.get("role_id", "") == "admin":
        return True

    with app.app_context():
        media = r.table("media").get(media_id).pluck("user", "category").run(db.conn)

    # User is owner
    if media["user"] == payload["user_id"]:
        return True

    # User is manager and the media is from its categories
    if payload["role_id"] == "manager":
        with app.app_context():
            if payload.get("category_id", "") == media["category"]:
                return True

    raise Error(
        "forbidden",
        "Not enough access rights to access this media_id " + str(media_id),
        traceback.format_exc(),
        description_code="not_enough_rights_media" + str(media_id),
    )


def ownsDeploymentId(payload, deployment_id):
    if payload["role_id"] == "admin":
        return True
    with app.app_context():
        deployment = r.table("deployments").get(deployment_id).run(db.conn)
    if deployment and deployment["user"] == payload["user_id"]:
        return True
    if payload["role_id"] == "manager":
        with app.app_context():
            deployment_category = (
                r.table("users")
                .get(deployment["user"])
                .pluck("category")
                .run(db.conn)["category"]
            )
        if deployment_category == payload["category_id"]:
            return True

    raise Error(
        "unauthorized",
        "Not enough access rights to access this deployment_id " + str(deployment_id),
        traceback.format_exc(),
    )


def ownsStorageId(payload, storage_id):
    if payload["role_id"] == "admin":
        return True

    with app.app_context():
        storage_user_id = (
            r.table("storage").get(storage_id).pluck("user_id")["user_id"].run(db.conn)
        )
    if storage_user_id == payload["user_id"]:
        return True

    if payload["role_id"] == "manager":
        with app.app_context():
            storage_category_id = (
                r.table("users")
                .get(storage_user_id)
                .pluck("category")["category"]
                .run(db.conn)
            )
        if storage_category_id == payload["category_id"]:
            return True

    raise Error(
        "forbidden",
        "Not enough access rights for this user_id " + payload["user_id"],
        traceback.format_exc(),
    )


def ownsBookingId(payload, bookings_id):
    if payload["role_id"] == "admin":
        return True

    with app.app_context():
        booking_user_id = (
            r.table("bookings")
            .get(bookings_id)
            .pluck("user_id")["user_id"]
            .run(db.conn)
        )
    if booking_user_id == payload["user_id"]:
        return True

    if payload["role_id"] == "manager":
        with app.app_context():
            booking_category_id = (
                r.table("users")
                .get(booking_user_id)
                .pluck("category")["category"]
                .run(db.conn)
            )
        if booking_category_id == payload["category_id"]:
            return True

    raise Error(
        "forbidden",
        "Not enough access rights for this user_id " + payload["user_id"],
        traceback.format_exc(),
    )


def itemExists(item_table, item_id):
    item = r.table(item_table).get(item_id).run(db.conn)
    if not item:
        raise Error(
            "not_found",
            item_table + " not found id: " + item_id,
            traceback.format_exc(),
        )


def userNotExists(uid, category_id, provider="local"):
    if list(
        r.table("users")
        .get_all([uid, category_id, provider], index="uid_category_provider")
        .run(db.conn)
    ):
        raise Error(
            "bad_request",
            "UID " + uid + " already exists in category_id " + category_id,
            traceback.format_exc(),
        )


def checkDuplicate(item_table, item_name, category=False, user=False, item_id=None):

    query = (
        r.table(item_table)
        .get_all(item_name, index="name")
        .filter(lambda item: (item["id"] != item_id))
    )

    ## check duplicate in the same category
    if category:
        if item_table == "groups":
            query = query.filter({"parent_category": category})

        else:
            query = query.filter({"category": category})

    ## check duplicate in the same user
    elif user:
        query = query.filter({"user": user})

    item = list(query.run(db.conn))

    if item:
        raise Error(
            "conflict",
            "Item with this name: " + item_name + " already exists in " + item_table,
            traceback.format_exc(),
            description_code="duplicated_name",
        )


def checkDuplicateUser(item_uid, category, provider):
    query = r.table("users").get_all(
        [item_uid, category, provider], index="uid_category_provider"
    )

    item = list(query.run(db.conn))

    if item:
        raise Error(
            "conflict",
            "User with this username: "
            + item_uid
            + " already exists in this category.",
            traceback.format_exc(),
        )


def checkDuplicateCustomURL(custom_url, category_id=None):
    query = (
        r.table("categories")
        .get_all(custom_url, index="custom_url_name")
        .filter(lambda item: (item["id"] != category_id))
    )

    if len(list(query.run(db.conn))) > 0:
        raise Error(
            "conflict", "Custom URL name already exists", traceback.format_exc()
        )


def allowedTemplateId(payload, template_id):
    with app.app_context():
        template = (
            r.table("domains")
            .get(template_id)
            .pluck("user", "allowed", "category")
            .default(None)
            .run(db.conn)
        )
    if not template:
        raise Error(
            "not_found",
            "Not found template_id " + str(template_id),
            traceback.format_exc(),
        )
    if payload["user_id"] == template["user"]:
        return True
    alloweds = template["allowed"]
    if payload["role_id"] == "admin":
        return True
    if (
        payload["role_id"] == "manager"
        and payload["category_id"] == template["category"]
    ):
        return True
    if alloweds["roles"] != False:
        if alloweds["roles"] == []:
            return True
        if payload["role_id"] in alloweds["roles"]:
            return True
    if alloweds["categories"] != False:
        if alloweds["categories"] == []:
            return True
        if payload["category_id"] in alloweds["categories"]:
            return True
    if alloweds["groups"] != False:
        if alloweds["groups"] == []:
            return True
        if payload["group_id"] in alloweds["groups"]:
            return True
    if alloweds["users"] != False:
        if alloweds["users"] == []:
            return True
        if payload["user_id"] in alloweds["users"]:
            return True
    raise Error(
        "forbidden",
        "Not enough access rights for this template_id " + str(template_id),
        traceback.format_exc(),
    )
