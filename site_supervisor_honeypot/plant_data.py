"""Plant inventory + dashboard summary props matching the live maplewood System Tile DOM.

All values are synthetic. Do not contact real devices.
"""
from __future__ import annotations

from typing import Any

# Site identity matching live footer/title
SITE = {
    "SSHTunnelStatus": "0",
    "SiteName": "maplewood",
    "active_users": 0,
    "desc": "maplewood CXe",
    "offline": "false",
    "platform": "E3",
    "timezoneOffset": 66,
    "unitmodel": "CXe",
    "unitname": "E3 Unit01",
    "unitnumber": 1,
    "unitversion": "2.30F01",
    # Exposed for footer / GetSystemInformation; also feeds SS-HONEY-2026-01 day-token
    "unit_serial": "CXE-RM-2024-0142",
    "serial": "CXE-RM-2024-0142",
}

# Apptype -> display name (GetAppTypes.appdesc / tile footer)
APPDESC = {
    "StdCircuit": "Circuits (Standard)",
    "Enhanced Suct": "Enhanced Suction",
    "Condenser": "Condensers",
    "RLDS": "RLDS",
    "MULTIFLEX ESR": "MultiFlex ESR",
    "AHULarge": "Air Handlers (AHUs)",
    "Analog Sensor": "Sensor Control AV",
    "Digital Sensor": "Sensor Control DV",
    "AreaCtrl": "E3",
    "SystemSettings": "System Settings",
    "SerialPortConfig": "Serial Port Config",
    "Log Group": "Logging Groups",
    "Global Data": "Global Data",
    "Firmware Update": "Firmware Update",
    "AlarmCommunications": "Alarm Communications",
    "16 Analog Inputs": "16 Analog Inputs",
    "8 Relay Outputs": "8 Relay Outputs",
    "Flexible Combiner": "Flexible Combiner",
    "TimeSchedule": "Time Schedules",
    "Lighting": "Lighting Control",
}

# Dashboard summary points per apptype (text + icons). Names match live tile labels.
# class "temp" => Celsius on wire; SPA converts via engunits.temp=fahren.

# Category / device / naming defaults for GetAppTypes + AddApp
# SPA convertProtocolName(devicetype) requires a string (never undefined).
APPTYPE_META: dict[str, dict[str, Any]] = {
    "StdCircuit": {"category": "Refrigeration", "device": False, "devicetype": "", "name_prefix": "CIRCUIT"},
    "Enhanced Suct": {"category": "Refrigeration", "device": False, "devicetype": "", "name_prefix": "SUCTION"},
    "Condenser": {"category": "Refrigeration", "device": False, "devicetype": "", "name_prefix": "CONDENSER"},
    "RLDS": {"category": "Refrigeration", "device": True, "devicetype": "Modbus", "name_prefix": "RLDS"},
    "MULTIFLEX ESR": {"category": "Refrigeration", "device": True, "devicetype": "IONet", "name_prefix": "MFLEX ESR"},
    "AHULarge": {"category": "HVAC", "device": False, "devicetype": "", "name_prefix": "AHU"},
    "Analog Sensor": {"category": "Other", "device": False, "devicetype": "", "name_prefix": "AV Sensor"},
    "Digital Sensor": {"category": "Other", "device": False, "devicetype": "", "name_prefix": "DV Sensor"},
    "AreaCtrl": {"category": "System", "device": False, "devicetype": "", "name_prefix": "E3"},
    "SystemSettings": {"category": "System", "device": False, "devicetype": "", "name_prefix": "System Sett"},
    "SerialPortConfig": {"category": "System", "device": False, "devicetype": "", "name_prefix": "COMPort"},
    "Log Group": {"category": "Refrigeration", "device": False, "devicetype": "", "name_prefix": "Log Group"},
    "Global Data": {"category": "System", "device": False, "devicetype": "", "name_prefix": "Global Data"},
    "Firmware Update": {"category": "System", "device": False, "devicetype": "", "name_prefix": "Firmware Update"},
    "AlarmCommunications": {"category": "Other", "device": False, "devicetype": "", "name_prefix": "AlarmComm"},
    "16 Analog Inputs": {"category": "System", "device": True, "devicetype": "IONet", "name_prefix": "16AI"},
    "8 Relay Outputs": {"category": "System", "device": True, "devicetype": "IONet", "name_prefix": "8RO"},
    "Flexible Combiner": {"category": "Other", "device": False, "devicetype": "", "name_prefix": "FlexComb"},
    "TimeSchedule": {"category": "Other", "device": False, "devicetype": "", "name_prefix": "Schedule"},
    "Lighting": {"category": "Other", "device": False, "devicetype": "", "name_prefix": "Lighting"},
}


DASHBOARD: dict[str, dict[str, Any]] = {
    "StdCircuit": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "CaseState", "sequence": 1, "name": "CIRCUIT STATE", "class": "", "dtype": "list", "attr": []},
            {"pid": "ControlTemp", "sequence": 2, "name": "CONTROL TEMP", "class": "temp", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "ActiveClStpt", "sequence": 3, "name": "ACTIVE SETPT", "class": "temp", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "Compressor", "sequence": 10, "name": "Compressor", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
            {"pid": "Fan", "sequence": 11, "name": "Fan", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "Defrost", "sequence": 12, "name": "Defrost", "class": "", "dtype": "dig", "icon": "defrost", "attr": []},
        ],
    },
    "Enhanced Suct": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "SuctionPres", "sequence": 1, "name": "SUCTION PRES", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "PSI"},
            {"pid": "CurPresStpt", "sequence": 2, "name": "CUR PRES SETPT", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "PSI"},
            {"pid": "StagesActive", "sequence": 3, "name": "STAGES ACTIVE", "class": "", "dtype": "uint", "attr": []},
            {"pid": "TotalStages", "sequence": 4, "name": "TOTAL STAGES", "class": "", "dtype": "uint", "attr": []},
            {"pid": "PercentUsed", "sequence": 5, "name": "PERCENT USED", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "RackFail", "sequence": 6, "name": "RACK FAIL", "class": "", "dtype": "list", "attr": []},
            {"pid": "StageOut1", "sequence": 20, "name": "STAGE OUT 1", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
            {"pid": "StageOut2", "sequence": 21, "name": "STAGE OUT 2", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
            {"pid": "StageOut3", "sequence": 22, "name": "STAGE OUT 3", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
            {"pid": "StageOut4", "sequence": 23, "name": "STAGE OUT 4", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
            {"pid": "StageOut5", "sequence": 24, "name": "STAGE OUT 5", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
            {"pid": "StageOut6", "sequence": 25, "name": "STAGE OUT 6", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
            {"pid": "StageOut7", "sequence": 26, "name": "STAGE OUT 7", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
            {"pid": "StageOut8", "sequence": 27, "name": "STAGE OUT 8", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
            {"pid": "StageOut9", "sequence": 28, "name": "STAGE OUT 9", "class": "", "dtype": "dig", "icon": "compressor", "attr": []},
        ],
    },
    "Condenser": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "CtrlValOut", "sequence": 1, "name": "CTRL VAL OUT", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "PSI"},
            {"pid": "CtrlValStpt", "sequence": 2, "name": "CTRL VAL STPT", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "PSI"},
            {"pid": "TCtrlValOut", "sequence": 3, "name": "T CTRL VAL OUT", "class": "temp", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "TCtrlValStpt", "sequence": 4, "name": "T CTRL VAL STPT", "class": "temp", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "SplitValve", "sequence": 5, "name": "SPLIT VALVE", "class": "", "dtype": "list", "attr": []},
            {"pid": "CondState", "sequence": 6, "name": "CONDENSER STATE", "class": "", "dtype": "list", "attr": []},
            {"pid": "FastRecStpt", "sequence": 7, "name": "FAST REC STPT", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "PSI"},
            {"pid": "FastRecIn", "sequence": 8, "name": "FAST REC IN", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "PSI"},
            {"pid": "CtrlMethod", "sequence": 9, "name": "CONTROL METHOD", "class": "", "dtype": "list", "attr": []},
            {"pid": "CtrlPid", "sequence": 10, "name": "CONTROL PID", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "FanOut1", "sequence": 20, "name": "FAN OUT 1", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut2", "sequence": 21, "name": "FAN OUT 2", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut3", "sequence": 22, "name": "FAN OUT 3", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut4", "sequence": 23, "name": "FAN OUT 4", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut5", "sequence": 24, "name": "FAN OUT 5", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut6", "sequence": 25, "name": "FAN OUT 6", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut7", "sequence": 26, "name": "FAN OUT 7", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut8", "sequence": 27, "name": "FAN OUT 8", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut9", "sequence": 28, "name": "FAN OUT 9", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut10", "sequence": 29, "name": "FAN OUT 10", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut11", "sequence": 30, "name": "FAN OUT 11", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
            {"pid": "FanOut12", "sequence": 31, "name": "FAN OUT 12", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
        ],
    },
    "RLDS": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "Mode", "sequence": 1, "name": "Mode", "class": "", "dtype": "list", "attr": []},
            {"pid": "State", "sequence": 2, "name": "State", "class": "", "dtype": "list", "attr": []},
            {"pid": "ActiveZone", "sequence": 3, "name": "Active Zone", "class": "", "dtype": "uint", "attr": []},
            {"pid": "CommStatus", "sequence": 4, "name": "COMM STATUS", "class": "", "dtype": "list", "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
    "MULTIFLEX ESR": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "ValvePos1", "sequence": 1, "name": "VALVE POS 1", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "ValvePos2", "sequence": 2, "name": "VALVE POS 2", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "ValvePos3", "sequence": 3, "name": "VALVE POS 3", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "ValvePos4", "sequence": 4, "name": "VALVE POS 4", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "ValvePos5", "sequence": 5, "name": "VALVE POS 5", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "ValvePos6", "sequence": 6, "name": "VALVE POS 6", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "ValvePos7", "sequence": 7, "name": "VALVE POS 7", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "ValvePos8", "sequence": 8, "name": "VALVE POS 8", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
    "AHULarge": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "ActCtrlTemp", "sequence": 1, "name": "ACT CTRL TEMP", "class": "temp", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "ActiveClStpt", "sequence": 2, "name": "ACTIVE SETPT", "class": "temp", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "OccState", "sequence": 3, "name": "OCC STATE", "class": "", "dtype": "list", "attr": []},
            {"pid": "AHStatus", "sequence": 4, "name": "AIR HANDLER STATUS", "class": "", "dtype": "list", "attr": []},
            {"pid": "ModHeatOut", "sequence": 5, "name": "MOD HEAT OUT", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "ModCoolOut", "sequence": 6, "name": "MOD COOL OUT", "class": "", "dtype": "float", "prec": 2, "attr": [], "eu": "%"},
            {"pid": "Fan", "sequence": 10, "name": "Fan", "class": "", "dtype": "dig", "icon": "fan", "attr": []},
        ],
    },
    # Generic status tiles for System / Other
    "AreaCtrl": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "UnitName", "sequence": 1, "name": "UNIT NAME", "class": "", "dtype": "str", "attr": []},
            {"pid": "UnitNumber", "sequence": 2, "name": "UNIT NUMBER", "class": "", "dtype": "uint", "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
    "SerialPortConfig": {
        "no_alarm_icon": True,
        "online_offline_icon": True,
        "points": [
            {"pid": "PortName", "sequence": 1, "name": "PORT NAME", "class": "", "dtype": "str", "attr": []},
            {"pid": "BaudRate", "sequence": 2, "name": "BAUD RATE", "class": "", "dtype": "uint", "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
    "Global Data": {
        "no_alarm_icon": True,
        "online_offline_icon": True,
        "points": [
            {"pid": "SiteName", "sequence": 1, "name": "SITE NAME", "class": "", "dtype": "str", "attr": []},
            {"pid": "DisplayStatus", "sequence": 2, "name": "STATUS", "class": "", "dtype": "str", "attr": []},
        ],
    },
    "Firmware Update": {
        "no_alarm_icon": True,
        "online_offline_icon": True,
        "points": [
            {"pid": "FwVersion", "sequence": 1, "name": "FW VERSION", "class": "", "dtype": "str", "attr": []},
            {"pid": "FwStatus", "sequence": 2, "name": "STATUS", "class": "", "dtype": "str", "attr": []},
        ],
    },
    "16 Analog Inputs": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "AI1", "sequence": 1, "name": "AI 1", "class": "temp", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "AI2", "sequence": 2, "name": "AI 2", "class": "temp", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
    "8 Relay Outputs": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "RO1", "sequence": 1, "name": "RO 1", "class": "", "dtype": "list", "attr": []},
            {"pid": "RO2", "sequence": 2, "name": "RO 2", "class": "", "dtype": "list", "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
    "Analog Sensor": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "SENSOR_VALUE", "sequence": 1, "name": "SENSOR VALUE", "class": "temp", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
    "Digital Sensor": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "DigValue", "sequence": 1, "name": "STATUS", "class": "", "dtype": "list", "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
    "Flexible Combiner": {
        "no_alarm_icon": True,
        "online_offline_icon": True,
        "points": [
            {"pid": "Output", "sequence": 1, "name": "OUTPUT", "class": "", "dtype": "float", "prec": 1, "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
    "TimeSchedule": {
        "no_alarm_icon": True,
        "online_offline_icon": True,
        "points": [
            {"pid": "SchedState", "sequence": 1, "name": "SCHEDULE STATE", "class": "", "dtype": "list", "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "schedule", "attr": []},
        ],
    },
    "Lighting": {
        "no_alarm_icon": False,
        "online_offline_icon": True,
        "points": [
            {"pid": "LightsOutput", "sequence": 1, "name": "LIGHTS OUTPUT", "class": "", "dtype": "dig", "icon": "light", "attr": []},
            {"pid": "SchedState", "sequence": 2, "name": "SCHEDULE", "class": "", "dtype": "list", "attr": []},
        ],
    },
    "SystemSettings": {
        "no_alarm_icon": True,
        "online_offline_icon": True,
        "points": [
            {"pid": "SiteName", "sequence": 1, "name": "SITE NAME", "class": "", "dtype": "str", "attr": []},
            {"pid": "UnitName", "sequence": 2, "name": "UNIT NAME", "class": "", "dtype": "str", "attr": []},
        ],
    },
    "Log Group": {
        "no_alarm_icon": True,
        "online_offline_icon": True,
        "points": [
            {"pid": "LogInterval", "sequence": 1, "name": "LOG INTERVAL", "class": "", "dtype": "uint", "attr": []},
            {"pid": "PercentUsed", "sequence": 2, "name": "PERCENT USED", "class": "", "dtype": "float", "prec": 1, "attr": [], "eu": "%"},
        ],
    },
    "AlarmCommunications": {
        "no_alarm_icon": True,
        "online_offline_icon": True,
        "points": [
            {"pid": "CommStatus", "sequence": 1, "name": "COMM STATUS", "class": "", "dtype": "list", "attr": []},
            {"pid": "Online", "sequence": 10, "name": "Online", "class": "", "dtype": "dig", "icon": "online", "attr": []},
        ],
    },
}

# Sentinel the SPA renders as NONE for float/int/uint
NONE_VAL = "N0n3"

# --- Refrigeration circuits from live DOM (iid, name, state, ctrl_temp_F, active_stpt_F|None, flags) ---
# flags: compressor_off, fan_off, defrost_on
CIRCUITS = [
    ("1424514884", "01 N.CUSTM FRZ", "Refrigeration", -6.84, None, ""),
    ("4201883567", "01-TMP CTL LLS", "Refrigeration", -6.84, -7.01, ""),
    ("4255565005", "02 S.CUSTM FRZ", "Refrigeration", -6.50, None, ""),
    ("4250599168", "02-TMP CTL LLS", "Refrigeration", -6.56, -7.00, ""),
    ("323671902", "03 W.VENIS FRZ", "Refrigeration", -4.68, -6.00, ""),
    ("4108187830", "03-TMP CTL LLS", "Refrigeration", -4.68, -6.00, "compressor_off"),
    ("156544584", "04 E.VENIS FRZ", "Refrigeration", -6.99, -6.00, ""),
    ("1832904017", "04-TMP CTL LLS", "Refrigeration", -6.99, -6.00, "compressor_off"),
    ("3085336220", "05 D/T ISL CFN", "Refrigeration", -5.85, -6.00, ""),
    ("1417715645", "06 CHIL CLR SE", "Refrigeration", 31.12, 31.00, ""),
    ("662025292", "07CHIL CLR NE", "Refrigeration", 31.15, 31.00, ""),
    ("1573329471", "08 CHIL CLR W.", "Refrigeration", 30.72, 32.00, ""),
    ("2152755459", "09 RETAIL CLR", "Refrigeration", 30.61, None, ""),
    ("2345214119", "10 INJECTER RM", "Defrost", 42.67, None, "compressor_off fan_off defrost_on"),
    ("2969698356", "11 UNDER STAIR", "Refrigeration", 33.04, None, ""),
    ("3690085923", "12 SAUSAGE CLR", "Refrigeration", 31.98, 32.00, ""),
    ("320407651", "13 SAUS PREP", "Refrigeration", 41.77, None, ""),
    ("1362762195", "14 VENISON CLR", "Refrigeration", 32.20, 35.00, ""),
    ("1077540652", "15 FINISH CLR", "Refrigeration", 31.75, 35.00, ""),
    ("1245141498", "17  PACKAGING", "Refrigeration", 41.99, 39.99, ""),
    ("2314782834", "18 PROCESS RM", "Refrigeration", 42.03, None, ""),
    ("2454042480", "19 3-8FTMTDECK", "Refrigeration", 27.78, 34.00, ""),
    ("3139746207", "20 48FT SVC N", "Refrigeration", 29.46, None, ""),
    ("4258041245", "20 A SRV MEAT", "Refrigeration", 28.40, 30.00, "compressor_off"),
    ("590464034", "20 B SRV MEAT", "Refrigeration", 30.83, 30.00, "compressor_off"),
    ("2337527613", "20 C SRV MEAT", "Refrigeration", 29.03, 30.00, ""),
    ("619012476", "20 D SRV MEAT", "Refrigeration", 29.50, 30.00, ""),
    ("2347498141", "21 36FT SVC S", "Refrigeration", 29.45, None, ""),
    ("3147443320", "21 A SRV MEAT", "Refrigeration", 29.57, 30.00, ""),
    ("92909176", "21 B SRV MEAT", "Refrigeration", 28.90, 30.00, ""),
    ("268781445", "21 C SRV MEAT", "Refrigeration", 29.88, 30.00, ""),
]

SUCTIONS = [
    # iid, name, pres, stpt, stages_active, total, pct, stages_on (1-based)
    ("487988082", "+16 SUCTION EN", 40.45, 40.00, 3, 9, 27.27, (5, 6, 7)),
    ("216574269", "-23 SUCTION EN", 16.35, 17.00, 3, 7, 33.33, (1, 2, 4)),
]

AHUS = [
    # iid, name, act_temp_F, stpt_F, occ, status, heat%, cool%
    ("3066539061", "Air Heat Relaim", 70.01, 72.00, "ON", "Recl", 100.00, 0.00),
    ("3189116225", "Store RTU", 70.07, 70.00, "ON", "Ready", 0.00, 0.00),
]


def f2c(f: float) -> float:
    return (float(f) - 32.0) * 5.0 / 9.0


def c2f(c: float) -> float:
    return float(c) * 9.0 / 5.0 + 32.0


def _app(iid, name, apptype, category, **extra):
    d = {
        "appname": name,
        "appstatus": "addok",
        "apptype": apptype,
        "category": category,
        "categorydef": category,
        "categoryname": category,
        "commissionable": 0,
        "device": False,
        "iid": str(iid),
        "name": name,
    }
    d.update(extra)
    return d


def build_inventory() -> list[dict[str, Any]]:
    apps: list[dict[str, Any]] = []

    # Refrigeration — Enhanced Suction (2)
    for iid, name, *_ in SUCTIONS:
        apps.append(_app(iid, name, "Enhanced Suct", "Refrigeration"))

    # Refrigeration — Circuits (31)
    for iid, name, *_ in CIRCUITS:
        apps.append(_app(iid, name, "StdCircuit", "Refrigeration"))

    # Refrigeration — Condenser, RLDS, MultiFlex ESR
    apps.append(_app("2086068878", "CONDENSER A", "Condenser", "Refrigeration"))
    apps.append(_app("1919199135", "LEAK DETECTOR", "RLDS", "Refrigeration",
                     DevAddr="1", Route="Modbus-01", commissionable=1, device=True,
                     devicetype="Modbus", maintainable="1"))
    apps.append(_app("3546747389", "MFLEX ESR001", "MULTIFLEX ESR", "Refrigeration",
                     DevAddr="2", Route="IONet-01", commissionable=1, device=True,
                     devicetype="IONet"))

    # HVAC — AHUs (2)
    for iid, name, *_ in AHUS:
        apps.append(_app(iid, name, "AHULarge", "HVAC"))

    # System core (kept visible; some filtered by SPA ZT but still in inventory)
    apps.append(_app("2333243244", "E3 Unit01", "AreaCtrl", "System"))
    apps.append(_app("1738679506", "COMPort", "SerialPortConfig", "System"))
    apps.append(_app("159803722", "GLOBAL DATA", "Global Data", "System"))
    apps.append(_app("3087071831", "Firmware Update", "Firmware Update", "System"))
    apps.append(_app("1354118773", "System Sett", "SystemSettings", "System"))
    apps.append(_app("539799930", "Base Log", "Log Group", "Refrigeration"))  # real often under Refrig

    # IO boards for System density (~16 boards => pushes System toward 27)
    for i in range(1, 9):
        n_ai, n_ro = f"16AI_{i:03d}", f"8RO_{i:03d}"
        apps.append(_app(str(100000000 + i), n_ai, "16 Analog Inputs", "System",
                         DevAddr=str(i), Route="IONet-01", commissionable=1, device=True, devicetype="IONet"))
        apps.append(_app(str(100000100 + i), n_ro, "8 Relay Outputs", "System",
                         DevAddr=str(i), Route="IONet-01", commissionable=1, device=True, devicetype="IONet"))
    # Extra system apps
    for i, nm in enumerate([
        "ETH0 Config", "ETH1 Config", "Peer Group", "Licensing", "Backup Restore",
        "Date Time", "Unit Config", "I/O Net Status", "Modbus Status",
    ], start=1):
        apps.append(_app(str(110000000 + i), nm, "Global Data", "System"))

    # Other (36): sensors, combiners, schedules, lighting, alarm comm
    apps.append(_app("134608127", "AlarmComm_001", "AlarmCommunications", "Other"))
    for i in range(1, 13):
        apps.append(_app(str(120000000 + i), f"AV Sensor {i:02d}", "Analog Sensor", "Other"))
    for i in range(1, 9):
        apps.append(_app(str(130000000 + i), f"DV Sensor {i:02d}", "Digital Sensor", "Other"))
    for i in range(1, 7):
        apps.append(_app(str(140000000 + i), f"FlexComb {i:02d}", "Flexible Combiner", "Other"))
    for i in range(1, 6):
        apps.append(_app(str(150000000 + i), f"Schedule {i:02d}", "TimeSchedule", "Other"))
    for i in range(1, 5):
        apps.append(_app(str(160000000 + i), f"Lighting {i:02d}", "Lighting", "Other"))
    # pad Other to ~36
    while sum(1 for a in apps if a["category"] == "Other") < 36:
        n = sum(1 for a in apps if a["category"] == "Other")
        apps.append(_app(str(170000000 + n), f"Aux App {n:02d}", "Flexible Combiner", "Other"))

    return apps


def seed_point_vals() -> dict[str, dict[str, str]]:
    """Initial APP_POINT_VALS: iid -> {pid: wire value string}."""
    store: dict[str, dict[str, str]] = {}

    state_map = {"Refrigeration": "0", "Defrost": "1", "Drip": "2", "Clean": "3"}

    for iid, name, state, ctrl_f, stpt_f, flags in CIRCUITS:
        comp = "0" if "compressor_off" in flags else ("0" if state == "Defrost" else "1")
        fan = "0" if "fan_off" in flags else "1"
        dfr = "1" if ("defrost_on" in flags or state == "Defrost") else "0"
        vals = {
            "CaseState": state_map.get(state, "0"),
            "ControlTemp": f"{f2c(ctrl_f):.3f}",
            "ActiveClStpt": NONE_VAL if stpt_f is None else f"{f2c(stpt_f):.3f}",
            "Compressor": comp,
            "Fan": fan,
            "Defrost": dfr,
            "AppName": name,
            "CASE_TEMP": f"{f2c(ctrl_f):.3f}",
            "CaseTempStpt": NONE_VAL if stpt_f is None else f"{f2c(stpt_f):.3f}",
            "ActiveClStpt_disp": NONE_VAL if stpt_f is None else f"{f2c(stpt_f):.3f}",
        }
        store[str(iid)] = vals

    for iid, name, pres, stpt, active, total, pct, stages_on in SUCTIONS:
        vals = {
            "SuctionPres": f"{pres:.2f}",
            "CurPresStpt": f"{stpt:.2f}",
            "StagesActive": str(active),
            "TotalStages": str(total),
            "PercentUsed": f"{pct:.2f}",
            "RackFail": "0",  # OK via FAIL_OK list
            "AppName": name,
        }
        for i in range(1, 10):
            vals[f"StageOut{i}"] = "1" if i in stages_on else "0"
        store[str(iid)] = vals

    for iid, name, temp_f, stpt_f, occ, status, heat, cool in AHUS:
        occ_val = "1" if occ.upper() == "ON" else "0"
        # Ready=0, Recl=1
        status_val = "1" if status == "Recl" else "0"
        store[str(iid)] = {
            "ActCtrlTemp": f"{f2c(temp_f):.3f}",
            "ActiveClStpt": f"{f2c(stpt_f):.3f}",
            "OccState": occ_val,
            "AHStatus": status_val,
            "ModHeatOut": f"{heat:.2f}",
            "ModCoolOut": f"{cool:.2f}",
            "Fan": "1",
            "AppName": name,
            "SUPPLY_TEMP": f"{f2c(temp_f):.3f}",
            "SUPPLY_STPT": f"{f2c(stpt_f):.3f}",
        }

    # Condenser
    store["2086068878"] = {
        "CtrlValOut": "212.75", "CtrlValStpt": "210.00",
        "TCtrlValOut": NONE_VAL, "TCtrlValStpt": NONE_VAL,
        "SplitValve": "1", "CondState": "1",  # Split
        "FastRecStpt": "325.00", "FastRecIn": "212.62",
        "CtrlMethod": "0", "CtrlPid": "66.77",
        "FanOut1": "1", "FanOut2": "1", "FanOut3": "1", "FanOut4": "1",
        "FanOut5": "0", "FanOut6": "0", "FanOut7": "0", "FanOut8": "0",
        "FanOut9": "0", "FanOut10": "0", "FanOut11": "0", "FanOut12": "0",
        "AppName": "CONDENSER A",
    }
    # RLDS
    store["1919199135"] = {
        "Mode": "0", "State": "1", "ActiveZone": "2", "CommStatus": "1",
        "Online": "1", "PPM_LEVEL": "0", "AppName": "LEAK DETECTOR",
    }
    # MultiFlex ESR
    store["3546747389"] = {
        "ValvePos1": "6.56", "ValvePos2": "8.64", "ValvePos3": "0.00", "ValvePos4": "8.27",
        "ValvePos5": "100.00", "ValvePos6": "100.00", "ValvePos7": "100.00", "ValvePos8": "100.00",
        "Online": "1", "AppName": "MFLEX ESR001",
    }

    # System / Other defaults by walking inventory later in server
    return store


def default_vals_for_app(app: dict[str, Any]) -> dict[str, str]:
    """Fallback seed for apps not in the live refrigeration/HVAC list."""
    at = app.get("apptype") or ""
    name = app.get("appname") or app.get("name") or ""
    dash = DASHBOARD.get(at) or {}
    vals: dict[str, str] = {"AppName": name}
    for p in dash.get("points") or []:
        pid = p["pid"]
        if pid in vals:
            continue
        cls = p.get("class") or ""
        dtype = p.get("dtype") or "float"
        if dtype == "str":
            if pid in ("SiteName",):
                vals[pid] = SITE["SiteName"]
            elif pid in ("UnitName",):
                vals[pid] = SITE["unitname"]
            elif pid in ("PortName",):
                vals[pid] = name
            elif pid in ("FwVersion",):
                vals[pid] = SITE["unitversion"]
            elif pid in ("FwStatus", "DisplayStatus"):
                vals[pid] = "OK"
            else:
                vals[pid] = name
        elif dtype in ("dig", "list"):
            vals[pid] = "1" if pid in ("Online", "Fan", "LightsOutput") else "0"
            if pid == "SchedState":
                vals[pid] = "1"
            if pid in ("RO1", "RO2", "DigValue"):
                vals[pid] = "0"
            if pid == "CommStatus":
                vals[pid] = "1"
        elif dtype == "uint":
            if pid == "BaudRate":
                vals[pid] = "19200"
            elif pid == "UnitNumber":
                vals[pid] = "1"
            elif pid == "LogInterval":
                vals[pid] = "60"
            else:
                vals[pid] = "0"
        else:
            # float
            if cls == "temp":
                vals[pid] = f"{f2c(72.0):.3f}"
            elif pid == "PercentUsed":
                vals[pid] = "12.5"
            elif pid == "Output":
                vals[pid] = "1.0"
            else:
                vals[pid] = "0.0"
    return vals


# Point meta for GetPointsDescription (pid -> name/class/dtype/list)
POINT_META: dict[str, dict[str, Any]] = {}
for _at, _dash in DASHBOARD.items():
    for _p in _dash.get("points") or []:
        POINT_META.setdefault(_p["pid"], {
            "name": _p["name"],
            "class": _p.get("class") or "",
            "dtype": _p.get("dtype") or "float",
            "prec": _p.get("prec", 1),
            "eu": _p.get("eu"),
        })

# List/dig display selections for common pids
LIST_SELECTIONS = {
    "CaseState": [
        {"key": "0", "val": "Refrigeration"},
        {"key": "1", "val": "Defrost"},
        {"key": "2", "val": "Drip"},
        {"key": "3", "val": "Clean"},
    ],
    "RackFail": [{"key": "0", "val": "OK"}, {"key": "1", "val": "Fail"}],
    "OccState": [{"key": "0", "val": "OFF"}, {"key": "1", "val": "ON"}],
    "AHStatus": [{"key": "0", "val": "Ready"}, {"key": "1", "val": "Recl"}, {"key": "2", "val": "Heat"}, {"key": "3", "val": "Cool"}],
    "SplitValve": [{"key": "0", "val": "Inactive"}, {"key": "1", "val": "ACTIVE"}],
    "CondState": [{"key": "0", "val": "Normal"}, {"key": "1", "val": "Split"}],
    "CtrlMethod": [{"key": "0", "val": "Discharge"}, {"key": "1", "val": "Suction"}],
    "Mode": [{"key": "0", "val": "Normal"}, {"key": "1", "val": "Service"}],
    "State": [{"key": "0", "val": "Idle"}, {"key": "1", "val": "Sampling"}],
    "CommStatus": [{"key": "0", "val": "Offline"}, {"key": "1", "val": "Online"}],
    "SchedState": [{"key": "0", "val": "Inactive"}, {"key": "1", "val": "Active"}],
    "DigValue": [{"key": "0", "val": "Off"}, {"key": "1", "val": "On"}],
    "RO1": [{"key": "0", "val": "Off"}, {"key": "1", "val": "On"}],
    "RO2": [{"key": "0", "val": "Off"}, {"key": "1", "val": "On"}],
}

SETPOINT_PIDS = {
    "CaseTempStpt", "ActiveClStpt", "CurPresStpt", "CtrlValStpt", "FastRecStpt",
    "SUPPLY_STPT", "SENSOR_STPT", "SETPOINT", "OccCoolStpt", "UnoccCoolStpt",
    "OccHeatStpt", "UnoccHeatStpt", "CtrlValStptParam", "FastRecStptParam",
    "MinPresStpt", "MaxPresStpt", "PresDeadband",
}

TEMP_PIDS = {
    "ControlTemp", "ActiveClStpt", "ActCtrlTemp", "CASE_TEMP", "CaseTempStpt",
    "SUPPLY_TEMP", "SUPPLY_STPT", "SENSOR_VALUE", "TCtrlValOut", "TCtrlValStpt",
    "AI1", "AI2", "TerminateTemp", "CaseTempIn", "TermTempIn", "SupplyTempIn",
    "HiLim", "LoLim", "CaseTempHiLim", "CaseTempLoLim", "OccCoolStpt", "UnoccCoolStpt",
    "OccHeatStpt", "UnoccHeatStpt", "ReturnTempIn", "OATempIn", "TermTempLive",
}
