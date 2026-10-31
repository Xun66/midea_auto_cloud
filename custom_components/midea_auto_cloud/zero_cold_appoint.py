"""Entities for the T0xE3 定时零冷水 schedule (see device_mapping/_zero_cold_appoint.py).

Per slot: a text entity ("22:30-01:00 daily", empty = delete) and an on/off switch. Both read
and write the same appoint_one..four attribute, so edits made in the 美居 app show up here on
the next poll and vice versa.
"""

from __future__ import annotations

from homeassistant.exceptions import ServiceValidationError

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
from .switch import MideaSwitchEntity
from .text import MideaTextEntity


class _ZeroColdAppointMixin:
    """Shared slot access for the text and switch entities."""

    @property
    def _slot_attr(self) -> str:
        return self._config.get("attribute", self._entity_key)

    @property
    def _slot_index(self) -> int:
        return SLOT_ATTRS.index(self._slot_attr)

    def _slot(self) -> list[int] | None:
        return coerce_slot(self._get_nested_value(self._slot_attr))

    def _all_slots(self) -> list[list[int] | None]:
        return [coerce_slot(self._get_nested_value(attr)) for attr in SLOT_ATTRS]

    async def _async_write_slot(self, slot: list[int]) -> None:
        if slot_enabled(slot):
            if (other := find_conflict(self._slot_index, slot, self._all_slots())) is not None:
                raise ServiceValidationError(
                    f"Overlaps with zero-cold schedule {other + 1}; change or turn that one off first"
                )
        await self.async_set_attribute(self._slot_attr, to_wire(slot))

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
            return
        current = self._slot() or EMPTY_SLOT
        # The app keeps the slot's temperature byte and saves edits as enabled (255).
        await self._async_write_slot([255, current[1], *parsed])


class ZeroColdAppointSwitch(_ZeroColdAppointMixin, MideaSwitchEntity):
    """Enable/disable an existing slot."""

    @property
    def is_on(self) -> bool:
        return slot_enabled(self._slot())

    async def async_turn_on(self, **kwargs) -> None:
        slot = self._slot()
        if not slot_exists(slot):
            raise ServiceValidationError("This zero-cold schedule slot is empty; set its time first")
        # app (checkNoWeekAppoint): a slot without weekdays becomes every day
        await self._async_write_slot([255, *slot[1:6], slot[6] or 255])

    async def async_turn_off(self, **kwargs) -> None:
        slot = self._slot()
        if slot_exists(slot):
            await self._async_write_slot([0, *slot[1:]])
