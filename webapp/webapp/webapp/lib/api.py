

import json
import queue

#!/usr/bin/env python
# coding=utf-8
import random
import sys
import time
from threading import Thread
from uuid import uuid4

import rethinkdb as r
from flask_login import current_user

from webapp import app

from ..lib.log import *
from .flask_rethink import RethinkDB

db = RethinkDB(app)
db.init_app(app)

from ..auth.authentication import Password, user_reloader
from ..lib.quotas import QuotaLimits
from .admin_api import flatten

quotas = QuotaLimits()


class isard:
    def __init__(self):
        with app.app_context():
            try:
                self.config = r.table("config").get(1).run(db.conn)
                self.f = flatten()
            except Exception as e:
                log.error("Unable to read config table from RethinkDB isard database")
                log.error(
                    "If you need to recreate isard database you should activate wizard again:"
                )
                log.error(
                    "   REMOVE install/.wizard file  (rm install/.wizard) and start isard again"
                )
                exit(1)
        pass

    def auto_interface_set(self, user, id, remote_addr):
        with app.app_context():
            dict = (
                r.table("domains")
                .get(id)
                .pluck("create_dict")
                .run(db.conn)["create_dict"]
            )
            if dict["hardware"]["interfaces"][0] == "default":
                return self.update_domain_network(user, id, remote_addr=remote_addr)
            else:
                return self.update_domain_network(
                    user, id, interface_id=dict["hardware"]["interfaces"][0]
                )

    def update_domain_network(self, user, id, interface_id=False, remote_addr=False):
        try:
            if interface_id:
                with app.app_context():
                    iface = r.table("interfaces").get(interface_id).run(db.conn)
                    dict = (
                        r.table("domains")
                        .get(id)
                        .pluck("create_dict")
                        .run(db.conn)["create_dict"]
                    )
                    dict["hardware"]["interfaces"] = [iface["id"]]
                    return self.check(
                        r.table("domains")
                        .get(id)
                        .update({"create_dict": dict})
                        .run(db.conn),
                        "replaced",
                    )
            return True
        except Exception as e:
            log.error("Error updating domain " + id + " network interface.\n" + str(e))
        return False

    def update_table_value(self, table, id, field, value):
        with app.app_context():
            return self.check(
                r.table(table)
                .get(id)
                .update({field: value, "accessed": int(time.time())})
                .run(db.conn),
                "replaced",
            )

    """
        MEDIA
    """

    def get_media_installs(self):
        with app.app_context():
            data = r.table("virt_install").run(db.conn)
            return self.f.table_values_bstrap(data)

    """
    USER
    """

    def get_user(self, user):
        with app.app_context():
            user = self.f.flatten_dict(r.table("users").get(user).run(db.conn))
            user["password"] = ""
        return user

    def get_user_domains(self, user, filterdict=False):
        if not filterdict:
            filterdict = {"kind": "desktop"}
        with app.app_context():
            domains = list(
                r.table("domains")
                .get_all(user, index="user")
                .filter(filterdict)
                .without("xml", "history_domain", "allowed")
                .run(db.conn)
            )
            domains = [d for d in domains if d.get("tag_visible", True)]
        return domains

    def get_user_tagged_domains(self, current_user, id=False):
        tags = (
            r.table("deployments")
            .get_all(current_user.id, index="user")
            .pluck("id", "name")
            .run(db.conn)
        )
        domains = []
        for tag in tags:
            domains += list(
                r.table("domains")
                .get_all(tag["id"], index="tag")
                .without("xml", "history_domain", "allowed")
                .run(db.conn)
            )
        return domains

    def get_user_media(self, userid):
        with app.app_context():
            return list(r.table("media").get_all(userid, index="user").run(db.conn))

    def get_domain(self, id, human_size=False, flatten=True):
        # ~ Should verify something???
        with app.app_context():
            domain = (
                r.table("domains")
                .get(id)
                .without(
                    "xml",
                    "xml_to_start",
                    "history_domain",
                    "hw_stats",
                    "disks_info",
                    "progress",
                    "jumperurl",
                    "viewer",
                )
                .run(db.conn)
            )
        try:
            if flatten:
                domain = self.f.flatten_dict(domain)
                if human_size:
                    domain["hardware-memory"] = self.human_size(
                        domain["hardware-memory"] * 1000
                    )
                    if "disks_info" in domain:
                        for i, dict in enumerate(domain["disks_info"]):
                            for key in dict.keys():
                                if "size" in key:
                                    domain["disks_info"][i][key] = self.human_size(
                                        domain["disks_info"][i][key]
                                    )
            else:
                """This != used and will do nothing as we should implement a recursive function to look for all the nested 'size' fields"""
                if human_size:
                    domain["hardware"]["memory"] = self.human_size(
                        domain["hardware"]["memory"] * 1000
                    )
                    if "disks_info" in domain:
                        for i, dict in enumerate(domain["disks_info"]):
                            for key in dict.keys():
                                if "size" in key:
                                    domain["disks_info"][i][key] = self.human_size(
                                        domain["disks_info"][i][key]
                                    )
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error(exc_type, fname, exc_tb.tb_lineno)
        return domain

    def get_domain_create_dict(self, id, human_size=False, flatten=True):
        # ~ Should verify something???
        with app.app_context():
            hardware = (
                r.table("domains")
                .get(id)
                .pluck({"create_dict": "hardware"})
                .run(db.conn)["create_dict"]
            )
        try:
            if flatten:
                hardware = self.f.flatten_dict(hardware)
                if human_size:
                    hardware["hardware-memory"] = self.human_size(
                        hardware["hardware-memory"] * 1000
                    )
                    if "disks_info" in hardware:
                        for i, dict in enumerate(hardware["disks_info"]):
                            for key in dict.keys():
                                if "size" in key:
                                    hardware["disks_info"][i][key] = self.human_size(
                                        hardware["disks_info"][i][key]
                                    )
            else:
                """This != used and will do nothing as we should implement a recursive function to look for all the nested 'size' fields"""
                if human_size:
                    hardware["hardware"]["memory"] = self.human_size(
                        hardware["hardware"]["memory"] * 1000
                    )
                    if "disks_info" in hardware:
                        for i, dict in enumerate(hardware["disks_info"]):
                            for key in dict.keys():
                                if "size" in key:
                                    hardware["disks_info"][i][key] = self.human_size(
                                        hardware["disks_info"][i][key]
                                    )
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            log.error(exc_type, fname, exc_tb.tb_lineno)
        return hardware

    def get_domain_media(self, id):
        with app.app_context():
            domain_cd = (
                r.table("domains")
                .get(id)
                .pluck({"create_dict": {"hardware"}})
                .run(db.conn)["create_dict"]["hardware"]
            )
        media = {"isos": [], "floppies": []}
        if "isos" in domain_cd and domain_cd["isos"] != []:
            for m in domain_cd["isos"]:
                try:
                    iso = (
                        r.table("media")
                        .get(m["id"])
                        .pluck("id", "name", {"progress": "total"})
                        .run(db.conn)
                    )
                    # iso['size']=iso.pop('progress')['total']
                    media["isos"].append(iso)
                except:
                    """Media does not exist"""
                    None
        if "floppies" in domain_cd and domain_cd["floppies"] != []:
            for m in domain_cd["floppies"]:
                try:
                    fd = (
                        r.table("media")
                        .get(m["id"])
                        .pluck("id", "name", {"progress": "total"})
                        .run(db.conn)
                    )
                    # fd['size']=fd.pop('progress')['total']
                    media["floppies"].append(fd)
                except:
                    """Media does not exist"""
                    None
        return media

    def get_domain_media_list(self, id):
        with app.app_context():
            domain_cd = (
                r.table("domains")
                .get(id)
                .pluck({"create_dict": {"hardware"}})
                .run(db.conn)["create_dict"]["hardware"]
            )
        media = []
        if "isos" in domain_cd and domain_cd["isos"] != []:
            for m in domain_cd["isos"]:
                try:
                    iso = (
                        r.table("media")
                        .get(m["id"])
                        .pluck("id", "name", {"progress": "total"})
                        .merge({"kind": "iso"})
                        .run(db.conn)
                    )
                    iso["size"] = iso.pop("progress")["total"]
                    media.append(iso)
                except:
                    """Media does not exist"""
                    None
        if "floppies" in domain_cd and domain_cd["floppies"] != []:
            for m in domain_cd["floppies"]:
                try:
                    fd = (
                        r.table("media")
                        .get(m["id"])
                        .pluck("id", "name", {"progress": "total"})
                        .merge({"kind": "fd"})
                        .run(db.conn)
                    )
                    fd["size"] = fd.pop("progress")["total"]
                    media.append(fd)
                except:
                    """Media does not exist"""
                    None
        return media

    def get_category(self, category):
        with app.app_context():
            try:
                return (
                    r.table("categories")
                    .get(category)
                    .pluck("id", "name", "description")
                    .run(db.conn)
                )
            except:
                return False

    def get_login_path():
        with app.app_context():
            category = (
                r.table("categories")
                .get(current_user.category)
                .pluck("id", "name", "frontend", "custom_url_name")
                .run(db.conn)
            )
        if category.get("frontend", False):
            return "/login/"
        else:
            return "/login/" + category.get("custom_url_name")

    def get_user_templates(self, user):
        with app.app_context():
            dom = list(
                r.table("domains")
                .get_all(["template", user], index="kind_user")
                .without("viewer", "xml", "history_domain")
                .run(db.conn)
            )
            return dom  # self.f.table_values_bstrap(dom)

    def template_update(self, template_id, data):
        with app.app_context():
            template = r.table("domains").get(template_id).run(db.conn)
        if template and template["kind"].endswith("template"):
            with app.app_context():
                r.table("domains").get(template_id).update(data).run(db.conn)
            return True
        return False

    def get_alloweds(self, user, table, pluck=[], order=False):
        with app.app_context():
            ud = r.table("users").get(user).run(db.conn)
            delete_allowed_key = False
            if not "allowed" in pluck:
                pluck.append("allowed")
                delete_allowed_key = True
            allowed_data = {}
            if table == "domains":
                if order:
                    data = (
                        r.table("domains")
                        .get_all("template", index="kind")
                        .order_by(order)
                        .group("category")
                        .pluck({"id", "name", "allowed"})
                        .run(db.conn)
                    )
                else:
                    data = (
                        r.table("domains")
                        .get_all("template", index="kind")
                        .group("category")
                        .pluck({"id", "name", "allowed"})
                        .run(db.conn)
                    )
                for group in data:
                    allowed_data[group] = []
                    for d in data[group]:
                        # False doesn't check, [] means all allowed
                        # Role is the master and user the least. If allowed in roles,
                        #   won't check categories, groups, users
                        allowed = d["allowed"]
                        if d["allowed"]["roles"] != False:
                            if not d["allowed"]["roles"]:  # Len != 0
                                if delete_allowed_key:
                                    d.pop("allowed", None)
                                allowed_data[group].append(d)
                                continue
                            if ud["role"] in d["allowed"]["roles"]:
                                if delete_allowed_key:
                                    d.pop("allowed", None)
                                allowed_data[group].append(d)
                                continue
                        if d["allowed"]["categories"] != False:
                            if not d["allowed"]["categories"]:
                                if delete_allowed_key:
                                    d.pop("allowed", None)
                                allowed_data[group].append(d)
                                continue
                            if ud["category"] in d["allowed"]["categories"]:
                                if delete_allowed_key:
                                    d.pop("allowed", None)
                                allowed_data[group].append(d)
                                continue
                        if d["allowed"]["groups"] != False:
                            if not d["allowed"]["groups"]:
                                if delete_allowed_key:
                                    d.pop("allowed", None)
                                allowed_data[group].append(d)
                                continue
                            if ud["group"] in d["allowed"]["groups"]:
                                if delete_allowed_key:
                                    d.pop("allowed", None)
                                allowed_data[group].append(d)
                                continue
                        if d["allowed"]["users"] != False:
                            if not d["allowed"]["users"]:
                                if delete_allowed_key:
                                    d.pop("allowed", None)
                                allowed_data[group].append(d)
                                continue
                            if user in d["allowed"]["users"]:
                                if delete_allowed_key:
                                    d.pop("allowed", None)
                                allowed_data[group].append(d)
                tmp_data = allowed_data.copy()
                for k, v in tmp_data.items():
                    if not len(tmp_data[k]):
                        allowed_data.pop(k, None)
                return allowed_data
            else:
                if order:
                    data = r.table(table).order_by(order).pluck(pluck).run(db.conn)
                else:
                    data = r.table(table).pluck(pluck).run(db.conn)
            allowed_data = []
            for d in data:
                # False doesn't check, [] means all allowed
                # Role is the master and user the least. If allowed in roles,
                #   won't check categories, groups, users
                allowed = d["allowed"]
                if d["allowed"]["roles"] != False:
                    if not d["allowed"]["roles"]:  # Len != 0
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if ud["role"] in d["allowed"]["roles"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                if d["allowed"]["categories"] != False:
                    if not d["allowed"]["categories"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if ud["category"] in d["allowed"]["categories"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                if d["allowed"]["groups"] != False:
                    if not d["allowed"]["groups"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if ud["group"] in d["allowed"]["groups"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                if d["allowed"]["users"] != False:
                    if not d["allowed"]["users"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if user in d["allowed"]["users"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
            return allowed_data

    def get_alloweds_select2(self, allowed):
        for k, v in allowed.items():
            if v != False and len(v):
                with app.app_context():
                    """allowed[k]=list(r.table(k).get_all(r.args(v), index='id').pluck('id','name').map(
                    lambda doc: doc.merge({'text': doc['name']}).without('name')).run(db.conn))"""
                    allowed[k] = list(
                        r.table(k)
                        .get_all(r.args(v), index="id")
                        .pluck("id", "name", "parent_category")
                        .run(db.conn)
                    )
        return allowed

    def get_all_alloweds_domains(self, userid):
        with app.app_context():
            ud = r.table("users").get(userid).run(db.conn)
            ## If the user owner is deleted won't return the template
            data = list(
                r.db("isard")
                .table("domains")
                .get_all(["template", True], index="template_enabled")
                .eq_join("user", r.db("isard").table("users"))
                .without({"right": {"id": True}})
                .pluck({"right": "role"}, "left")
                .zip()
                .pluck(
                    "id",
                    "name",
                    "allowed",
                    "kind",
                    "group",
                    "role",
                    "icon",
                    "category",
                    "user",
                    "description",
                    "status",
                )
                .order_by("name")
                .run(db.conn)
            )
            ## This will get all but missing 'role' field of owner. Needs that function.
            # data = list(r.db('isard').table("domains").filter(r.row['kind'].match("template"))
            #         .pluck('id','name','allowed','kind','group','role','icon','category','user','description','status')
            #         .order_by('name')
            #         .run(db.conn))
        alloweds = []
        for d in data:
            try:
                d["username"] = (
                    r.table("users").get(d["user"]).pluck("name").run(db.conn)["name"]
                )
            except:
                d["username"] = "X " + d["user"]
            if ud["role"] == "admin":
                alloweds.append(d)
                continue
            if d["user"] == ud["id"]:
                alloweds.append(d)
                continue
            if d["allowed"]["roles"] != False:
                if len(d["allowed"]["roles"]) == 0:
                    alloweds.append(d)
                    continue
                else:
                    if ud["role"] in d["allowed"]["roles"]:
                        alloweds.append(d)
                        continue
            if d["allowed"]["categories"] != False:
                if len(d["allowed"]["categories"]) == 0:
                    alloweds.append(d)
                    continue
                else:
                    if ud["category"] in d["allowed"]["categories"]:
                        alloweds.append(d)
                        continue
            if d["allowed"]["groups"] != False:
                if len(d["allowed"]["groups"]) == 0:
                    alloweds.append(d)
                    continue
                else:
                    if ud["group"] in d["allowed"]["groups"]:
                        alloweds.append(d)
                        continue
            if d["allowed"]["users"] != False:
                if len(d["allowed"]["users"]) == 0:
                    alloweds.append(d)
                    continue
                else:
                    if ud["id"] in d["allowed"]["users"]:
                        alloweds.append(d)
                        continue
        return alloweds

    def get_all_alloweds_table(self, table, userid, pluck="default", skipOwner=False):
        if pluck == "default":
            pluck = ["id", "name", "allowed", "kind", "icon", "description"]
        if pluck != False:
            if "user" not in pluck:
                pluck.append("user")
            if "allowed" not in pluck:
                pluck.append("allowed")
        with app.app_context():
            ud = r.table("users").get(userid).run(db.conn)
            delete_allowed_key = False
            if pluck != False:
                data1 = (
                    r.table(table)
                    .get_all(userid, index="user")
                    .order_by("name")
                    .pluck(pluck)
                    .run(db.conn)
                )
                data2 = (
                    r.table(table)
                    .filter(
                        lambda d: d["allowed"]["roles"] is not False
                        or d["allowed"]["groups"] is not False
                        or d["allowed"]["categories"] is not False
                        or d["allowed"]["users"] is not False
                    )
                    .order_by("name")
                    .pluck(pluck)
                    .run(db.conn)
                )
            else:
                data1 = (
                    r.table(table)
                    .get_all(userid, index="user")
                    .order_by("name")
                    .run(db.conn)
                )
                data2 = (
                    r.table(table)
                    .filter(
                        lambda d: d["allowed"]["roles"] is not False
                        or d["allowed"]["groups"] is not False
                        or d["allowed"]["categories"] is not False
                        or d["allowed"]["users"] is not False
                    )
                    .order_by("name")
                    .run(db.conn)
                )
            data = data1 + data2
            data = [i for n, i in enumerate(data) if i not in data[n + 1 :]]
            allowed_data = []
            for d in data:
                try:
                    d["username"] = (
                        r.table("users")
                        .get(d["user"])
                        .pluck("name")
                        .run(db.conn)["name"]
                    )
                except:
                    d["username"] = "X " + d["user"]
                # Who belongs this resource (table)
                if userid == d["user"]:
                    if skipOwner:
                        continue
                    else:
                        allowed_data.append(d)
                        continue

                # False doesn't check, [] means all allowed
                # Role is the master and user the least. If allowed in roles,
                #   won't check categories, groups, users
                # ~ allowed=d['allowed']
                if d["allowed"]["roles"] != False:
                    if not d["allowed"]["roles"]:  # Len != 0
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if ud["role"] in d["allowed"]["roles"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                if d["allowed"]["categories"] != False:
                    if not d["allowed"]["categories"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if ud["category"] in d["allowed"]["categories"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                if d["allowed"]["groups"] != False:
                    if not d["allowed"]["groups"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if ud["group"] in d["allowed"]["groups"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                if d["allowed"]["users"] != False:
                    if not d["allowed"]["users"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if userid in d["allowed"]["users"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
            return allowed_data

    def get_all_table_allowed_term(
        self, table, kind, field, value, userid, pluck="default"
    ):
        if pluck == "default":
            pluck = ["id", "name", "allowed", "kind", "icon", "user", "description"]
        if pluck != False:
            if "user" not in pluck:
                pluck.append("user")
            if "allowed" not in pluck:
                pluck.append("allowed")
        with app.app_context():
            ud = r.table("users").get(userid).run(db.conn)
            delete_allowed_key = False
            if pluck != False:
                data = (
                    r.table(table)
                    .get_all(kind, index="kind")
                    .filter(lambda d: d[field].match("(?i)" + value))
                    .filter(
                        lambda d: d["user"] is userid
                        or d["allowed"]["roles"] is not False
                        or d["allowed"]["groups"] is not False
                        or d["allowed"]["categories"] is not False
                        or d["allowed"]["users"] is not False
                    )
                    .order_by("name")
                    .pluck(pluck)
                    .run(db.conn)
                )
            else:
                data = (
                    r.table(table)
                    .get_all(kind, index="kind")
                    .filter(lambda d: d[field].match("(?i)" + value))
                    .filter(
                        lambda d: d["user"] is userid
                        or d["allowed"]["roles"] is not False
                        or d["allowed"]["groups"] is not False
                        or d["allowed"]["categories"] is not False
                        or d["allowed"]["users"] is not False
                    )
                    .order_by("name")
                    .run(db.conn)
                )
            allowed_data = []
            for d in data:
                # Who belongs this resource (table)
                if userid == d["user"]:
                    allowed_data.append(d)
                    continue

                # False doesn't check, [] means all allowed
                # Role is the master and user the least. If allowed in roles,
                #   won't check categories, groups, users
                # ~ allowed=d['allowed']
                if d["allowed"]["roles"] != False:
                    if not d["allowed"]["roles"]:  # Len != 0
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if ud["role"] in d["allowed"]["roles"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                if d["allowed"]["categories"] != False:
                    if not d["allowed"]["categories"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if ud["category"] in d["allowed"]["categories"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                if d["allowed"]["groups"] != False:
                    if not d["allowed"]["groups"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if ud["group"] in d["allowed"]["groups"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                if d["allowed"]["users"] != False:
                    if not d["allowed"]["users"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
                        continue
                    if userid in d["allowed"]["users"]:
                        if delete_allowed_key:
                            d.pop("allowed", None)
                        allowed_data.append(d)
            return allowed_data

    def user_relative_media_path(self, user, filename):
        with app.app_context():
            userObj = (
                r.table("users")
                .get(user)
                .pluck("id", "category", "group", "provider", "username", "uid")
                .run(db.conn)
            )
        parsed_name = self.parse_string(filename)
        if not parsed_name:
            return False
        id = str(uuid4())
        # ~ Missing check if id already exists
        return {
            "id": id,
            "name": filename,
            "user": user,
            "username": userObj["username"],
            "category": userObj["category"],
            "group": userObj["group"],
        }

    def new_tmpl_from_domain(self, from_id, form_data, user_id):
        """exceeded = quotas.check('NewTemplate',user_id)
        if exceeded != False:
            return exceeded"""

        parsed_name = self.parse_string(form_data["name"])
        template_id = "_" + user_id + "-" + parsed_name

        with app.app_context():
            # Checking if template exists:
            if r.table("domains").get(template_id).run(db.conn) != None:
                return "Template name already exists."

            # Lets construct new template_dict data
            desktop = (
                r.table("domains")
                .get(from_id)
                .without("disks_info", "history_domain", "xml_to_start")
                .run(db.conn)
            )
            user = (
                r.table("users")
                .get(user_id)
                .pluck("id", "category", "group", "provider", "username", "uid")
                .run(db.conn)
            )

        parent_disk = desktop["hardware"]["disks"][0]["file"]

        form_data["create_dict"]["hardware"]["disks"] = [
            {"extension": "qcow2", "parent": parent_disk}
        ]

        hardware = self.parse_media_info(form_data["create_dict"])["hardware"]
        hardware["not_change_cpu_section"] = (
            desktop.get("create_dict", {})
            .get("hardware", {})
            .get("not_change_cpu_section", False)
        )
        hardware["virtualization_nested"] = (
            desktop.get("create_dict", {})
            .get("hardware", {})
            .get("virtualization_nested", False)
        )

        if "roles" not in form_data["allowed"].keys():
            form_data["allowed"]["roles"] = False
        if "categories" not in form_data["allowed"].keys():
            form_data["allowed"]["categories"] = False

        create_dict = {"hardware": hardware, "origin": from_id}
        if desktop["create_dict"].get("reservables"):
            create_dict = {
                **create_dict,
                **{"reservables": desktop["create_dict"]["reservables"]},
            }

        template_dict = {
            "id": template_id,
            "name": form_data["name"],
            "description": form_data["description"],
            "kind": form_data["kind"],
            "user": user["id"],
            "username": user["username"],
            "enabled": form_data["enabled"],
            "status": "CreatingTemplate",
            "detail": None,
            "category": user["category"],
            "group": user["group"],
            "xml": desktop["xml"],  #### In desktop creation is
            "icon": desktop["icon"],
            "image": desktop["image"],
            "server": desktop["server"],
            "os": desktop["os"],
            "guest_properties": desktop["guest_properties"],
            "create_dict": create_dict,
            "hypervisors_pools": form_data["hypervisors_pools"],
            "parents": desktop["parents"] if "parents" in desktop.keys() else [],
            "allowed": form_data["allowed"],
        }

        with app.app_context():
            return self.check(
                r.table("domains")
                .get(from_id)
                .update(
                    {
                        "create_dict": {"template_dict": template_dict},
                        "status": "CreatingTemplate",
                    }
                )
                .run(db.conn),
                "replaced",
            )

    def new_domains_auto_user(self, user, auto_templates):
        with app.app_context():
            usr_dsk = (
                r.table("domains")
                .get_all(["desktop", user], index="kind_user")
                .run(db.conn)
            )
            usr_dsk_list = [d["id"] for d in usr_dsk]
        for t in auto_templates["desktops"]:
            if "_" + user + "-" + t.split("-", 2)[2] in usr_dsk_list:
                continue
            with app.app_context():
                tmpl = r.table("domains").get(t).run(db.conn)
                tmpl["create_dict"]["template"] = tmpl["id"]
                tmpl["create_dict"]["name"] = tmpl["name"]
                tmpl["create_dict"]["description"] = tmpl["description"]
                if "forced_hyp" in tmpl.keys():
                    tmpl["create_dict"]["forced_hyp"] = tmpl["forced_hyp"]
                tmpl["create_dict"]["hypervisors_pools"] = tmpl["hypervisors_pools"]

            self.new_domain_from_tmpl(user, tmpl["create_dict"])

    def new_domains_from_tmpl(self, current_user, create_dict, ignoreexisting=False):
        selected = create_dict.pop("allowed", None)
        # if current_user.role == == 'manager'
        users = []

        if current_user.role == "admin":
            if selected["roles"] is not False:
                if not selected["roles"]:
                    with app.app_context():
                        selected["roles"] = [
                            r["id"]
                            for r in list(r.table("roles").pluck("id").run(db.conn))
                        ]
                for role in selected["roles"]:
                    # Can't use get_all as has no index in database
                    with app.app_context():
                        roles = list(
                            r.table("users")
                            .filter({"role": role})
                            .pluck("id")
                            .run(db.conn)
                        )
                    users = users + [r["id"] for r in roles]
            if selected["categories"] is not False:
                if not selected["categories"]:
                    with app.app_context():
                        selected["categories"] = [
                            c["id"]
                            for c in list(
                                r.table("categories").pluck("id").run(db.conn)
                            )
                        ]
                with app.app_context():
                    categories = list(
                        r.table("users")
                        .get_all(r.args(selected["categories"]), index="category")
                        .pluck("id")
                        .run(db.conn)
                    )
                users = users + [c["id"] for c in categories]

        if selected["groups"] is not False:
            if not selected["groups"]:
                query = r.table("groups")
                if current_user.role == "manager":
                    query = query.get_all(
                        current_user.category, index="parent_category"
                    )
                with app.app_context():
                    selected["groups"] = [
                        g["id"] for g in list(query.pluck("id").run(db.conn))
                    ]
            with app.app_context():
                groups = list(
                    r.table("users")
                    .get_all(r.args(selected["groups"]), index="group")
                    .pluck("id")
                    .run(db.conn)
                )
            users = users + [g["id"] for g in groups]

        if selected["users"] is not False:
            if not selected["users"]:
                query = r.table("users")
                if current_user.role == "manager":
                    query = query.get_all(current_user.category, index="category")
                with app.app_context():
                    selected["users"] = [
                        u["id"] for u in list(query.pluck("id").run(db.conn))
                    ]
            users = users + selected["users"]

        """Remove duplicates"""
        users = list(set(users))
        with app.app_context():
            try:
                existing_desktops = list(
                    r.table("domains")
                    .get_all(r.args(users), index="user")
                    .filter({"name": create_dict["name"]})
                    .pluck("user")
                    .run(db.conn)
                )
            except:
                None
        if len(existing_desktops):
            lst_existing_desktops = [
                ed["user"].split("-")[-1] for ed in existing_desktops
            ]
            if not ignoreexisting:
                return ", ".join(lst_existing_desktops)
        if "tag" in create_dict.keys():
            create_dict["tag"] = current_user.id + "=" + create_dict["tag"]
            user_reloader(current_user.id)
        for user in users:
            self.new_domain_from_tmpl(user, create_dict)
        if len(existing_desktops):
            return ", ".join(lst_existing_desktops)
        return True

    def new_domain_from_tmpl(self, user, create_dict):
        exceeded = quotas.check("NewDesktop", user)
        if exceeded != False:
            return exceeded
        with app.app_context():
            userObj = (
                r.table("users")
                .get(user)
                .pluck("id", "category", "group", "provider", "username", "uid")
                .run(db.conn)
            )
            ephimeral_cat = (
                r.table("categories")
                .get(userObj["category"])
                .pluck("ephimeral")
                .run(db.conn)
            )
            ephimeral_group = (
                r.table("groups").get(userObj["group"]).pluck("ephimeral").run(db.conn)
            )
        ephimeral = (
            ephimeral_group if "ephimeral" in ephimeral_group.keys() else ephimeral_cat
        )

        with app.app_context():
            dom = (
                r.table("domains")
                .get(create_dict["template"])
                .without(
                    "xml",
                    "xml_to_start",
                    "history_domain",
                    "hw_stats",
                    "disks_info",
                    "progress",
                    "jumperurl",
                    "viewer",
                )
                .run(db.conn)
            )
        if "forced_hyp" not in dom.keys():
            dom["forced_hyp"] = False
        parent_disk = dom["hardware"]["disks"][0]["file"]

        qos_id = create_dict.pop("qos_id") if "qos_id" in create_dict.keys() else False
        parsed_name = self.parse_string(create_dict["name"])
        create_dict["hardware"]["disks"] = [
            {
                "extension": "qcow2",
                "parent": parent_disk,
                "qos_id": qos_id,
            }
        ]

        if len(create_dict["hardware"].get("isos", [])):
            create_dict["hardware"]["isos"] = [
                dict(iso)
                for iso in {
                    tuple(isos.items())
                    for isos in create_dict["hardware"]["isos"]
                    + dom["create_dict"]["hardware"].get("isos", [])
                }
            ]
        else:
            create_dict["hardware"]["isos"] = dom["create_dict"]["hardware"].get(
                "isos", []
            )

        if len(create_dict["hardware"].get("floppies", [])):
            create_dict["hardware"]["floppies"] = [
                dict(floppy)
                for floppy in {
                    tuple(floppies.items())
                    for floppies in create_dict["hardware"]["floppies"]
                    + dom["create_dict"]["hardware"].get("floppies", [])
                }
            ]
        else:
            create_dict["hardware"]["floppies"] = dom["create_dict"]["hardware"].get(
                "floppies", []
            )

        create_dict["hardware"]["not_change_cpu_section"] = (
            dom.get("create_dict", {})
            .get("hardware", {})
            .get("not_change_cpu_section", False)
        )
        create_dict["hardware"]["virtualization_nested"] = (
            dom.get("create_dict", {})
            .get("hardware", {})
            .get("virtualization_nested", False)
        )

        new_create_dict = {
            "hardware": create_dict["hardware"],
            "origin": create_dict["template"],
        }
        if dom["create_dict"].get("reservables"):
            new_create_dict = {
                **new_create_dict,
                **{"reservables": dom["create_dict"]["reservables"]},
            }

        new_domain = {
            "id": "_" + user + "-" + parsed_name,
            "name": create_dict["name"],
            "description": create_dict["description"],
            "tag": create_dict.get("tag", False),
            "tag_name": create_dict.get("tag_name", False),
            "tag_visible": create_dict.get("tag_visible", True),
            "jumperurl": app.adminapi.jumperurl_gencode()
            if create_dict.get("tag_visible", True)
            else False,
            "kind": "desktop",
            "user": userObj["id"],
            "username": userObj["username"],
            "status": "Creating",
            "detail": None,
            "category": userObj["category"],
            "group": userObj["group"],
            "xml": None,
            "icon": dom["icon"],
            "image": dom["image"],
            "server": dom["server"],
            "os": dom["os"],
            "guest_properties": dom["guest_properties"],
            "create_dict": new_create_dict,
            "forced_hyp": dom["forced_hyp"],
            "hypervisors_pools": create_dict["hypervisors_pools"],
            "allowed": {
                "roles": False,
                "categories": False,
                "groups": False,
                "users": False,
            },
        }
        if "ephimeral" in ephimeral.keys():
            new_domain["ephimeral"] = ephimeral["ephimeral"]
        with app.app_context():
            if r.table("domains").get(new_domain["id"]).run(db.conn) == None:
                return self.check(
                    r.table("domains").insert(new_domain).run(db.conn), "inserted"
                )
            else:
                return "Domain name already exists."

    def update_domain(self, create_dict):
        id = create_dict["id"]
        create_dict.pop("id", None)
        # ~ description=create_dict['description']
        # ~ create_dict.pop('description',None)

        if "disk_bus" in create_dict["create_dict"]["hardware"]:
            new_create_dict = (
                r.table("domains")
                .get(id)
                .pluck("create_dict", "tag", "booking_id")
                .run(db.conn)
            )
            if len(new_create_dict["create_dict"]["hardware"]["disks"]):
                new_create_dict["create_dict"]["hardware"]["disks"][0][
                    "bus"
                ] = create_dict["create_dict"]["hardware"]["disk_bus"]
                create_dict["create_dict"]["hardware"]["disks"] = new_create_dict[
                    "create_dict"
                ]["hardware"]["disks"]
            create_dict["create_dict"]["hardware"].pop("disk_bus", None)

        if "qos_id" in create_dict["create_dict"]["hardware"]:
            create_dict["create_dict"]["hardware"]["disks"][0]["qos_id"] = create_dict[
                "create_dict"
            ]["hardware"]["qos_id"]
            create_dict["create_dict"]["hardware"].pop("qos_id", None)

        create_dict["create_dict"] = self.parse_media_info(create_dict["create_dict"])

        create_dict["status"] = "Updating"

        r.table("domains").get(id).update(
            {
                "guest_properties": {
                    "viewers": r.literal(create_dict["guest_properties"]["viewers"])
                }
            }
        ).run(db.conn)

        if (
            new_create_dict["create_dict"].get("reservables")
            and create_dict["create_dict"]["reservables"]
            != new_create_dict["create_dict"]["reservables"]
        ):
            try:
                with app.app_context():
                    r.table("bookings").get_all(
                        ["desktop", id], index="item_type-id"
                    ).delete().run(db.conn)
            except:
                log.debug(traceback.format_exc())
        with app.app_context():
            return self.check(
                r.table("domains").get(id).update(create_dict).run(db.conn), "replaced"
            )
        # ~ return update_table_value('domains',id,{'create_dict':'hardware'},create_dict['hardware'])

    def parse_media_info(self, create_dict):
        medias = ["isos", "floppies", "storage"]
        for m in medias:
            if m in create_dict["hardware"]:
                newlist = []
                for item in create_dict["hardware"][m]:
                    with app.app_context():
                        newlist.append(
                            r.table("media")
                            .get(item["id"])
                            .pluck("id", "name", "description")
                            .run(db.conn)
                        )
                create_dict["hardware"][m] = newlist
        return create_dict

    def update_user_password(self, id, passwd):
        pw = Password()
        self.update_table_value(
            "users", current_user.id, "password", pw.encrypt(passwd)
        )
        return True

    """ def user_hardware_allowed(self, user_id)
        return quota.user_hardware_allowed(user_id) """

    """
    HELPERS
    """

    # ~ GENERIC
    def check(self, dict, action):
        """
        These are the actions:
        {u'skipped': 0, u'deleted': 1, u'unchanged': 0, u'errors': 0, u'replaced': 0, u'inserted': 0}
        """
        if dict[action]:
            return True
        if not dict["errors"]:
            return True
        return False

    def parse_string(self, txt, strip=True):
        import locale
        import re
        import unicodedata

        if type(txt) != str:
            txt = txt.decode("utf-8")
        if strip:
            txt = txt.strip()
        # locale.setlocale(locale.LC_ALL, 'ca_ES')
        prog = re.compile("[-_àèìòùáéíóúñçÀÈÌÒÙÁÉÍÓÚÑÇ .a-zA-Z0-9]+$")
        if not prog.match(txt):
            return False
        else:
            # ~ Replace accents
            txt = "".join(
                (
                    c
                    for c in unicodedata.normalize("NFD", txt)
                    if unicodedata.category(c) != "Mn"
                )
            )
            return txt.replace(" ", "_")

    """ def toCamel(self,phrase):
        split = re.split('_| ',phrase)
        return self.parse_string(split[0]).lower() + self.parse_string(''.join(x.capitalize() for x in split[1:])) """

    def toCamel(self, phrase):
        split = re.split("_| ", phrase)
        if len(split) > 1:
            return self.parse_string(split[0]).lower() + self.parse_string(
                "".join(x.capitalize() for x in split[1:] if x != "")
            )
        else:
            return self.parse_string(split[0]).lower()

    def human_size(self, size_bytes):
        """
        format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
        Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
        e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
        """
        if size_bytes == 1:
            # because I really hate unnecessary plurals
            return "1 byte"

        suffixes_table = [
            ("bytes", 0),
            ("KB", 0),
            ("MB", 0),
            ("GB", 2),
            ("TB", 2),
            ("PB", 2),
        ]

        num = float(size_bytes)
        for suffix, precision in suffixes_table:
            if num < 1024.0:
                break
            num /= 1024.0

        if precision == 0:
            formatted_size = "%d" % num
        else:
            formatted_size = str(round(num, ndigits=precision))

        return "%s %s" % (formatted_size, suffix)

    def flatten_dict(self, d):
        def items():
            for key, value in list(d.items()):
                if isinstance(value, dict):
                    for subkey, subvalue in list(self.flatten_dict(value).items()):
                        yield key + "-" + subkey, subvalue
                else:
                    yield key, value

        return dict(items())

    def unflatten_dict(self, dictionary):
        resultDict = dict()
        for key, value in dictionary.items():
            parts = key.split("-")
            d = resultDict
            for part in parts[:-1]:
                if part not in d:
                    d[part] = dict()
                d = d[part]
            d[parts[-1]] = value
        return resultDict
