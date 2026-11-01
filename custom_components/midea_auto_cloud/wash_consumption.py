"""Washer water/power statistics from the 美居 app's 能耗统计 API (/xyj/washConsumption).

Upstream polls /xyj/h5/api/WashSessions/getWaterPower, which returns null for some washers
(e.g. T0xDB project 13633). The app plugin (energy-efficiency-statistics page) uses this API:
- getDayConsumption: the 7 days ending at queryTime, dayWater (L) / dayPower (kWh);
- getMonthConsumption: the 6 months ending at queryTime's month, monthWater / monthPower.
It needs the numeric userId of the logged-in account (homegroup member list), not the uid.
"""

from __future__ import annotations

import datetime
import json
import logging
import time
from secrets import token_hex

_LOGGER = logging.getLogger(__name__)

WASH_API = "/xyj/washConsumption/energy/v1/consumption/get{}Consumption"


async def _wash_api(cloud, kind: str, params: dict):
    """POST to the washConsumption API; returns `result` on errorCode 0, else None."""
    data = {
        "stamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
        "reqId": token_hex(16),
        **params,
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
            cloud._api_url + WASH_API.format(kind), headers=header, data=body, timeout=30,
            proxy=cloud._proxy,
        )
        response = json.loads(await r.read())
    except Exception as e:  # noqa: BLE001
        _LOGGER.debug("Wash consumption %s failed: %s", kind, e)
        return None
    if str(response.get("errorCode")) != "0":
        _LOGGER.debug("Wash consumption %s: %s %s", kind, response.get("msg"), response.get("result"))
        return None
    return response.get("result")


async def _user_id_candidates(cloud) -> list[str]:
    """Numeric userIds from the home member lists; the account's own (mobile match) first."""
    if cached := getattr(cloud, "_wash_user_ids", None):
        return cached
    homes = await cloud._api_request(endpoint="/v1/homegroup/list/get", data={}) or {}
    mine, others = [], []
    for home in homes.get("homeList") or []:
        members = await cloud._api_request(
            endpoint="/v1/homegroup/member/get", data={"homegroupId": home.get("homegroupId")}
        ) or {}
        for member in members.get("list") or []:
            if not (user_id := str(member.get("userId") or "")):
                continue
            target = mine if member.get("mobile") == cloud._account else others
            if user_id not in mine + others:
                target.append(user_id)
    cloud._wash_user_ids = mine + others
    return cloud._wash_user_ids


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


HISTORY_WINDOWS = 20  # walk back at most 10 years of 6-month windows


def _month_entry(m: dict) -> tuple[float, float]:
    return _num(m.get("monthWater")), _num(m.get("monthPower"))


async def _load_history(cloud, params: dict, oldest: str) -> dict | None:
    """Months before `oldest` ("YYYY-MM"), walking back until a window is all zero.

    None when a call fails, so a partial history never lowers the lifetime totals.
    """
    history: dict[str, tuple[float, float]] = {}
    for _ in range(HISTORY_WINDOWS):
        before = datetime.date(int(oldest[:4]), int(oldest[5:7]), 1) - datetime.timedelta(days=1)
        window = await _wash_api(cloud, "Month", {**params, "queryTime": before.isoformat()})
        if window is None:
            return None
        entries = {m["month"]: _month_entry(m) for m in window if m.get("month")}
        history.update(entries)
        if not entries or not any(w or p for w, p in entries.values()):
            return history
        oldest = min(entries)
    return history


async def async_poll_wash_consumption(cloud, device, now: datetime.datetime) -> bool:
    """Set cloud_{water,power}_{today,month,year,total}; False when the API gives nothing.

    The *_total sensors are lifetime sums over every month the app has (for the Energy dashboard).
    Past months are fetched once and cached on the device; each poll refreshes the last 6 months.
    """
    base = {
        "applianceId": str(device.device_id),
        "category": f"{device.device_type:02X}",
        "project_no": device.attributes.get("project_no") or device.subtype,
        "queryTime": now.strftime("%Y-%m-%d"),
    }
    window = None
    for user_id in await _user_id_candidates(cloud):
        if (window := await _wash_api(cloud, "Month", {"userId": user_id, **base})) is not None:
            if cloud._wash_user_ids[0] != user_id:  # remember the one that has access
                cloud._wash_user_ids.remove(user_id)
                cloud._wash_user_ids.insert(0, user_id)
            break
    if window is None:
        return False
    params = {"userId": user_id, **base}

    months: dict[str, tuple[float, float]] = getattr(device, "_wash_months", None) or {}
    recent = {m["month"]: _month_entry(m) for m in window if m.get("month")}
    if not getattr(device, "_wash_history_loaded", False):
        history = await _load_history(cloud, params, min(recent)) if recent else {}
        if history is not None:
            months.update(history)
            device._wash_history_loaded = True
    months.update(recent)
    device._wash_months = months

    this_month = months.get(now.strftime("%Y-%m"), (0.0, 0.0))
    year = [v for k, v in months.items() if k.startswith(f"{now.year}-")]
    days = await _wash_api(cloud, "Day", params) or []
    today = next((d for d in days if d.get("day") == base["queryTime"]), {})

    attrs = device._attributes
    attrs["cloud_water_today"] = round(_num(today.get("dayWater")), 2)
    attrs["cloud_power_today"] = round(_num(today.get("dayPower")), 3)
    attrs["cloud_water_month"] = round(this_month[0], 2)
    attrs["cloud_power_month"] = round(this_month[1], 3)
    if getattr(device, "_wash_history_loaded", False):  # complete history only: a drop would read as a meter reset
        attrs["cloud_water_year"] = round(sum(w for w, _ in year), 2)
        attrs["cloud_power_year"] = round(sum(p for _, p in year), 3)
        attrs["cloud_water_total"] = round(sum(w for w, _ in months.values()), 2)
        attrs["cloud_power_total"] = round(sum(p for _, p in months.values()), 3)
    return True
