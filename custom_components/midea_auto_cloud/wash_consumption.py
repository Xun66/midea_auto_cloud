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


async def async_poll_wash_consumption(cloud, device, now: datetime.datetime) -> bool:
    """Set cloud_{water,power}_{today,month,year}; False when the API gives nothing."""
    base = {
        "applianceId": str(device.device_id),
        "category": f"{device.device_type:02X}",
        "project_no": device.attributes.get("project_no") or device.subtype,
        "queryTime": now.strftime("%Y-%m-%d"),
    }
    months = None
    for user_id in await _user_id_candidates(cloud):
        if (months := await _wash_api(cloud, "Month", {"userId": user_id, **base})) is not None:
            if cloud._wash_user_ids[0] != user_id:  # remember the one that has access
                cloud._wash_user_ids.remove(user_id)
                cloud._wash_user_ids.insert(0, user_id)
            break
    if months is None:
        return False
    params = {"userId": user_id, **base}

    if now.month > 6:  # the month list covers 6 months; fetch January..June separately
        months += await _wash_api(cloud, "Month", {**params, "queryTime": f"{now.year}-06-30"}) or []
    year = {m.get("month"): m for m in months if str(m.get("month", "")).startswith(f"{now.year}-")}
    this_month = year.get(now.strftime("%Y-%m")) or {}
    days = await _wash_api(cloud, "Day", params) or []
    today = next((d for d in days if d.get("day") == base["queryTime"]), {})

    attrs = device._attributes
    attrs["cloud_water_today"] = round(_num(today.get("dayWater")), 2)
    attrs["cloud_power_today"] = round(_num(today.get("dayPower")), 3)
    attrs["cloud_water_month"] = round(_num(this_month.get("monthWater")), 2)
    attrs["cloud_power_month"] = round(_num(this_month.get("monthPower")), 3)
    attrs["cloud_water_year"] = round(sum(_num(m.get("monthWater")) for m in year.values()), 2)
    attrs["cloud_power_year"] = round(sum(_num(m.get("monthPower")) for m in year.values()), 3)
    return True
