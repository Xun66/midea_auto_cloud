"""T0xE3 定时零冷水 (device-side zero-cold-water schedule): 4 slots stored in the heater.

Read with lua query {"query_type": "predict"}, which returns appoint_one..appoint_four as
[enable, temp, start_h, start_m, end_h, end_m, week]. Write with lua control
{"appoint_one": "255,42,22,30,1,0,255"} (same as the 美居 app plugin, deviceWaterAppoint*).

- enable: app writes 255 (on) / 0 (off); the heater reports 1 when on.
- week: bit0..bit6 = Sun..Sat, bit7 = repeat weekly (0 = run once). 255 = every day;
  0 is treated as every day by the app.
- A slot exists when any start/end field is non-zero; deleting writes 0,0,0,0,0,0,255.

Pure Python (no Home Assistant imports) so it can be unit-tested standalone.
"""

from __future__ import annotations

import json
import re

SLOT_ATTRS = ("appoint_one", "appoint_two", "appoint_three", "appoint_four")
PREDICT_QUERY = {"query_type": "predict"}
EMPTY_SLOT = [0, 0, 0, 0, 0, 0, 255]
MIN_MINUTES = 3  # app: 定时零冷水的时长不能少于3分钟

# sn8s whose app plugin lists "deviceWaterAppoint" (T0xE3 plugin 202608181445, cloudHomePage.js)
APPOINT_SN8 = (
    "5110000N", "5110001M", "5110001S", "5110001T", "5110001U", "5110001X", "5110001Y", "51100020",
    "51100021", "51100027", "5110002D", "5110002G", "5110002L", "5110002N", "5110002T", "511000E1",
    "511000L8", "511000L9", "511000T1", "511000VC", "511000WZ", "511000Y7", "511000Y9", "51100GT9",
    "51100GTS", "51100HB7", "51100HL9", "51100HP7", "51100HT2", "51100HT3", "51100HT5", "51100HT7",
    "51100HTD", "51100HTG", "51100HTN", "51100JD5", "51100JM9", "51100JX7", "51100L10", "51100LS5",
    "51100NT1", "51100NT3", "51100RD3", "51100RT5", "51100RX6", "51100RX7", "51100RX9", "51100TD7",
    "51100TX7", "51100UV8", "51100Y8S", "51101610", "51101631", "51101642", "51101693", "51101699",
    "51101700", "51101701", "51101704", "51101705", "51101706", "51101707", "51101708", "51101709",
    "5110170A", "5110170B", "5110170C", "5110170D", "51101711", "51101712", "51101713", "51101714",
    "51101717", "5110171F", "5110171G", "5110171J", "5110171K", "5110171L", "5110171W", "5110171X",
    "5110171Y", "51101721", "51101722", "51101723", "51101725", "5110172G", "5110172H", "5110172S",
    "5110172T", "5110172U", "5110172V", "5110172W", "5110172X", "5110172Y", "5110172Z", "51101730",
    "51101733", "5110173H", "5110173M", "5110173N", "5110174T", "51101750", "51101752", "51101850",
    "51101857", "51101858", "5110185F", "5110185G", "5110185J", "5110185Q", "51101860", "51101868",
    "5110186B", "5110186D", "5110186E", "5110186J", "51101874", "51101876", "51101877", "5110187C",
    "5110187D", "5110187F", "5110187H", "5110187Q", "5110187Z", "51101882", "51101883", "51101885",
    "51101887", "5110188N", "51101891", "51101892", "51101898", "51101899", "5110189A", "5110189D",
    "511018A0", "511018A4", "511018A5", "511018A9", "511018AC", "511018AF", "511018AH", "511018AJ",
    "511018AQ", "511018AT", "511018B2", "511018BD", "511018BE", "511018BF", "511018BN", "511018BQ",
    "511018C3", "511018CD", "511018CE", "511018CF", "511018CG", "511018CH", "511018CJ", "511018CL",
    "511018CN", "511018D0", "511018D2", "511018D3", "511018D4", "511018DB", "511018DJ", "511018E1",
    "511018E6", "511018E7", "511018EG", "511018ET", "511018F6", "511018F9", "511018GW", "511018GZ",
    "511018H0", "511018H1", "511018H2", "511018H3", "511018H5", "511018H6", "511018HG", "511018HH",
    "511018HJ", "511018J0", "511018K1", "511018M3", "511018P5", "511018R6", "511018ZB", "511018ZC",
    "511018ZD", "511018ZH", "511018ZL", "511018ZN", "511018ZR", "511018ZV", "511018ZW", "511018ZY",
    "51101901", "51101903", "51101906", "51101909", "5110190C", "5110190F", "5110190H", "5110190N",
    "5110190Q", "5110190W", "5110190Z", "51101910", "5110191E", "5110191F", "5110191G", "5110191H",
    "5110191J", "5110191L", "51101922", "51101924", "51101926", "51101927", "5110192A", "5110192B",
    "51101LS5", "5110HTB5", "5110HTL7", "5110HTL8", "5110HTQ6", "5110HTS3", "51111030",
)

DAY_NAMES = ("sun", "mon", "tue", "wed", "thu", "fri", "sat")  # bit index = app weekday (0 = Sunday)
_DAY_ALIASES = {
    **{d: i for i, d in enumerate(DAY_NAMES)},
    **{d: i for i, d in enumerate(
        ("sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"))},
    **{d: i for i, d in enumerate(("周日", "周一", "周二", "周三", "周四", "周五", "周六"))},
}
_ALL_DAYS = 0x7F
_WEEKDAYS = 0b0111110
_WEEKENDS = 0b1000001
_REPEAT = 0x80
_TIME_RE = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*(.*?)\s*$")


class AppointError(ValueError):
    """Invalid schedule text or slot conflict."""


def coerce_slot(value) -> list[int] | None:
    """Accept the lua list, a JSON string "[...]" or a wire string "a,b,c" (optimistic local value)."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            value = json.loads(text) if text.startswith("[") else text.split(",")
        except ValueError:
            return None
    try:
        slot = [int(v) for v in value]
    except (TypeError, ValueError):
        return None
    return slot if len(slot) == 7 else None


def slot_exists(slot: list[int] | None) -> bool:
    return bool(slot) and any(slot[2:6])


def slot_enabled(slot: list[int] | None) -> bool:
    return slot_exists(slot) and slot[0] != 0


def _days_mask(week: int) -> int:
    days = week & _ALL_DAYS
    return _ALL_DAYS if days == 0 else days  # app: week 0 means every day


def format_days(week: int) -> str:
    days = _days_mask(week)
    if days == _ALL_DAYS:
        text = "daily"
    elif days == _WEEKDAYS:
        text = "weekdays"
    elif days == _WEEKENDS:
        text = "weekends"
    else:
        text = ",".join(name for i, name in enumerate(DAY_NAMES) if days >> i & 1)
    if week not in (0, 255) and not week & _REPEAT:
        text += " once"
    return text


def format_slot(slot: list[int] | None) -> str:
    """[1,42,22,30,1,0,255] -> "22:30-01:00 daily"; empty slot -> ""."""
    if not slot_exists(slot):
        return ""
    return f"{slot[2]:02d}:{slot[3]:02d}-{slot[4]:02d}:{slot[5]:02d} {format_days(slot[6])}"


def parse_text(text: str) -> tuple[int, int, int, int, int] | None:
    """"07:00-07:30 mon-fri" -> (start_h, start_m, end_h, end_m, week); "" -> None (delete)."""
    if not text or not text.strip():
        return None
    match = _TIME_RE.match(text)
    if not match:
        raise AppointError(f"expected 'HH:MM-HH:MM [days]', got {text!r}")
    sh, sm, eh, em = (int(match.group(i)) for i in range(1, 5))
    if sh > 23 or eh > 23 or sm > 59 or em > 59:
        raise AppointError(f"invalid time in {text!r}")
    start, end = sh * 60 + sm, eh * 60 + em
    if start == end:
        raise AppointError("start and end time must differ")
    if (end - start) % 1440 < MIN_MINUTES:
        raise AppointError(f"a slot must last at least {MIN_MINUTES} minutes")

    days, repeat = 0, True
    for token in re.split(r"[\s,，、]+", match.group(5).lower()):
        if not token:
            continue
        if token in ("daily", "everyday", "every", "day", "每天"):
            days |= _ALL_DAYS
        elif token in ("weekdays", "workdays", "工作日"):
            days |= _WEEKDAYS
        elif token in ("weekends", "weekend", "周末"):
            days |= _WEEKENDS
        elif token in ("once", "单次"):
            repeat = False
        elif token in _DAY_ALIASES:
            days |= 1 << _DAY_ALIASES[token]
        elif "-" in token and all(p in _DAY_ALIASES for p in token.split("-", 1)):
            first, last = (_DAY_ALIASES[p] for p in token.split("-", 1))
            i = first
            while True:
                days |= 1 << i
                if i == last:
                    break
                i = (i + 1) % 7
        else:
            raise AppointError(f"unknown day {token!r} (use daily, weekdays, weekends, mon..sun, once)")
    if days == 0:
        days = _ALL_DAYS
    return sh, sm, eh, em, days | (_REPEAT if repeat else 0)


def _week_intervals(slot: list[int]) -> list[tuple[int, int]]:
    """Minute intervals on a 7-day circle (0 = Sunday 00:00); overnight slots spill into the next day."""
    week_len = 7 * 1440
    start, end = slot[2] * 60 + slot[3], slot[4] * 60 + slot[5]
    length = (end - start) % 1440
    out = []
    days = _days_mask(slot[6])
    for day in range(7):
        if days >> day & 1:
            s = day * 1440 + start
            e = s + length
            if e <= week_len:
                out.append((s, e))
            else:
                out += [(s, week_len), (0, e - week_len)]
    return out


def find_conflict(index: int, slot: list[int], slots: list[list[int] | None]) -> int | None:
    """Return the 0-based index of another enabled slot overlapping `slot`, else None."""
    mine = _week_intervals(slot)
    for other_index, other in enumerate(slots):
        if other_index == index or not slot_enabled(other):
            continue
        for a, b in mine:
            for c, d in _week_intervals(other):
                if a < d and c < b:
                    return other_index
    return None


def to_wire(slot: list[int]) -> str:
    return ",".join(str(v) for v in slot)
