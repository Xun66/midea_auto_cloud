# midea_auto_cloud (patched)

Fork of [sususweet/midea_auto_cloud](https://github.com/sususweet/midea_auto_cloud) (Apache-2.0) with small local
patches. **Use upstream unless you need these patches.**

This branch (`patched`) does not carry upstream's history. A daily workflow takes upstream's latest release,
applies `patches/*.patch` and publishes it as `<upstream tag>-patched`, so HACS follows upstream releases.
If a patch stops applying the workflow fails and nothing is published.

## Patches

- `0001-softener-63600118-water-usage.patch` — T0xED sn8 `63600118` (water softener, e.g. MSO120-1000G):
  add sensors for the water usage the device already reports: `water_consumption_big` (total litres,
  usable in the Energy dashboard), `water_consumption_today`, `water_consumption_average`.
- `0002-e3-zero-cold-water-schedule.patch` — T0xE3 gas water heaters whose app uses the device-side
  定时零冷水 schedule (231 sn8s, e.g. `511018ZH` JSQ30-M9R Ultra): poll the lua `predict` query and add,
  per slot (4), a text entity `22:30-01:00 daily` / `07:00-07:30 mon-fri` / `06:00-06:30 sat once`
  (empty = delete) and an on/off switch. Same slots as the 美居 app, so edits show up on both sides.

## Install (HACS)

HACS → ⋮ → Custom repositories → this repository, type *Integration*, then download it.
Replace an existing upstream install by removing the upstream repository in HACS first
(config entries and devices are kept).

## Manual sync

`./sync.sh [TAG]` locally, or run the *Sync upstream release* workflow (optionally with *force*).
