

import json

from api.libv2.deployments import api_deployments
from api.libv2.validators import _validate_item
from flask import request

from api import app

from ..._common.api_exceptions import Error
from ..decorators import (
    allowedTemplateId,
    checkDuplicate,
    is_not_user,
    ownsDeploymentId,
)


@app.route("/api/v3/deployment/<deployment_id>", methods=["GET"])
@is_not_user
def api_v3_deployment(payload, deployment_id):
    ownsDeploymentId(payload, deployment_id)
    deployment = api_deployments.get(deployment_id=deployment_id, desktops=True)
    return json.dumps(deployment), 200, {"Content-Type": "application/json"}


@app.route("/api/v3/deployments", methods=["GET"])
@is_not_user
def api_v3_deployments(payload):
    deployments = api_deployments.lists(payload["user_id"])
    return json.dumps(deployments), 200, {"Content-Type": "application/json"}


@app.route("/api/v3/deployments", methods=["POST"])
@is_not_user
def api_v3_deployments_new(payload):
    try:
        data = request.get_json(force=True)
    except:
        raise Error(
            "bad_request", "Could not decode body data", description_code="bad_request"
        )

    data = _validate_item("deployment", data)
    allowedTemplateId(payload, data["template_id"])
    checkDuplicate("deployments", data["name"], user=payload["user_id"])

    api_deployments.new(
        payload,
        data["template_id"],
        data["name"],
        data["description"],
        data["desktop_name"],
        data["allowed"],
        data,
        visible=data["visible"],
        deployment_id=data["id"],
    )
    return json.dumps({"id": data["id"]}), 200, {"Content-Type": "application/json"}


@app.route("/api/v3/deployments/<deployment_id>", methods=["DELETE"])
@is_not_user
def api_v3_deployments_delete(payload, deployment_id):
    ownsDeploymentId(payload, deployment_id)
    api_deployments.checkDesktopsStarted(deployment_id)
    api_deployments.delete(deployment_id)
    return json.dumps({}), 200, {"Content-Type": "application/json"}


@app.route("/api/v3/deployments/<deployment_id>", methods=["PUT"])
@is_not_user
def api_v3_deployments_recreate(payload, deployment_id):
    ownsDeploymentId(payload, deployment_id)
    api_deployments.recreate(payload, deployment_id)
    return json.dumps({}), 200, {"Content-Type": "application/json"}


@app.route("/api/v3/deployments/start/<deployment_id>", methods=["PUT"])
@is_not_user
def api_v3_deployments_start(payload, deployment_id):
    ownsDeploymentId(payload, deployment_id)
    api_deployments.start(deployment_id)
    return json.dumps({}), 200, {"Content-Type": "application/json"}


@app.route("/api/v3/deployments/stop/<deployment_id>", methods=["PUT"])
@is_not_user
def api_v3_deployments_stop(payload, deployment_id):
    ownsDeploymentId(payload, deployment_id)
    api_deployments.stop(deployment_id)
    return json.dumps({}), 200, {"Content-Type": "application/json"}


@app.route("/api/v3/deployments/visible/<deployment_id>", methods=["PUT"])
@is_not_user
def api_v3_deployments_viewer(payload, deployment_id):
    ownsDeploymentId(payload, deployment_id)
    data = request.get_json()
    api_deployments.visible(deployment_id, data.get("stop_started_domains"))

    return json.dumps({}), 200, {"Content-Type": "application/json"}


@app.route("/api/v3/deployments/directviewer_csv/<deployment_id>", methods=["GET"])
@is_not_user
def api_v3_deployments_directviewer_csv(payload, deployment_id):
    ownsDeploymentId(payload, deployment_id)
    reset_url = request.args.get("reset")
    if reset_url:
        api_deployments.jumper_url_reset(deployment_id)
    return (
        json.dumps(api_deployments.direct_viewer_csv(deployment_id)),
        200,
        {"Content-Type": "text/csv"},
    )
