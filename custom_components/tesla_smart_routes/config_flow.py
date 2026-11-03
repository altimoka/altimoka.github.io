from __future__ import annotations

import asyncio
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryFlow
from homeassistant.core import callback
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.selector import (
    EntitySelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .helpers import build_maps_url, waypoint_place_url
from .request_validation import RouteValidationError, normalize_proxy_settings
from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_LABEL,
    CONF_NAME,
    CONF_PLACE_ID,
    CONF_PROXY_URL,
    CONF_PROXY_CERT_SHA256,
    CONF_VIN,
    CONF_VIN_ENTITY,
    CONF_VIN_SOURCE,
    CONF_WAYPOINTS,
    DEFAULT_PROXY_URL,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_SCOPES,
    OAUTH2_TOKEN,
    SUBENTRY_TYPE_ROUTE,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Optional(CONF_PROXY_URL, default=DEFAULT_PROXY_URL): str,
        vol.Required(CONF_PROXY_CERT_SHA256): str,
    }
)


class TeslaLocalOAuth2Implementation(config_entry_oauth2_flow.LocalOAuth2Implementation):
    def __init__(self, hass, client_id: str, client_secret: str) -> None:
        super().__init__(
            hass=hass,
            domain=DOMAIN,
            client_id=client_id,
            client_secret=client_secret,
            authorize_url=OAUTH2_AUTHORIZE,
            token_url=OAUTH2_TOKEN,
        )

    @property
    def redirect_uri(self) -> str:
        return "https://my.home-assistant.io/redirect/oauth"

    @property
    def extra_authorize_data(self) -> dict:
        return {"scope": OAUTH2_SCOPES}


ROUTE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): str})

VIN_SOURCE_OPTIONS = [
    {"value": "manual", "label": "Manual VIN"},
    {"value": "entity", "label": "From HA entity"},
]

VIN_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VIN_SOURCE, default="manual"): SelectSelector(
            SelectSelectorConfig(options=VIN_SOURCE_OPTIONS, mode=SelectSelectorMode.LIST)
        ),
    }
)

VIN_MANUAL_SCHEMA = vol.Schema({vol.Required(CONF_VIN): str})

VIN_ENTITY_SCHEMA = vol.Schema({vol.Required(CONF_VIN_ENTITY): EntitySelector()})

# Create flow: add waypoints one by one with action choice
WAYPOINT_ACTION_OPTIONS = [
    {"value": "add_another", "label": "Add another waypoint"},
    {"value": "done", "label": "Done — create route"},
]

WAYPOINT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LABEL, default=""): str,
        vol.Optional(CONF_PLACE_ID, default=""): str,
        vol.Required("action", default="add_another"): SelectSelector(
            SelectSelectorConfig(
                options=WAYPOINT_ACTION_OPTIONS,
                mode=SelectSelectorMode.LIST,
            )
        ),
    }
)

# Manage flow: single waypoint entry (no action selector)
SINGLE_WAYPOINT_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LABEL, default=""): str,
        vol.Optional(CONF_PLACE_ID, default=""): str,
    }
)

# Manage flow: action options (built dynamically based on whether waypoints exist)
MANAGE_ACTION_BASE = [
    {"value": "add_new", "label": "Add new waypoint"},
    {"value": "done", "label": "Done"},
]

MANAGE_ACTION_FULL = [
    {"value": "add_new", "label": "Add new waypoint"},
    {"value": "edit_or_delete", "label": "Edit or delete a waypoint"},
    {"value": "done", "label": "Done"},
]

WAYPOINT_EDIT_DELETE_OPTIONS = [
    {"value": "edit", "label": "Edit this waypoint"},
    {"value": "delete", "label": "Delete this waypoint"},
]


class TeslaNavConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN):
    VERSION = 1
    DOMAIN = DOMAIN

    _proxy_url: str | None = None
    _proxy_certificate_sha256: str | None = None

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(__name__)

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            try:
                self._proxy_url, self._proxy_certificate_sha256 = normalize_proxy_settings(
                    user_input[CONF_PROXY_URL], user_input[CONF_PROXY_CERT_SHA256]
                )
            except RouteValidationError:
                return self.async_show_form(
                    step_id="user", data_schema=USER_SCHEMA,
                    errors={"base": "invalid_proxy_settings"},
                )
            self.flow_impl = TeslaLocalOAuth2Implementation(
                self.hass,
                user_input[CONF_CLIENT_ID],
                user_input[CONF_CLIENT_SECRET],
            )
            return await self.async_step_auth()

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA)

    async def async_oauth_create_entry(self, data: dict) -> dict:
        data[CONF_PROXY_URL] = self._proxy_url
        data[CONF_PROXY_CERT_SHA256] = self._proxy_certificate_sha256
        data[CONF_CLIENT_ID] = self.flow_impl.client_id
        data[CONF_CLIENT_SECRET] = self.flow_impl.client_secret
        return self.async_create_entry(title="Tesla Nav", data=data)

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_ROUTE: TeslaNavRouteSubentryFlow}


class TeslaNavRouteSubentryFlow(ConfigSubentryFlow):
    def __init__(self) -> None:
        self._route_data: dict = {}
        self._waypoints: list[dict] = []
        self._is_reconfigure: bool = False
        self._initial_maps_url: str | None = None
        self._editing_index: int | None = None

    # ------------------------------------------------------------------ create

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._route_data = user_input
            self._waypoints = []
            return await self.async_step_vin_source()
        return self.async_show_form(step_id="user", data_schema=ROUTE_SCHEMA)

    async def async_step_vin_source(self, user_input=None):
        if user_input is not None:
            self._route_data[CONF_VIN_SOURCE] = user_input[CONF_VIN_SOURCE]
            if user_input[CONF_VIN_SOURCE] == "manual":
                return await self.async_step_vin_manual()
            return await self.async_step_vin_entity()
        suggested = {CONF_VIN_SOURCE: self._route_data.get(CONF_VIN_SOURCE, "manual")}
        return self.async_show_form(
            step_id="vin_source",
            data_schema=self.add_suggested_values_to_schema(VIN_SOURCE_SCHEMA, suggested),
        )

    async def async_step_vin_manual(self, user_input=None):
        if user_input is not None:
            self._route_data[CONF_VIN] = user_input[CONF_VIN].strip()
            self._route_data.pop(CONF_VIN_ENTITY, None)
            if self._is_reconfigure:
                return self._save_vehicle()
            return await self.async_step_add_waypoint()
        suggested = {CONF_VIN: self._route_data.get(CONF_VIN, "")}
        return self.async_show_form(
            step_id="vin_manual",
            data_schema=self.add_suggested_values_to_schema(VIN_MANUAL_SCHEMA, suggested),
        )

    async def async_step_vin_entity(self, user_input=None):
        if user_input is not None:
            self._route_data[CONF_VIN_ENTITY] = user_input[CONF_VIN_ENTITY]
            self._route_data.pop(CONF_VIN, None)
            if self._is_reconfigure:
                return self._save_vehicle()
            return await self.async_step_add_waypoint()
        current = self._route_data.get(CONF_VIN_ENTITY)
        schema = (
            self.add_suggested_values_to_schema(VIN_ENTITY_SCHEMA, {CONF_VIN_ENTITY: current})
            if current
            else VIN_ENTITY_SCHEMA
        )
        return self.async_show_form(step_id="vin_entity", data_schema=schema)

    def _save_vehicle(self):
        subentry = self._get_reconfigure_subentry()
        vin_keys = {CONF_VIN, CONF_VIN_ENTITY, CONF_VIN_SOURCE}
        new_data = {k: v for k, v in subentry.data.items() if k not in vin_keys}
        new_data[CONF_VIN_SOURCE] = self._route_data[CONF_VIN_SOURCE]
        if self._route_data[CONF_VIN_SOURCE] == "manual":
            new_data[CONF_VIN] = self._route_data[CONF_VIN]
        else:
            new_data[CONF_VIN_ENTITY] = self._route_data[CONF_VIN_ENTITY]
        return self.async_update_reload_and_abort(
            self._get_entry(), subentry, title=subentry.title, data=new_data,
        )

    def _finish_waypoints(self):
        from .button import SIGNAL_NEW_ROUTE
        title = self._route_data[CONF_NAME]
        data = {**self._route_data, CONF_WAYPOINTS: self._waypoints}
        if self._is_reconfigure:
            entry = self._get_entry()
            subentry = self._get_reconfigure_subentry()
            return self.async_update_reload_and_abort(entry, subentry, title=title, data=data)

        entry = self._get_entry()
        existing_ids = set(entry.subentries.keys())

        async def _notify():
            await asyncio.sleep(0)
            for sub_id, sub in entry.subentries.items():
                if sub_id not in existing_ids:
                    async_dispatcher_send(
                        self.hass,
                        f"{SIGNAL_NEW_ROUTE}_{entry.entry_id}",
                        sub_id,
                    )
                    break

        self.hass.async_create_task(_notify())
        return self.async_create_entry(title=title, data=data)

    async def async_step_add_waypoint(self, user_input=None):
        errors = {}
        if user_input is not None:
            label = user_input.get(CONF_LABEL, "").strip()
            place_id = user_input.get(CONF_PLACE_ID, "").strip()
            action = user_input.get("action", "done")

            if not label and not place_id:
                return self._finish_waypoints()
            elif label and place_id:
                self._waypoints.append({"label": label, "place_id": place_id})
                if action == "add_another":
                    return await self.async_step_add_waypoint()
                return self._finish_waypoints()
            else:
                errors["base"] = "waypoint_incomplete"

        added = "\n".join(f"• {w['label']} ({w['place_id']})" for w in self._waypoints)
        maps_url_line = f"\n[View current route]({self._initial_maps_url})" if self._initial_maps_url else ""
        return self.async_show_form(
            step_id="add_waypoint",
            data_schema=WAYPOINT_SCHEMA,
            description_placeholders={
                "waypoints": added or "None yet.",
                "maps_url": maps_url_line,
            },
            errors=errors,
        )

    # --------------------------------------------------------------- reconfigure

    async def async_step_reconfigure(self, user_input=None):
        self._is_reconfigure = True
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["edit_route", "edit_vehicle", "edit_waypoints"],
        )

    async def async_step_edit_route(self, user_input=None):
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            return self.async_update_reload_and_abort(
                self._get_entry(),
                subentry,
                title=user_input[CONF_NAME],
                data={**subentry.data, **user_input},
            )
        return self.async_show_form(
            step_id="edit_route",
            data_schema=self.add_suggested_values_to_schema(ROUTE_SCHEMA, subentry.data),
        )

    async def async_step_edit_vehicle(self, user_input=None):
        subentry = self._get_reconfigure_subentry()
        self._route_data = {
            CONF_NAME: subentry.data[CONF_NAME],
            CONF_VIN_SOURCE: subentry.data.get(CONF_VIN_SOURCE, "manual"),
        }
        if CONF_VIN in subentry.data:
            self._route_data[CONF_VIN] = subentry.data[CONF_VIN]
        if CONF_VIN_ENTITY in subentry.data:
            self._route_data[CONF_VIN_ENTITY] = subentry.data[CONF_VIN_ENTITY]
        return await self.async_step_vin_source()

    async def async_step_edit_waypoints(self, user_input=None):
        subentry = self._get_reconfigure_subentry()
        self._route_data = {
            CONF_NAME: subentry.data[CONF_NAME],
            CONF_VIN_SOURCE: subentry.data.get(CONF_VIN_SOURCE, "manual"),
        }
        if CONF_VIN in subentry.data:
            self._route_data[CONF_VIN] = subentry.data[CONF_VIN]
        if CONF_VIN_ENTITY in subentry.data:
            self._route_data[CONF_VIN_ENTITY] = subentry.data[CONF_VIN_ENTITY]
        self._initial_maps_url = build_maps_url(subentry.data.get(CONF_WAYPOINTS, []))
        self._waypoints = list(subentry.data.get(CONF_WAYPOINTS, []))
        return await self.async_step_manage_waypoints()

    async def async_step_manage_waypoints(self, user_input=None):
        has_waypoints = bool(self._waypoints)

        if user_input is not None:
            action = user_input.get("waypoint_action")
            if action == "done":
                return self._finish_waypoints()
            if action == "add_new":
                return await self.async_step_add_single_waypoint()
            if action == "edit_or_delete":
                return await self.async_step_select_waypoint()

        action_options = MANAGE_ACTION_FULL if has_waypoints else MANAGE_ACTION_BASE
        route_link = f"\n\n[View full route on Google Maps]({self._initial_maps_url})" if self._initial_maps_url else ""
        added = "\n".join(f"• [{w['label']}]({waypoint_place_url(w)})" for w in self._waypoints)
        return self.async_show_form(
            step_id="manage_waypoints",
            data_schema=vol.Schema({
                vol.Required("waypoint_action"): SelectSelector(
                    SelectSelectorConfig(options=action_options, mode=SelectSelectorMode.LIST)
                ),
            }),
            description_placeholders={
                "waypoints": added or "None.",
                "maps_url": route_link,
            },
        )

    async def async_step_select_waypoint(self, user_input=None):
        if user_input is not None:
            self._editing_index = int(user_input["waypoint_index"])
            return await self.async_step_manage_waypoint_action()

        wp_options = [
            {"value": str(i), "label": w["label"]}
            for i, w in enumerate(self._waypoints)
        ]
        return self.async_show_form(
            step_id="select_waypoint",
            data_schema=vol.Schema({
                vol.Required("waypoint_index"): SelectSelector(
                    SelectSelectorConfig(options=wp_options, mode=SelectSelectorMode.LIST)
                ),
            }),
        )

    async def async_step_manage_waypoint_action(self, user_input=None):
        waypoint = self._waypoints[self._editing_index]
        if user_input is not None:
            action = user_input.get("waypoint_edit_action")
            if action == "delete":
                self._waypoints.pop(self._editing_index)
                self._editing_index = None
                return await self.async_step_manage_waypoints()
            return await self.async_step_edit_waypoint()

        return self.async_show_form(
            step_id="manage_waypoint_action",
            data_schema=vol.Schema({
                vol.Required("waypoint_edit_action", default="edit"): SelectSelector(
                    SelectSelectorConfig(
                        options=WAYPOINT_EDIT_DELETE_OPTIONS,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
            }),
            description_placeholders={"label": waypoint["label"]},
        )

    async def async_step_add_single_waypoint(self, user_input=None):
        errors = {}
        if user_input is not None:
            label = user_input.get(CONF_LABEL, "").strip()
            place_id = user_input.get(CONF_PLACE_ID, "").strip()
            if label and place_id:
                self._waypoints.append({"label": label, "place_id": place_id})
                return await self.async_step_manage_waypoints()
            if not label and not place_id:
                return await self.async_step_manage_waypoints()
            errors["base"] = "waypoint_incomplete"

        return self.async_show_form(
            step_id="add_single_waypoint",
            data_schema=SINGLE_WAYPOINT_SCHEMA,
            errors=errors,
        )

    async def async_step_edit_waypoint(self, user_input=None):
        errors = {}
        if user_input is not None:
            label = user_input.get(CONF_LABEL, "").strip()
            place_id = user_input.get(CONF_PLACE_ID, "").strip()
            if label and place_id:
                self._waypoints[self._editing_index] = {"label": label, "place_id": place_id}
                self._editing_index = None
                return await self.async_step_manage_waypoints()
            errors["base"] = "waypoint_incomplete"

        current = self._waypoints[self._editing_index]
        return self.async_show_form(
            step_id="edit_waypoint",
            data_schema=self.add_suggested_values_to_schema(SINGLE_WAYPOINT_SCHEMA, current),
            errors=errors,
        )
