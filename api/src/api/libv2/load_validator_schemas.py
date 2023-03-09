

import os
import uuid
from base64 import b64encode
from secrets import token_bytes

import yaml
from cerberus import Validator, schema_registry

from api import app

from .._common.storage_pool import DEFAULT_STORAGE_POOL_ID
from .helpers import _parse_string


class IsardValidator(Validator):
    def _normalize_default_setter_storagepools(self):
        return DEFAULT_STORAGE_POOL_ID

    def _normalize_default_setter_genuuid(self, document):
        return str(uuid.uuid4())

    def _normalize_default_setter_mediaicon(self, document):
        if document["kind"] == "iso":
            return _parse_string("fa-circle-o")
        else:
            return _parse_string("fa-floppy-o")

    def _check_with_validate_vlan(self, field, value):
        """
        Value should be a string with a numeric value >= 1 and <= 4094
        """
        if not (value.isnumeric() and 1 <= int(value) <= 4094):
            self._error(
                field, "Value should be a string with a numeric value >= 1 and <= 4094"
            )

    def _check_with_validate_vlan_range(self, field, value):
        """
        Value should be a string with a numeric range like 55-33 and range should be >= 1 and <= 4094
        """
        range = value.split("-")
        if len(range) != 2 or not range[0].isnumeric() or not range[1].isnumeric():
            self._error(
                field, 'Value should be a string with a numeric range like "55-33"'
            )
        elif int(range[0]) > int(range[1]):
            self._error(
                field, "Last range number cannot be less than first range number"
            )
        elif not 1 <= int(range[0]) <= 4094 or not 1 <= int(range[1]) <= 4094:
            self._error(field, "Range limits should be >= 1 and <= 4094")

    def _normalize_default_setter_gensecret(self, document):
        return b64encode(token_bytes(32)).decode()


def load_validators(purge_unknown=True):
    snippets_path = os.path.join(app.root_path, "schemas/snippets")
    for snippets_filename in os.listdir(snippets_path):
        with open(os.path.join(snippets_path, snippets_filename)) as file:
            snippet_schema_yml = file.read()
            snippet_schema = yaml.load(snippet_schema_yml, Loader=yaml.FullLoader)
            schema_registry.add(snippets_filename.split(".")[0], snippet_schema)

    validators = {}
    schema_path = os.path.join(app.root_path, "schemas")
    for schema_filename in os.listdir(schema_path):
        try:
            with open(os.path.join(schema_path, schema_filename)) as file:
                schema_yml = file.read()
                schema = yaml.load(schema_yml, Loader=yaml.FullLoader)
                validators[schema_filename.split(".")[0]] = IsardValidator(
                    schema, purge_unknown=purge_unknown
                )
                validators[schema_filename.split(".")[0] + ".schema"] = schema
        except IsADirectoryError:
            None
    return validators
