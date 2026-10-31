from homeassistant.const import Platform, UnitOfTemperature, UnitOfVolume, UnitOfTime, PERCENTAGE, PRECISION_HALVES
from homeassistant.components.sensor import SensorStateClass, SensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass

DEVICE_MAPPING = {
    "default": {
        "rationale": ["off", "on"],
        "queries": [{}, {"query_type": "status"}, {"device_type": "controller"}],
        "centralized": [],
        "entities": {
            Platform.SWITCH: {
                "power": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "bubble": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "cold_water": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "cold_water_master": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "bathtub": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "safe": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "cold_water_dot": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "change_litre_switch": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "cold_water_ai": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "cold_water_pressure": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "person_mode_one": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "person_mode_two": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "person_mode_three": {
                    "device_class": SwitchDeviceClass.SWITCH,
                },
                "lamp_control1_power": {
                    "device_class": SwitchDeviceClass.SWITCH,
                    "translation_key": "light",
                    "merge_attributes": ["lamp_control2_power", "lamp_control3_power"],
                },
                "lamp_control2_power": {
                    "device_class": SwitchDeviceClass.SWITCH,
                    "translation_key": "lamp_control2_power",
                    "merge_attributes": ["lamp_control1_power", "lamp_control3_power"],
                },
                "lamp_control3_power": {
                    "device_class": SwitchDeviceClass.SWITCH,
                    "translation_key": "lamp_control3_power",
                    "merge_attributes": ["lamp_control1_power", "lamp_control2_power"],
                },
                # "gesture_function": {
                #     "device_class": SwitchDeviceClass.SWITCH,
                # }
            },
            Platform.CLIMATE: {
                "water_heater": {
                    "power": "power",
                    "hvac_modes": {
                        "off": {"power": "off"},
                        "heat": {"power": "on", "mode": "shower"}
                    },
                    "target_temperature": "temperature",
                    "current_temperature": "out_water_tem",
                    "min_temp": 20,
                    "max_temp": 60,
                    "temperature_unit": UnitOfTemperature.CELSIUS,
                    "precision": PRECISION_HALVES,
                }
            },
            Platform.SELECT: {
                "mode": {
                    "options": {
                        "shower": {"mode": "shower"},
                        "bath": {"mode": "bath"},
                        "mixed": {"mode": "mixed"},
                        "eco": {"mode": "eco"},
                        "kitchen": {"mode": "kitchen"},
                        "thalposis": {"mode": "thalposis"},
                        "intelligence": {"mode": "intelligence"},
                        "unfreeze": {"mode": "unfreeze"},
                        "wash_bowl": {"mode": "wash_bowl"},
                        "high_temperature": {"mode": "high_temperature"},
                        "baby": {"mode": "baby"},
                        "adult": {"mode": "adult"},
                        "old": {"mode": "old"}
                    }
                },
                "power_level": {
                    "options": {
                        "low": {"power_level": 0},
                        "medium": {"power_level": 1},
                        "high": {"power_level": 2},
                        "max": {"power_level": 3}
                    }
                },
                "type_machine": {
                    "options": {
                        "standard": {"type_machine": 20},
                        "premium": {"type_machine": 21},
                        "deluxe": {"type_machine": 22}
                    }
                },
                "capacity": {
                    "options": {
                        "small": {"capacity": 1},
                        "medium": {"capacity": 2},
                        "large": {"capacity": 3}
                    }
                },
                # "gesture_function_type": {
                #     "options": {
                #         "none": {"gesture_function_type": "0"},
                #         "wave": {"gesture_function_type": "1"},
                #         "touch": {"gesture_function_type": "2"},
                #         "proximity": {"gesture_function_type": "3"}
                #     }
                # }
            },
            Platform.SENSOR: {
                "out_water_tem": {
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "water_volume": {
                    "device_class": SensorDeviceClass.VOLUME,
                    "unit_of_measurement": UnitOfVolume.LITERS,
                    "state_class": SensorStateClass.TOTAL_INCREASING
                },
                "zero_cold_tem": {
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "bath_out_volume": {
                    "device_class": SensorDeviceClass.VOLUME,
                    "unit_of_measurement": UnitOfVolume.LITERS,
                    "state_class": SensorStateClass.TOTAL_INCREASING
                },
                "return_water_tem": {
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "change_litre": {
                    "device_class": SensorDeviceClass.VOLUME,
                    "unit_of_measurement": UnitOfVolume.LITERS,
                    "state_class": SensorStateClass.TOTAL_INCREASING
                },
                "bathtub_water_level": {
                    "device_class": SensorDeviceClass.VOLUME,
                    "unit_of_measurement": UnitOfVolume.LITERS,
                    "state_class": SensorStateClass.TOTAL_INCREASING
                },
                "temperature": {
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "gas_lift_percent": {
                    "device_class": SensorDeviceClass.POWER_FACTOR,
                    "unit_of_measurement": PERCENTAGE,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "person_tem_one": {
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "person_tem_two": {
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "person_tem_three": {
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "in_water_tem": {
                    "device_class": SensorDeviceClass.TEMPERATURE,
                    "unit_of_measurement": UnitOfTemperature.CELSIUS,
                    "state_class": SensorStateClass.MEASUREMENT
                },
                "error_code": {
                    "device_class": SensorDeviceClass.ENUM
                }
            }
        }
    }
}

# 定时零冷水: models with the device-side 4-slot schedule also poll the "predict" query and get
# a text + switch per slot (entities in zero_cold_appoint.py).
from copy import deepcopy as _deepcopy
from ._zero_cold_appoint import APPOINT_SN8 as _APPOINT_SN8, PREDICT_QUERY as _PREDICT_QUERY, SLOT_ATTRS as _SLOT_ATTRS

_appoint = _deepcopy(DEVICE_MAPPING["default"])
_appoint["queries"].append(_PREDICT_QUERY)
for _i, _attr in enumerate(_SLOT_ATTRS, 1):
    _appoint["entities"].setdefault(Platform.TEXT, {})[f"zero_cold_appoint_{_i}"] = {
        "attribute": _attr,
        "zero_cold_appoint": True,
        "icon": "mdi:calendar-clock",
    }
    _appoint["entities"][Platform.SWITCH][f"zero_cold_appoint_{_i}_enable"] = {
        "attribute": _attr,
        "zero_cold_appoint": True,
        "icon": "mdi:calendar-check",
    }
DEVICE_MAPPING[_APPOINT_SN8] = _appoint
