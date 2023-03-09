

import logging as log
import os
import time
import traceback

from rethinkdb import RethinkDB

from api import app

r = RethinkDB()


class loadConfig:
    def __init__(self, app=None):
        None

    def check_db(self):
        ready = False
        while not ready:
            try:
                conn = r.connect(
                    host=app.config["RETHINKDB_HOST"],
                    port=app.config["RETHINKDB_PORT"],
                    auth_key="",
                    db=app.config["RETHINKDB_DB"],
                )
                print("Database server OK")
                app.system_tables = r.table_list().run(conn)
                ready = True
            except Exception as e:
                print(
                    "Database server "
                    + app.config["RETHINKDB_HOST"]
                    + ":"
                    + app.config["RETHINKDB_PORT"]
                    + " not present. Waiting to be ready"
                )
                time.sleep(2)
        ready = False
        while not ready:
            try:
                tables = list(r.db("isard").table_list().run(conn))
            except:
                print("  No tables yet in database")
                time.sleep(1)
                continue
            if "config" in tables:
                ready = True
            else:
                print("Waiting for database to be populated with all tables...")
                print("   " + str(len(tables)) + " populated")
                time.sleep(2)

        secret = app.ram["secrets"]["isardvdi"] = os.environ["API_ISARDVDI_SECRET"]
        r.db("isard").table("secrets").insert(
            {
                "id": "isardvdi",
                "secret": secret,
                "description": "isardvdi",
                "domain": "localhost",
                "category_id": "default",
                "role_id": "admin",
            },
            conflict="replace",
        ).run(conn)
        secret = app.ram["secrets"]["isardvdi-hypervisors"] = os.environ[
            "API_HYPERVISORS_SECRET"
        ]
        r.db("isard").table("secrets").insert(
            {
                "id": "isardvdi-hypervisors",
                "secret": secret,
                "description": "isardvdi hypervisors access",
                "domain": "*",
                "category_id": "default",
                "role_id": "hypervisor",
            },
            conflict="replace",
        ).run(conn)

    def init_app(self, app):
        """
        Read RethinkDB configuration from environ
        """
        try:
            app.config.setdefault(
                "RETHINKDB_HOST", os.environ.get("RETHINKDB_HOST", "isard-db")
            )
            app.config.setdefault(
                "RETHINKDB_PORT", os.environ.get("RETHINKDB_PORT", "28015")
            )
            app.config.setdefault("RETHINKDB_AUTH", "")
            app.config.setdefault(
                "RETHINKDB_DB", os.environ.get("RETHINKDB_DB", "isard")
            )

            app.config.setdefault("LOG_LEVEL", os.environ.get("LOG_LEVEL", "INFO"))
            app.config.setdefault("LOG_FILE", "isard-api.log")
            app.debug = True if os.environ["LOG_LEVEL"] == "DEBUG" else False

        except:
            log.error(traceback.format_exc())
            log.error("Missing parameters!")
            print("Missing parameters!")
            return False
        print("Initial configuration loaded...")
        self.check_db()
        return True
