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

## Install (HACS)

HACS → ⋮ → Custom repositories → this repository, type *Integration*, then download it.
Replace an existing upstream install by removing the upstream repository in HACS first
(config entries and devices are kept).

## Manual sync

`./sync.sh [TAG]` locally, or run the *Sync upstream release* workflow (optionally with *force*).
