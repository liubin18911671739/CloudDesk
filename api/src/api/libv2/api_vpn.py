#!/usr/bin/env python
# coding=utf-8


import traceback

from rethinkdb import RethinkDB

from api import app

from .._common.api_exceptions import Error

r = RethinkDB()
import logging as log

from .flask_rethink import RDB

db = RDB(app)
db.init_app(app)


def active_client(
    kind,
    client_ip,
    remote_ip=None,
    remote_port=None,
    status=False,
):
    # NOTE: Kind will be users/hypers as this are the only two wireguard
    #       interfaces. Remotevpn are handled in users wg interface.
    if kind not in ["users", "hypers"]:
        raise Error(
            "not_found",
            "Active client vpn connection: Vpn kind " + str(kind) + " not found",
            traceback.format_exc(),
            description_code="vpn_kind_not_found",
        )

    connection_data = {
        "connected": status,
        "remote_ip": remote_ip,
        "remote_port": remote_port,
    }

    # Find ip
    if kind == "users":
        with app.app_context():
            if len(
                list(
                    r.table("remotevpn")
                    .get_all(client_ip, index="wg_client_ip")
                    .run(db.conn)
                )
            ):
                r.table("remotevpn").get_all(client_ip, index="wg_client_ip").update(
                    {"vpn": {"wireguard": connection_data}}
                ).run(db.conn)
                return True
            r.table("users").get_all(client_ip, index="wg_client_ip").update(
                {"vpn": {"wireguard": connection_data}}
            ).run(db.conn)
            return True
    else:  # kind = hypers
        with app.app_context():
            r.table("hypervisors").get_all(client_ip, index="wg_client_ip").update(
                {"vpn": {"wireguard": connection_data}}
            ).run(db.conn)
        return True


def reset_connection_status(
    kind,
):
    if kind not in ["users", "hypers", "all"]:
        raise Error(
            "not_found",
            "Reset vpn connection: Vpn kind " + str(kind) + " not found",
            traceback.format_exc(),
            description_code="vpn_kind_not_found",
        )
    connection_data = {"connected": False, "remote_ip": None, "remote_port": None}

    # Find ip
    if kind in ["users", "all"]:
        with app.app_context():
            r.table("users").has_fields({"vpn": {"wireguard": "Address"}}).update(
                {"vpn": {"wireguard": connection_data}}
            ).run(db.conn)
    if kind in ["remotevpn", "all"]:
        with app.app_context():
            r.table("remotevpn").has_fields({"vpn": {"wireguard": "Address"}}).update(
                {"vpn": {"wireguard": connection_data}}
            ).run(db.conn)
    if kind in ["hypers", "all"]:
        with app.app_context():
            r.table("hypervisors").has_fields({"vpn": {"wireguard": "Address"}}).update(
                {"vpn": {"wireguard": connection_data}}
            ).run(db.conn)
    return True


def reset_connections_list_status(
    data,
):
    connection_data = {"connected": False, "remote_ip": None, "remote_port": None}
    for client_vpn in data:
        if client_vpn["kind"] == "users":
            with app.app_context():
                r.table("users").get_all(
                    client_vpn["client_ip"], index="wg_client_ip"
                ).update({"vpn": {"wireguard": connection_data}}).run(db.conn)
                r.table("remotevpn").get_all(
                    client_vpn["client_ip"], index="wg_client_ip"
                ).update({"vpn": {"wireguard": connection_data}}).run(db.conn)
        if client_vpn["kind"] == "hypers":
            with app.app_context():
                r.table("hypervisors").get_all(
                    client_vpn["client_ip"], index="wg_client_ip"
                ).update({"vpn": {"wireguard": connection_data}}).run(db.conn)
    return True
