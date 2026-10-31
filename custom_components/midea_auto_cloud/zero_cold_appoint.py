"""Entities for the T0xE3 定时零冷水 schedule and AI 零冷水 (see device_mapping/_zero_cold_appoint.py).

Per slot: a text entity ("22:30-01:00 daily", empty = delete) and an on/off switch. Both read
and write the same appoint_one..four attribute, so edits made in the 美居 app show up here on
the next poll and vice versa.

AI 零冷水 lives in the hot-water cloud (/cfhrs/e3/...), not in the lua status. The switch and the
mode select mirror the app's aiColdWaterPage: turning AI on/off and switching between the custom
schedule and the AI-learned schedule rewrite the 4 device slots exactly like the app does.
"""

from __future__ import annotations

import datetime
import json
import logging
import time
from secrets import token_hex

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .device_mapping._zero_cold_appoint import (
    DAY_NAMES,
    EMPTY_SLOT,
    SLOT_ATTRS,
    AppointError,
    coerce_slot,
    find_conflict,
    format_slot,
    parse_text,
    slot_enabled,
    slot_exists,
    to_wire,
)
from .select import MideaSelectEntity
from .switch import MideaSwitchEntity
from .text import MideaTextEntity

_LOGGER = logging.getLogger(__name__)

E3_API = "/cfhrs/e3/v1/api"
E3_API_KEY = "/cfhrs/e3/v2/api"  # setTimerZeroCold

ATTR_AI = "ai_zero_cold"
ATTR_AI_MODE = "ai_zero_cold_mode"
ATTR_AI_STUDY_DAYS = "ai_zero_cold_study_days"
ATTR_AI_LEARNED = "ai_zero_cold_learned"
AI_MODES = ("custom", "ai")  # cloud mode 0 = 自定义定时, 1 = AI 定时


async def hotwater_api(cloud, endpoint: str, msg: str, params: dict):
    """POST to the 美的热水 cloud API; returns `result` on retCode 0, else None.

    These endpoints answer {"retCode", "desc", "result"} instead of the usual {"code", "data"},
    so they cannot go through MeijuCloud._api_request.
    """
    data = {
        "reqId": token_hex(16),
        "stamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        "msg": msg,
        "params": params,
    }
    random = str(int(time.time()))
    body = json.dumps(data)
    header = {
        "content-type": "application/json; charset=utf-8",
        "secretVersion": "1",
        "sign": cloud._security.sign(body, random),
        "random": random,
    }
    if cloud._access_token is not None:
        header["accesstoken"] = cloud._access_token
    try:
        r = await cloud._session.post(
            cloud._api_url + endpoint, headers=header, data=body, timeout=30, proxy=cloud._proxy
        )
        response = json.loads(await r.read())
    except Exception as e:  # noqa: BLE001
        _LOGGER.warning("Hot-water cloud %s %s failed: %s", endpoint, msg, e)
        return None
    if str(response.get("retCode")) != "0":
        _LOGGER.warning("Hot-water cloud %s %s: %s", endpoint, msg, response.get("desc") or response)
        return None
    return response.get("result")


async def async_poll_ai_zero_cold(cloud, device) -> None:
    """Coordinator hook: AI 零冷水 state (switch/mode/study days) and the learned windows."""
    params = {"applianceId": str(device.device_id), "sn8": device.sn8, "action": "get"}
    if (state := await hotwater_api(cloud, E3_API, "aiZeroColdWaterSwitchPlus", params)) is not None:
        device.attributes[ATTR_AI] = "on" if state.get("switch") == 1 else "off"
        device.attributes[ATTR_AI_MODE] = AI_MODES[1] if state.get("mode") == 1 else AI_MODES[0]
        device.attributes[ATTR_AI_STUDY_DAYS] = state.get("studyDays")
    learned = await hotwater_api(
        cloud, E3_API, "aiZeroColdWaterAiSettingPlus", {"applianceId": str(device.device_id)}
    )
    if isinstance(learned, list):
        device.attributes[ATTR_AI_LEARNED] = [f"{w['startTime']}-{w['endTime']}" for w in learned]


class _ZeroColdMixin:
    """Device slot and hot-water cloud access shared by all zero-cold entities."""

    @property
    def _cloud(self):
        return self.coordinator._cloud

    @property
    def _base_params(self) -> dict:
        return {"applianceId": str(self._device_id)}

    def _slot_at(self, index: int) -> list[int] | None:
        return coerce_slot(self._get_nested_value(SLOT_ATTRS[index]))

    def _all_slots(self) -> list[list[int] | None]:
        return [self._slot_at(i) for i in range(len(SLOT_ATTRS))]

    def _enabled_count(self) -> int:
        return sum(slot_enabled(s) for s in self._all_slots())

    async def _api(self, msg: str, params: dict, endpoint: str = E3_API, *, required: bool = True):
        result = await hotwater_api(self._cloud, endpoint, msg, {**self._base_params, **params})
        if result is None and required:
            raise HomeAssistantError(f"Midea hot-water cloud request {msg} failed")
        return result

    async def _write_slot_at(self, index: int, slot: list[int]) -> None:
        await self.async_set_attribute(SLOT_ATTRS[index], to_wire(slot))

    async def _close_all_slots(self) -> None:
        """app closeAppointList: switch every enabled slot off, keep its times."""
        for index, slot in enumerate(self._all_slots()):
            if slot and slot[0] != 0:
                await self._write_slot_at(index, [0, *slot[1:]])

    async def _refresh_ai_state(self) -> None:
        await async_poll_ai_zero_cold(self._cloud, self.coordinator.device)
        self.coordinator.async_set_updated_data(self.coordinator._snapshot())


class _ZeroColdAppointMixin(_ZeroColdMixin):
    """One schedule slot; mirrors the app's deviceWaterAppointPage side effects."""

    @property
    def _slot_attr(self) -> str:
        return self._config.get("attribute", self._entity_key)

    @property
    def _slot_index(self) -> int:
        return SLOT_ATTRS.index(self._slot_attr)

    def _slot(self) -> list[int] | None:
        return self._slot_at(self._slot_index)

    async def _async_write_slot(self, slot: list[int]) -> None:
        if slot_enabled(slot):
            if (other := find_conflict(self._slot_index, slot, self._all_slots())) is not None:
                raise ServiceValidationError(
                    f"Overlaps with zero-cold schedule {other + 1}; change or turn that one off first"
                )
        await self.async_set_attribute(self._slot_attr, to_wire(slot))

    async def _after_slot_change(self, close_old_ai: bool) -> None:
        """app: report the timer state and turn off the old AI 智能启动 (V2) when it conflicts."""
        enabled = self._enabled_count()
        await self._api(
            "setTimerZeroCold", {"action": "set", "sw": 1 if enabled else 0}, E3_API_KEY, required=False
        )
        if close_old_ai:
            v2 = {"sn8": self._sn8}
            state = await self._api("aiZeroColdWaterPlusSwitchV2", {**v2, "action": "get"}, required=False)
            if state and state.get("switch") == 1:
                await self._api(
                    "aiZeroColdWaterPlusSwitchV2", {**v2, "action": "set", "switch": 0}, required=False
                )

    @property
    def extra_state_attributes(self) -> dict:
        slot = self._slot()
        if not slot_exists(slot):
            return {}
        return {
            "enabled": slot_enabled(slot),
            "temperature": slot[1],
            "days": [name for i, name in enumerate(DAY_NAMES) if (slot[6] or 0x7F) >> i & 1],
            "repeat": slot[6] in (0, 255) or bool(slot[6] & 0x80),
            "raw": slot,
        }


class ZeroColdAppointText(_ZeroColdAppointMixin, MideaTextEntity):
    """Slot time range and days; setting an empty value deletes the slot (like the app)."""

    def __init__(self, coordinator, device, manufacturer, rationale, entity_key, config):
        super().__init__(coordinator, device, manufacturer, rationale, entity_key, config)
        self._attr_native_min = 0
        self._attr_native_max = 64
        self._attr_pattern = None

    @property
    def native_value(self) -> str | None:
        return format_slot(self._slot())

    async def async_set_value(self, value: str) -> None:
        try:
            parsed = parse_text(value)
        except AppointError as err:
            raise ServiceValidationError(str(err)) from err
        if parsed is None:
            await self.async_set_attribute(self._slot_attr, to_wire(EMPTY_SLOT))
        else:
            current = self._slot() or EMPTY_SLOT
            # The app keeps the slot's temperature byte and saves edits as enabled (255).
            await self._async_write_slot([255, current[1], *parsed])
        # app getConflictAiWithDiy after returning from the edit page
        await self._after_slot_change(close_old_ai=self._enabled_count() <= 1)


class ZeroColdAppointSwitch(_ZeroColdAppointMixin, MideaSwitchEntity):
    """Enable/disable an existing slot."""

    @property
    def is_on(self) -> bool:
        return slot_enabled(self._slot())

    async def async_turn_on(self, **kwargs) -> None:
        slot = self._slot()
        if not slot_exists(slot):
            raise ServiceValidationError("This zero-cold schedule slot is empty; set its time first")
        before = self._enabled_count()
        # app (checkNoWeekAppoint): a slot without weekdays becomes every day
        await self._async_write_slot([255, *slot[1:6], slot[6] or 255])
        # app appointControl: closes the old AI 智能启动 when going from 0 to 1 enabled slot
        await self._after_slot_change(close_old_ai=before == 0 and self._enabled_count() == 1)

    async def async_turn_off(self, **kwargs) -> None:
        slot = self._slot()
        if slot_exists(slot):
            await self._async_write_slot([0, *slot[1:]])
            await self._after_slot_change(close_old_ai=False)


class _ZeroColdAiMixin(_ZeroColdMixin):
    """AI 零冷水 actions, following the app's aiColdWaterPage."""

    @property
    def _ai_mode(self) -> int:
        return 1 if self._get_nested_value(ATTR_AI_MODE) == AI_MODES[1] else 0

    @property
    def _study_days(self) -> int:
        return int(self._get_nested_value(ATTR_AI_STUDY_DAYS) or 0)

    async def _set_ai(self, switch: int, mode: int) -> None:
        await self._api("aiZeroColdWaterSwitchPlus", {"sn8": self._sn8, "action": "set", "switch": switch, "mode": mode})

    async def _timed_tasks(self, action: str, task: list) -> list:
        result = await self._api(
            "aiTimedZeroColdWaterPlus", {"platform": self._sn8, "action": action, "task": task}
        )
        return result if isinstance(result, list) else []

    def _current_settings(self) -> list[str]:
        # the app saves the slots as the heater reports them (enable 1/0, not the 255 it writes)
        return [
            to_wire([1 if slot[0] else 0, *slot[1:]]) if slot else to_wire(EMPTY_SLOT)
            for slot in self._all_slots()
        ]

    async def _backup_slots(self) -> None:
        """app sendDeviceAppointToServer / pushDeviceAppoint: save the 4 device slots on the server."""
        saved = await self._timed_tasks("getAll", [])
        settings = self._current_settings()
        if 0 < len(saved) < 4:
            await self._timed_tasks(
                "delete", [{"taskId": t["taskId"], "setting": settings[i]} for i, t in enumerate(saved)]
            )
            saved = []
        if saved:
            tasks = [{"taskId": saved[i]["taskId"], "setting": settings[i]} for i in range(4)]
            await self._timed_tasks("update", tasks)
        else:
            await self._timed_tasks("add", [{"taskId": str(i + 1), "setting": s} for i, s in enumerate(settings)])

    async def _restore_slots(self) -> None:
        """app setSavedAppointToDevice: write the server copy back to the slots, then mode 0."""
        for index, task in enumerate((await self._timed_tasks("getAll", []))[: len(SLOT_ATTRS)]):
            slot = coerce_slot(task.get("setting"))
            if slot:
                await self._write_slot_at(index, [255 if slot[0] else 0, *slot[1:]])
        await self._set_ai(1, 0)

    async def _write_learned_slots(self) -> None:
        """app getAiAppoint(true) + openAppointList: learned windows → slots at 42 °C, every day."""
        learned = await self._api("aiZeroColdWaterAiSettingPlus", {}) or []
        for index, window in enumerate(learned[: len(SLOT_ATTRS)]):
            sh, sm = (int(v) for v in window["startTime"].split(":"))
            eh, em = (int(v) for v in window["endTime"].split(":"))
            await self._write_slot_at(index, [255, 42, sh, sm, eh, em, 255])

    async def _ai_turn_on(self) -> None:
        mode = self._ai_mode
        await self._set_ai(1, mode)
        if self._study_days == 0 and mode == 1:
            await self._write_learned_slots()
        else:
            await self._restore_slots()

    async def _ai_turn_off(self) -> None:
        await self._set_ai(0, self._ai_mode)
        if self._ai_mode == 0:
            await self._backup_slots()
        await self._close_all_slots()

    async def _ai_select_mode(self, mode: int) -> None:
        if mode == self._ai_mode:
            return
        if self._get_nested_value(ATTR_AI) != "on":
            raise ServiceValidationError("Turn AI zero-cold on first")
        if mode == 1:
            if self._study_days:
                raise ServiceValidationError(
                    f"AI zero-cold is still learning ({self._study_days} days left)"
                )
            await self._backup_slots()  # app pushDeviceAppoint
            await self._close_all_slots()
            await self._write_learned_slots()
            await self._set_ai(1, 1)
        else:
            await self._restore_slots()  # app showSelf

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "mode": self._get_nested_value(ATTR_AI_MODE),
            "study_days": self._get_nested_value(ATTR_AI_STUDY_DAYS),
            "learned_windows": self._get_nested_value(ATTR_AI_LEARNED),
        }


class ZeroColdAiSwitch(_ZeroColdAiMixin, MideaSwitchEntity):
    """AI 零冷水 on/off."""

    @property
    def is_on(self) -> bool:
        return self._get_nested_value(ATTR_AI) == "on"

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self._ai_turn_on()
        finally:
            await self._refresh_ai_state()

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self._ai_turn_off()
        finally:
            await self._refresh_ai_state()


class ZeroColdAiModeSelect(_ZeroColdAiMixin, MideaSelectEntity):
    """AI 零冷水 schedule source: custom (自定义定时) or ai (AI 定时)."""

    @property
    def options(self) -> list[str]:
        return list(AI_MODES)

    @property
    def current_option(self) -> str | None:
        return self._get_nested_value(ATTR_AI_MODE)

    async def async_select_option(self, option: str) -> None:
        try:
            await self._ai_select_mode(AI_MODES.index(option))
        finally:
            await self._refresh_ai_state()


ENTITY_CLASSES = {
    "slot_text": ZeroColdAppointText,
    "slot_switch": ZeroColdAppointSwitch,
    "ai_switch": ZeroColdAiSwitch,
    "ai_mode": ZeroColdAiModeSelect,
}
