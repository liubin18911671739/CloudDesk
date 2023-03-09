#!/usr/bin/env python
# coding=utf-8


from rethinkdb import RethinkDB

from api import app

r = RethinkDB()
import logging as log

from ..flask_rethink import RDB

db = RDB(app)
db.init_app(app)

import traceback
import uuid
from datetime import datetime, timedelta
from pprint import pformat

import portion as P
import pytz

from ..._common.api_exceptions import Error
from ..api_scheduler import Scheduler
from ..helpers import _check, _get_reservables
from .api_reservables import Reservables
from .api_reservables_planner_compute import (
    booking_provisioning,
    convert_plans_to_portions,
    get_same_plans_for_booking,
    get_subitems_planning,
    join_existing_plan_after_new_plan_start,
    join_existing_plan_before_new_plan_end,
    payload_priority,
)


class ReservablesPlanner:
    def __init__(self):
        self.round_minutes = 5
        self.scheduler = Scheduler()
        self.reservables = Reservables()

    def ceil_dt(self, dt):
        return dt + (datetime.min.replace(tzinfo=pytz.UTC) - dt) % timedelta(
            minutes=self.round_minutes
        )

    ## Reservables View endpoints
    def list_item_plans(self, item_id, start=None, end=None):
        if not start:
            start = datetime.now(pytz.utc)
        else:
            start = datetime.strptime(start, "%Y-%m-%dT%H:%M%z").astimezone(pytz.UTC)
        if not end:
            end = start
        else:
            end = datetime.strptime(end, "%Y-%m-%dT%H:%M%z").astimezone(pytz.UTC)

        ## An item/subitem planning should not overlap
        return list(
            r.table("resource_planner")
            .get_all(item_id, index="item_id")
            .filter(r.row["start"] <= end)
            .filter(r.row["end"] >= start)
            .run(db.conn)
        )

    def list_subitem_plans(
        self, item_id, subitem_id, start=None, end=None, getUsername=None
    ):
        if not start:
            start = datetime.now(pytz.utc).strftime("%Y-%m-%dT%H:%M%z")
        query = r.table("resource_planner").get_all(
            [item_id, subitem_id], index="item-subitem"
        )
        if end:
            query = query.filter(
                r.row["start"].during(
                    datetime.strptime(start, "%Y-%m-%dT%H:%M%z").astimezone(pytz.UTC),
                    datetime.strptime(end, "%Y-%m-%dT%H:%M%z").astimezone(pytz.UTC),
                )
            )
        else:
            query = query.filter(
                lambda plan: plan["start"]
                > datetime.strptime(start, "%Y-%m-%dT%H:%M%z").astimezone(pytz.UTC)
            )
        if getUsername:
            query = query.merge(
                lambda p: {"user_name": r.table("users").get(p["user_id"])["username"]}
            )
        with app.app_context():
            data = list(query.run(db.conn))
        ## An item/subitem planning should not overlap
        return data

    def add_plan(
        self,
        payload,
        data,
    ):
        # Round start/end dates to self.round_minutes
        try:
            start = self.ceil_dt(
                datetime.strptime(data["start"], "%Y-%m-%dT%H:%M%z")
            ).astimezone(pytz.UTC)
        except ValueError:
            log.debug(traceback.format_exc())
            raise Error(
                "bad_request",
                "Start date invalid.",
                description_code="invalid_start_date",
            )
        try:
            end = self.ceil_dt(
                datetime.strptime(data["end"], "%Y-%m-%dT%H:%M%z")
            ).astimezone(pytz.UTC) - timedelta(0, 1)
        except ValueError:
            raise Error(
                "bad_request", "End date invalid.", description_code="invalid_end_date"
            )

        # Plan data structure
        try:
            plan = {
                "id": str(uuid.uuid4()),
                "item_type": data["item_type"],
                "item_id": data["item_id"],
                "subitem_id": data["subitem_id"],
                "units": self.reservables.get_subitem_units(
                    data["item_type"], data["item_id"], data["subitem_id"]
                ),
                "start": start,
                "end": end,
                "user_id": payload["user_id"],
                "event_type": "available",
            }
        except:
            raise Error(
                "bad_request",
                "New plan body data incorrect",
                traceback.format_exc(),
                description_code="incorrect_new_plan_body_data",
            )
        ## Get item behaviours
        item_can_overlap = self.reservables.planning_item_can_overlap(
            data["item_type"], data["item_id"]
        )
        subitem_can_overlap = self.reservables.planning_subitem_can_overlap(
            data["item_type"], data["item_id"], data["subitem_id"]
        )
        subitem_join_before = self.reservables.planning_subitem_join_before(
            data["item_type"], data["item_id"], data["subitem_id"]
        )
        subitem_join_after = self.reservables.planning_subitem_join_after(
            data["item_type"], data["item_id"], data["subitem_id"]
        )
        subitem_shedule = self.reservables.planning_schedule_subitem(
            data["item_type"], data["item_id"], data["subitem_id"]
        )
        ## Execute item behaviours
        if not item_can_overlap:
            self.check_plan_item_id_overlapped(plan)
        if not subitem_can_overlap:
            self.check_plan_subitem_id_overlapped(plan)

        replanned = False
        if subitem_join_before:
            joined_plan = join_existing_plan_after_new_plan_start(plan)
            if joined_plan:
                print(
                    "Existing plan "
                    + joined_plan["id"]
                    + " moved start time to new plan "
                    + plan["id"]
                )
                if subitem_shedule:
                    self.reschedule_existing_plan_start(plan, joined_plan)
                replanned = joined_plan["id"]

        if subitem_join_after:
            joined_plan = join_existing_plan_before_new_plan_end(plan)
            if joined_plan:
                print(
                    "Existing plan "
                    + joined_plan["id"]
                    + " moved end time to new plan "
                    + plan["id"]
                )
                if subitem_shedule:
                    self.reschedule_existing_plan_end(plan, joined_plan)
                replanned = joined_plan["id"]

        if replanned:
            # It has been already updated at scheduler and db
            return replanned
        else:
            if subitem_shedule:
                self.new_subitem_schedule(plan)
            inserted = _check(
                r.table("resource_planner").insert(plan).run(db.conn), "inserted"
            )
            if not inserted:
                raise Error(
                    "internal_error",
                    "Could not insert plan in database",
                    description_code="unable_to_insert",
                )
            return plan["id"]

    def update_plan(self, payload, plan_id, start, end):
        with app.app_context():
            bookings_in_actual_plan = list(
                r.table("bookings")
                .filter(
                    r.row["plans"].contains(lambda plan: plan["plan_id"] == plan_id)
                )
                .filter(
                    r.row["start"]
                    <= datetime.strptime(start, "%Y-%m-%dT%H:%M%z").astimezone(pytz.UTC)
                )
                .filter(
                    r.row["end"]
                    >= datetime.strptime(end, "%Y-%m-%dT%H:%M%z").astimezone(pytz.UTC)
                )
                .run(db.conn)
            )
        if len(bookings_in_actual_plan):
            with app.app_context():
                bookings_failing_in_new_range = list(
                    r.table("bookings")
                    .filter(
                        r.row["plans"].contains(lambda plan: plan["plan_id"] == plan_id)
                    )
                    .filter(
                        r.row["start"]
                        <= datetime.strptime(start, "%Y-%m-%dT%H:%M%z").astimezone(
                            pytz.UTC
                        )
                    )
                    .filter(
                        r.row["end"]
                        >= datetime.strptime(end, "%Y-%m-%dT%H:%M%z").astimezone(
                            pytz.UTC
                        )
                    )
                    .run(db.conn)
                )
            if len(bookings_in_actual_plan) != len(bookings_failing_in_new_range):
                # The difference will imply to remove those bookings
                bookings2remove = [
                    b["id"]
                    for b in bookings_in_actual_plan
                    if b not in bookings_failing_in_new_range
                ]
                with app.app_context():
                    r.table("bookings").get_all(
                        r.args[bookings2remove], index="id"
                    ).delete().run(db.conn)
        with app.app_context():
            plan = r.table("resource_planner").get(plan_id).run(db.conn)
        self.add_plan(payload, plan)

    def delete_plan(self, plan_id):
        ## Remove Scheduler
        with app.app_context():
            if not _check(
                r.table("resource_planner").get(plan_id).delete().run(db.conn),
                "deleted",
            ):
                Error("internal_server", "Could not remove plan from database.")
            self.scheduler.remove_scheduler_startswith_id(plan_id)

            ## NEEDS to get plan["start"] and plan["end"] to get only those bookings??
            result = (
                r.table("bookings")
                .filter(
                    r.row["plans"].contains(lambda plan: plan["plan_id"] == plan_id)
                )
                .delete(return_changes=True)
                .run(db.conn)
            )
        if result.get("changes"):
            booking_ids = [b["old_val"]["id"] for b in result["changes"]]
            for booking_id in booking_ids:
                self.scheduler.remove_scheduler_startswith_id(booking_id)

    def get_plan_bookings(self, plan_id):
        with app.app_context():
            return (
                r.table("bookings")
                .filter(
                    r.row["plans"].contains(lambda plan: plan["plan_id"] == plan_id)
                )
                .without("reservables", "plans")
                .run(db.conn)
            )

    ## Bookings functions
    #######################################################

    def get_item_availability(
        self,
        payload,
        item_type,
        item_id,
        fromDate,
        toDate,
        returnUnavailable=False,
        subitems=None,
    ):
        if not subitems:
            subitems, units, item_name = _get_reservables(item_type, item_id)
        else:
            units = 1
        priority = payload_priority(payload, subitems)
        # {'priority': {'NVIDIA-A40-1Q': 45}, 'forbid_time': 24, 'max_time': 2, 'max_items': 30}
        planning = booking_provisioning(
            payload, item_type, item_id, subitems, units, priority, fromDate, toDate
        )

        format_planning = []
        for plan in planning:
            if not returnUnavailable and plan["event_type"] == "unavailable":
                continue
            format_planning.append(
                {
                    "start": plan["start"].strftime("%Y-%m-%dT%H:%M%z"),
                    "end": plan["end"].strftime("%Y-%m-%dT%H:%M%z"),
                    "event_type": plan["event_type"],
                    "units": plan["units"],
                }
            )
        return format_planning

    def existing_booking_update_fits(self, payload, booking):
        return (
            False  # The booking_provisioning should send booking item_type and item_id
        )
        plans = booking_provisioning(
            payload,
            booking["item_type"],
            booking["item_id"],
            booking["reservables"],
            booking["units"],
            payload_priority(payload, booking["reservables"]),
            booking["start"],
            booking["end"],
            skip_booking_id=booking["id"],
        )
        portion_plans = convert_plans_to_portions(plans)
        new_booking = P.closed(booking["start"], booking["end"])
        fits = [p for p in portion_plans if p.contains(new_booking)]
        if len(fits) == 1:
            return True
        if not len(fits):
            return False
        log.error("The booking fits in more than one plan!?!?")
        return False

    def new_booking_plans(self, payload, booking):
        subitems = booking["reservables"]
        units = booking["units"]
        priority = payload_priority(payload, booking["reservables"])
        start = booking["start"]
        end = booking["end"]

        plans = {}
        for k, v in subitems.items():
            if not v or not len(v):
                continue
            # Get overlapped and keep non overlapped
            for subitem in v:
                all_plans = get_subitems_planning([subitem])
                plans[subitem] = get_same_plans_for_booking(
                    all_plans, subitem, priority["priority"][subitem], start, end, units
                )
                log.debug(
                    "Plans for " + k + "/" + subitem + ": " + str(len(plans[subitem]))
                )
        if len(plans.keys()) == 0:
            return []
        elif len(plans.keys()) == 1:
            return plans
        else:
            log.error(
                "Trying to book desktop with multiple reservables"
                + str(list(plans.keys()))
                + ". Not implemented"
            )
            return []

    ##### Scheduling
    def reschedule_existing_plan_start(self, new_plan, existing_plan):
        # Card will be set to default profile between plans
        # If event is added, at start time an scheduler is added (15/5/2/1 minutes before start as kwargs/plan_id index key)
        # existing_plan start is now new_plan start (moved before)
        # we need to reeschedule plan_id to new start time
        self.scheduler.bookings_reschedule_item_id(
            existing_plan["item_id"], existing_plan["start"]
        )

    def reschedule_existing_plan_end(self, new_plan, existing_plan):
        # Card will be set to default profile between plans
        # If event is added, at start time an scheduler is added (15/5/2/1 minutes before start as kwargs/plan_id index key)
        # existing_plan end is now new_plan end (moved after)
        # Remove existing default profile scheduler if exists at end for existing plan
        self.scheduler.bookings_remove_scheduler_item_id(existing_plan["item_id"])
        # If there is no plan just after new end, schedule default
        with app.app_context():
            joined_plan_end = list(
                (
                    r.table("resource_planner")
                    .get_all(new_plan["item_id"], index="item_id")
                    .filter({"subitem_id": new_plan["subitem_id"]})
                    .filter(r.row["end"] == existing_plan["end"])
                ).run(db.conn)
            )
        if not len(joined_plan_end):
            self.scheduler.bookings_schedule_subitem(
                new_plan["id"],
                new_plan["item_type"],
                new_plan["item_id"],
                self.reservables.get_default_subitem(
                    new_plan["item_type"], new_plan["item_id"]
                ),
                new_plan["end"],
            )

    def new_subitem_schedule(self, plan):
        self.scheduler.bookings_schedule_subitem(
            plan["id"],
            plan["item_type"],
            plan["item_id"],
            plan["subitem_id"],
            plan["start"],
        )

    ###### Plan & booking checks
    def check_plan_item_id_overlapped(self, plan):
        # We can't overlap in gpu, but we can merge existing plan with new plan if they have the same subitem_id (profile)
        # We will only join if:
        #   - new plan ends just when another plan with same profile starts
        #   . new plan starts just after another plan with same profile ends
        # So, the case where they both overlaps but they have the same subitem_id will be taken as an overlap conflict here now.
        with app.app_context():
            overlaps_start = list(
                (
                    r.table("resource_planner")
                    .get_all(plan["item_id"], index="item_id")
                    .filter(
                        r.row["start"].during(
                            plan["start"],
                            plan["end"],
                        )
                    )
                    .run(db.conn)
                )
            )
            overlaps_end = list(
                (
                    r.table("resource_planner")
                    .get_all(plan["item_id"], index="item_id")
                    .filter(
                        r.row["end"].during(
                            plan["start"],
                            plan["end"],
                        )
                    )
                    .run(db.conn)
                )
            )
            overlaps_completely = list(
                (
                    r.table("resource_planner")
                    .get_all(plan["item_id"], index="item_id")
                    .filter(
                        (r.row["start"] <= plan["start"])
                        & (r.row["end"] >= plan["end"])
                    )
                    .run(db.conn)
                )
            )
        if len(overlaps_start):
            overlaps_start = overlaps_start[0]
            raise Error(
                "conflict",
                "The current item planning for "
                + plan["item_id"]
                + " / "
                + plan["subitem_id"]
                + " ["
                + plan["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + plan["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "] overlaps starting time with "
                + overlaps_start["item_id"]
                + " / "
                + overlaps_start["subitem_id"]
                + " plan "
                + overlaps_start["id"]
                + ": ["
                + overlaps_start["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + overlaps_start["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "]",
            )
        if len(overlaps_end):
            overlaps_end = overlaps_end[0]
            raise Error(
                "conflict",
                "The current item planning for "
                + plan["item_id"]
                + " / "
                + plan["subitem_id"]
                + " ["
                + plan["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + plan["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "] overlaps end time with "
                + overlaps_end["item_id"]
                + " / "
                + overlaps_end["subitem_id"]
                + " plan "
                + overlaps_end["id"]
                + ": ["
                + overlaps_end["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + overlaps_end["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "]",
            )
        if len(overlaps_completely):
            overlaps_completely = overlaps_completely[0]
            raise Error(
                "conflict",
                "The current item planning for "
                + plan["item_id"]
                + " / "
                + plan["subitem_id"]
                + " ["
                + plan["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + plan["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "] overlaps completely with "
                + overlaps_completely["item_id"]
                + " / "
                + overlaps_completely["subitem_id"]
                + " plan "
                + overlaps_completely["id"]
                + ": ["
                + overlaps_completely["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + overlaps_completely["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "]",
            )

    def check_plan_subitem_id_overlapped(self, plan):
        # We can't overlap in gpu, but we can merge existing plan with new plan if they have the same subitem_id (profile)
        # We will only join if:
        #   - new plan ends just when another plan with same profile starts
        #   . new plan starts just after another plan with same profile ends
        # So, the case where they both overlaps but they have the same subitem_id will be taken as an overlap conflict here now.
        with app.app_context():
            overlaps_start = list(
                (
                    r.table("resource_planner")
                    .get_all(
                        [plan["item_type"], plan["item_id"], plan["subitem_id"]],
                        index="type-item-subitem",
                    )
                    .filter(
                        r.row["start"].during(
                            plan["start"],
                            plan["end"],
                        )
                    )
                    .run(db.conn)
                )
            )
            overlaps_end = list(
                (
                    r.table("resource_planner")
                    .get_all(
                        [plan["item_type"], plan["item_id"], plan["subitem_id"]],
                        index="type-item-subitem",
                    )
                    .filter(
                        r.row["end"].during(
                            plan["start"],
                            plan["end"],
                        )
                    )
                    .run(db.conn)
                )
            )
            overlaps_completely = list(
                (
                    r.table("resource_planner")
                    .get_all(
                        [plan["item_type"], plan["item_id"], plan["subitem_id"]],
                        index="type-item-subitem",
                    )
                    .filter(
                        (r.row["start"] <= plan["start"])
                        & (r.row["end"] >= plan["end"])
                    )
                    .run(db.conn)
                )
            )
        if len(overlaps_start):
            overlaps_start = overlaps_start[0]
            raise Error(
                "conflict",
                "The current subitem planning for "
                + plan["item_id"]
                + " / "
                + plan["subitem_id"]
                + " ["
                + plan["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + plan["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "] overlaps starting time with "
                + overlaps_start["item_id"]
                + " / "
                + overlaps_start["subitem_id"]
                + " plan "
                + overlaps_start["id"]
                + ": ["
                + overlaps_start["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + overlaps_start["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "]",
            )
        if len(overlaps_end):
            overlaps_end = overlaps_end[0]
            raise Error(
                "conflict",
                "The current subitem planning for "
                + plan["item_id"]
                + " / "
                + plan["subitem_id"]
                + " ["
                + plan["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + plan["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "] overlaps end time with "
                + overlaps_end["item_id"]
                + " / "
                + overlaps_end["subitem_id"]
                + " plan "
                + overlaps_end["id"]
                + ": ["
                + overlaps_end["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + overlaps_end["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "]",
            )
        if len(overlaps_completely):
            overlaps_completely = overlaps_completely[0]
            raise Error(
                "conflict",
                "The current subitem planning for "
                + plan["item_id"]
                + " / "
                + plan["subitem_id"]
                + " ["
                + plan["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + plan["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "] overlaps completely with "
                + overlaps_completely["item_id"]
                + " / "
                + overlaps_completely["subitem_id"]
                + " plan "
                + overlaps_completely["id"]
                + ": ["
                + overlaps_completely["start"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "/"
                + overlaps_completely["end"].strftime("%Y-%m-%dT%H:%M:%S%z")
                + "]",
            )

    def is_any_plan_item_id_overlapped(self):
        conflicts = {}
        with app.app_context():
            plans = r.table("resource_planner").run(db.conn)
            for plan in plans:
                if not conflicts.get(plan["item_id"]):
                    conflicts[plan["item_id"]] = {"start": [], "end": []}
                start = list(
                    (
                        r.table("resource_planner")
                        .get_all(plan["item_id"], index="item_id")
                        .filter(lambda iplan: r.not_(iplan["id"] == plan["id"]))
                        .filter(
                            r.row["start"].during(
                                plan["start"],
                                plan["end"],
                            )
                        )
                        .run(db.conn)
                    )
                )
                end = list(
                    (
                        r.table("resource_planner")
                        .get_all(plan["item_id"], index="item_id")
                        .filter(
                            r.row["end"].during(
                                plan["start"],
                                plan["end"],
                            )
                        )
                        .run(db.conn)
                    )
                )
                if len(start):
                    log.debug("------------------- START CONFLICTS")
                    log.debug(pformat(plan))
                    log.debug(pformat(start))
                if len(end):
                    log.debug("------------------- END CONFLICTS")
                    log.debug(pformat(plan))
                    log.debug(pformat(end))

        return conflicts
