#!/usr/bin/env python
# coding=utf-8


from rethinkdb import RethinkDB

from api import app

r = RethinkDB()
import traceback

from .._common.api_exceptions import Error
from .flask_rethink import RDB

db = RDB(app)
db.init_app(app)


def _validate_item(item, data, normalize=True):
    if not app.validators[item].validate(data):
        raise Error(
            "bad_request",
            "Data validation for "
            + item
            + " failed: "
            + str(app.validators[item].errors),
            traceback.format_exc(),
        )
    if normalize:
        return app.validators[item].normalized(data)
    return data


def _validate_table(table):
    if table not in app.system_tables:
        raise Error(
            "not_found",
            "Table " + table + " does not exist.",
            traceback.format_exc(),
        )


def _validate_alloweds(alloweds):
    None


def check_user_duplicated_domain_name(name, user_id, kind="desktop", item_id=None):
    with app.app_context():
        if (
            r.table("domains")
            .get_all([kind, user_id], index="kind_user")
            .filter(
                lambda item: (item["name"] == name.strip()) & (item["id"] != item_id)
            )
            .count()
            .run(db.conn)
            > 0
        ):
            user_name = r.table("users").get(user_id).pluck("name").run(db.conn)["name"]
            raise Error(
                "conflict",
                "User " + user_name + " already has " + kind + " with name " + name,
                traceback.format_exc(),
                description_code="new_desktop_name_exists"
                if kind == "desktop"
                else "new_template_name_exists",
            )
