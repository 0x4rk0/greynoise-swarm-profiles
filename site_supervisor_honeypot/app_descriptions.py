"""ADF-like GetAppDescription payloads for each Site Supervisor apptype.

Synthetic only — mirrors Copeland E3 / Site Supervisor group naming and the
live maplewood Status tile labels. Do not contact real devices.
"""
from __future__ import annotations

from typing import Any, Callable

from plant_data import (
    SITE, APPDESC, DASHBOARD, NONE_VAL, LIST_SELECTIONS, f2c,
)


def _grp(name: str, sort: int, visible: str = "1") -> dict:
    return {"type": "group", "name": name, "id": name, "sort": str(sort), "visible": visible}


def _pt(pid, name, group, *, cls="", funct="param", dtype="float", prec=1,
        attr=None, val="0", visible="Basic", grpseq="1", desc="",
        min_v=None, max_v=None, selections=None):
    d = {
        "pid": pid, "name": name, "group": group, "grpseq": str(grpseq),
        "subgrpseq": "1", "class": cls, "funct": funct, "desc": desc or name,
        "dtype": dtype, "attr": attr if attr is not None else [],
        "val": str(val), "visible": visible,
    }
    if selections is not None:
        d["dtype"] = "list"
        d["list"] = selections
    elif dtype == "float":
        d["prec"] = str(prec)
    if min_v is not None:
        d["min"] = str(min_v)
    if max_v is not None:
        d["max"] = str(max_v)
    return d


def _dig(off="Off", on="On"):
    return [{"key": "0", "val": off}, {"key": "1", "val": on}]


def _case_state_list():
    return [
        {"key": "0", "val": "Refrigeration"},
        {"key": "1", "val": "Defrost"},
        {"key": "2", "val": "Drip"},
        {"key": "3", "val": "Clean"},
    ]


def _header(name: str, apptype: str, groups: list) -> dict:
    return {
        "name": name,
        "apptype": apptype,
        "description": APPDESC.get(apptype, apptype),
        "attr": [],
        "desc": groups,
    }


def _sv(store: dict, pid: str, default: str = "0") -> str:
    v = store.get(pid)
    return default if v is None else str(v)


# ---------------------------------------------------------------------------
# StdCircuit — Circuits (Standard)
# ---------------------------------------------------------------------------
def build_std_circuit(name: str, store: dict, *, ctrl_f: float = 30.0, stpt_f: float | None = 30.0) -> dict:
    wire = _sv(store, "ControlTemp", f"{f2c(ctrl_f):.3f}")
    sp = _sv(store, "ActiveClStpt", NONE_VAL if stpt_f is None else f"{f2c(stpt_f):.3f}")
    sp_num = stpt_f if stpt_f is not None else ctrl_f
    state_val = _sv(store, "CaseState", "0")
    groups = [
        _grp("Status_Group", 1),
        _grp("General", 2),
        _grp("Case Temp", 3),
        _grp("Defr Times", 4),
        _grp("Defrost", 5),
        _grp("Alarms", 6),
        _grp("Inputs", 7),
        _grp("Outputs", 8),
        _grp("Fan Control", 9),
        _grp("EEPR", 10),
        _grp("Demand", 11),
        _grp("Associations", 12),
        _grp("Input/Output Status", 13),
        _grp("Generic Alarms", 14),
    ]
    points = [
        # Status = tile points
        _pt("CaseState", "CIRCUIT STATE", "Status_Group", funct="output", dtype="dig",
            val=state_val, selections=_case_state_list(), grpseq=1),
        _pt("ControlTemp", "CONTROL TEMP", "Status_Group", cls="temp", funct="output",
            dtype="float", prec=1, val=wire, grpseq=2),
        _pt("ActiveClStpt", "ACTIVE SETPT", "Status_Group", cls="temp", funct="output",
            dtype="float", prec=1, val=sp, grpseq=3),
        _pt("Compressor", "Compressor", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "Compressor", "1"), selections=_dig(), grpseq=4),
        _pt("Fan", "Fan", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "Fan", "1"), selections=_dig(), grpseq=5),
        _pt("Defrost", "Defrost", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "Defrost", "0"), selections=_dig(), grpseq=6),
        # General
        _pt("AppName", "Application Name", "General", funct="param", dtype="str",
            val=name, grpseq=1),
        _pt("CP^Category", "Category", "General", funct="param", dtype="str",
            val="Refrigeration", attr=["lock"], grpseq=2),
        _pt("CircuitNum", "Circuit Number", "General", funct="param", dtype="uint",
            val="1", attr=["setpt"], grpseq=3),
        # Case Temp
        _pt("CaseTempStpt", "Case Temp Setpoint", "Case Temp", cls="temp", funct="param",
            dtype="float", prec=1, val=sp if sp != NONE_VAL else f"{f2c(ctrl_f):.3f}",
            attr=["setpt"], min_v=-40, max_v=60, grpseq=1),
        _pt("CaseTempHiLim", "Case Temp Hi Limit", "Case Temp", cls="temp", funct="param",
            dtype="float", prec=1, val=f"{f2c(sp_num + 2):.3f}", attr=["setpt"], grpseq=2),
        _pt("CaseTempLoLim", "Case Temp Lo Limit", "Case Temp", cls="temp", funct="param",
            dtype="float", prec=1, val=f"{f2c(sp_num - 3):.3f}", attr=["setpt"], grpseq=3),
        _pt("CaseTempDB", "Case Temp Deadband", "Case Temp", cls="temp", funct="param",
            dtype="float", prec=1, val=f"{(1.0 * 5 / 9):.3f}", attr=["setpt"], grpseq=4),
        _pt("TempControl", "Temp Control", "Case Temp", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=5),
        # Defr Times
        _pt("DefrostType", "Defrost Type", "Defr Times", funct="param", dtype="list",
            val="0" if sp_num > 0 else "1",
            selections=[{"key": "0", "val": "Off Time"}, {"key": "1", "val": "Electric"},
                        {"key": "2", "val": "Hot Gas"}], grpseq=1),
        _pt("DefrostDuration", "Defrost Duration (min)", "Defr Times", funct="param",
            dtype="uint", val="25" if sp_num > 0 else "40", attr=["setpt"], min_v=5, max_v=120, grpseq=2),
        _pt("DefrostInterval", "Defrost Interval (hr)", "Defr Times", funct="param",
            dtype="uint", val="6" if sp_num > 0 else "8", attr=["setpt"], min_v=1, max_v=24, grpseq=3),
        _pt("TerminateTemp", "Terminate Temp", "Defr Times", cls="temp", funct="param",
            dtype="float", prec=1, val=f"{f2c(48.0):.3f}", attr=["setpt"], grpseq=4),
        _pt("DripTime", "Drip Time (min)", "Defr Times", funct="param", dtype="uint",
            val="5", attr=["setpt"], grpseq=5),
        # Defrost runtime
        _pt("DefrostState", "Defrost State", "Defrost", funct="output", dtype="dig",
            val=_sv(store, "Defrost", "0"), selections=_dig("Idle", "Active"), grpseq=1),
        _pt("TermTempLive", "Termination Temp", "Defrost", cls="temp", funct="output",
            dtype="float", prec=1, val=f"{f2c(ctrl_f + 4):.3f}", grpseq=2),
        # Alarms
        _pt("HiLimDelay", "Hi Limit Delay (min)", "Alarms", funct="param", dtype="uint",
            val="15", attr=["setpt"], grpseq=1),
        _pt("LoLimDelay", "Lo Limit Delay (min)", "Alarms", funct="param", dtype="uint",
            val="15", attr=["setpt"], grpseq=2),
        _pt("EnCaseTempAlm", "Enable Case Temp Alarm", "Alarms", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=3),
        _pt("EnProofAlm", "Enable Proof Alarm", "Alarms", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=4),
        # Inputs / Outputs
        _pt("CaseTempIn", "Case Temp Sensor", "Inputs", cls="temp", funct="input",
            dtype="float", prec=1, val=wire, grpseq=1),
        _pt("TermTempIn", "Termination Sensor", "Inputs", cls="temp", funct="input",
            dtype="float", prec=1, val=f"{f2c(ctrl_f + 4):.3f}", grpseq=2),
        _pt("ProofIn", "Proof Input", "Inputs", funct="input", dtype="dig",
            val="1", selections=_dig("Open", "Closed"), grpseq=3),
        _pt("RefrigOut", "Refrigeration Output", "Outputs", funct="output", dtype="dig",
            val=_sv(store, "Compressor", "1"), selections=_dig(), attr=["no_ovr"], grpseq=1),
        _pt("DefrostOut", "Defrost Output", "Outputs", funct="output", dtype="dig",
            val=_sv(store, "Defrost", "0"), selections=_dig(), attr=["no_ovr"], grpseq=2),
        _pt("FanOut", "Evaporator Fan", "Outputs", funct="output", dtype="dig",
            val=_sv(store, "Fan", "1"), selections=_dig(), attr=["no_ovr"], grpseq=3),
        # Fan Control
        _pt("FanMode", "Fan Mode", "Fan Control", funct="param", dtype="list",
            val="0", selections=[{"key": "0", "val": "Continuous"}, {"key": "1", "val": "Cycle"},
                                 {"key": "2", "val": "Off During Defrost"}], grpseq=1),
        _pt("FanDelay", "Fan Delay (sec)", "Fan Control", funct="param", dtype="uint",
            val="0", attr=["setpt"], grpseq=2),
        # EEPR / Demand / Associations / IO / Generic
        _pt("EEPRPos", "EEPR Position %", "EEPR", funct="output", dtype="float",
            prec=1, val="45.0", grpseq=1),
        _pt("EEPREnable", "EEPR Enable", "EEPR", funct="param", dtype="dig",
            val="0", selections=_dig("Disabled", "Enabled"), grpseq=2),
        _pt("DemandShed", "Demand Shed", "Demand", funct="output", dtype="dig",
            val="0", selections=_dig("Normal", "Shed"), grpseq=1),
        _pt("AssocCount", "Associations", "Associations", funct="output", dtype="uint",
            val="0", grpseq=1),
        _pt("IOSummary", "I/O Summary", "Input/Output Status", funct="output", dtype="str",
            val="OK", attr=["lock"], grpseq=1),
        _pt("GenericAlm", "Generic Alarm", "Generic Alarms", funct="output", dtype="dig",
            val="0", selections=_dig("Normal", "Alarm"), grpseq=1),
    ]
    return {"header": _header(name, "StdCircuit", groups), "points": points}


# ---------------------------------------------------------------------------
# Enhanced Suct
# ---------------------------------------------------------------------------
def build_enhanced_suct(name: str, store: dict, *, pres: float = 40.0, stpt: float = 40.0) -> dict:
    total = int(_sv(store, "TotalStages", "9"))
    groups = [
        _grp("Status_Group", 1), _grp("General", 2), _grp("Setpoints", 3),
        _grp("Inputs", 4), _grp("Outputs", 5), _grp("Stage Setup", 6),
        _grp("Stage Outs", 7), _grp("Alarms", 8), _grp("Proof", 9),
        _grp("Comp Oil", 10), _grp("Normal", 11), _grp("Power", 12),
        _grp("Hot Gas", 13), _grp("Checkit", 14), _grp("Checkit Alm", 15),
        _grp("ISD", 16), _grp("Associations", 17),
        _grp("Input/Output Status", 18), _grp("Generic Alarms", 19),
    ]
    points = [
        _pt("SuctionPres", "SUCTION PRES", "Status_Group", funct="output", dtype="float",
            prec=2, val=_sv(store, "SuctionPres", f"{pres:.2f}"), grpseq=1),
        _pt("CurPresStpt", "CUR PRES SETPT", "Status_Group", funct="param", dtype="float",
            prec=2, val=_sv(store, "CurPresStpt", f"{stpt:.2f}"), attr=["setpt"],
            min_v=0, max_v=150, grpseq=2),
        _pt("StagesActive", "STAGES ACTIVE", "Status_Group", funct="output", dtype="uint",
            val=_sv(store, "StagesActive", "0"), grpseq=3),
        _pt("TotalStages", "TOTAL STAGES", "Status_Group", funct="output", dtype="uint",
            val=_sv(store, "TotalStages", str(total)), grpseq=4),
        _pt("PercentUsed", "PERCENT USED", "Status_Group", funct="output", dtype="float",
            prec=2, val=_sv(store, "PercentUsed", "0"), grpseq=5),
        _pt("RackFail", "RACK FAIL", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "RackFail", "0"), selections=LIST_SELECTIONS["RackFail"], grpseq=6),
        _pt("AppName", "Application Name", "General", funct="param", dtype="str", val=name, grpseq=1),
        _pt("CP^Category", "Category", "General", funct="param", dtype="str",
            val="Refrigeration", attr=["lock"], grpseq=2),
        _pt("PresDeadband", "Pressure Deadband", "Setpoints", funct="param", dtype="float",
            prec=2, val="2.00", attr=["setpt"], grpseq=1),
        _pt("MinPresStpt", "Minimum Pressure Stpt", "Setpoints", funct="param", dtype="float",
            prec=2, val=f"{max(0, stpt - 10):.2f}", attr=["setpt"], grpseq=2),
        _pt("MaxPresStpt", "Maximum Pressure Stpt", "Setpoints", funct="param", dtype="float",
            prec=2, val=f"{stpt + 15:.2f}", attr=["setpt"], grpseq=3),
        _pt("SuctionPresIn", "Suction Pressure Input", "Inputs", funct="input", dtype="float",
            prec=2, val=_sv(store, "SuctionPres", f"{pres:.2f}"), grpseq=1),
        _pt("DischargePresIn", "Discharge Pressure Input", "Inputs", funct="input", dtype="float",
            prec=2, val=f"{pres + 150:.2f}", grpseq=2),
        _pt("RackEnable", "Rack Enable", "Outputs", funct="output", dtype="dig",
            val="1", selections=_dig(), grpseq=1),
        _pt("CapacityOut", "Capacity Output %", "Outputs", funct="output", dtype="float",
            prec=2, val=_sv(store, "PercentUsed", "0"), grpseq=2),
        _pt("NumStages", "Number of Stages", "Stage Setup", funct="param", dtype="uint",
            val=str(total), attr=["setpt"], min_v=1, max_v=16, grpseq=1),
        _pt("StageUpDelay", "Stage Up Delay (sec)", "Stage Setup", funct="param", dtype="uint",
            val="30", attr=["setpt"], grpseq=2),
        _pt("StageDownDelay", "Stage Down Delay (sec)", "Stage Setup", funct="param", dtype="uint",
            val="45", attr=["setpt"], grpseq=3),
        _pt("HiPresAlarm", "Hi Pressure Alarm", "Alarms", funct="param", dtype="float",
            prec=2, val=f"{stpt + 25:.2f}", attr=["setpt"], grpseq=1),
        _pt("LoPresAlarm", "Lo Pressure Alarm", "Alarms", funct="param", dtype="float",
            prec=2, val=f"{max(0, stpt - 15):.2f}", attr=["setpt"], grpseq=2),
        _pt("EnRackFailAlm", "Enable Rack Fail Alarm", "Alarms", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=3),
        _pt("ProofStatus", "Proof Status", "Proof", funct="output", dtype="dig",
            val="1", selections=_dig("Fail", "OK"), grpseq=1),
        _pt("OilPress", "Oil Pressure", "Comp Oil", funct="output", dtype="float",
            prec=2, val=f"{pres + 20:.2f}", grpseq=1),
        _pt("OilFail", "Oil Fail", "Comp Oil", funct="output", dtype="dig",
            val="0", selections=LIST_SELECTIONS["RackFail"], grpseq=2),
        _pt("NormalMode", "Normal Mode", "Normal", funct="output", dtype="dig",
            val="1", selections=_dig(), grpseq=1),
        _pt("KWDemand", "kW Demand", "Power", funct="output", dtype="float", prec=1, val="42.5", grpseq=1),
        _pt("HotGasActive", "Hot Gas Active", "Hot Gas", funct="output", dtype="dig",
            val="0", selections=_dig(), grpseq=1),
        _pt("CheckitStatus", "Checkit Status", "Checkit", funct="output", dtype="dig",
            val="1", selections=_dig("Alarm", "OK"), grpseq=1),
        _pt("CheckitAlm", "Checkit Alarm", "Checkit Alm", funct="output", dtype="dig",
            val="0", selections=_dig("Normal", "Alarm"), grpseq=1),
        _pt("ISDEnable", "ISD Enable", "ISD", funct="param", dtype="dig",
            val="0", selections=_dig("Disabled", "Enabled"), grpseq=1),
        _pt("AssocCount", "Associations", "Associations", funct="output", dtype="uint", val="0", grpseq=1),
        _pt("IOSummary", "I/O Summary", "Input/Output Status", funct="output", dtype="str",
            val="OK", attr=["lock"], grpseq=1),
        _pt("GenericAlm", "Generic Alarm", "Generic Alarms", funct="output", dtype="dig",
            val="0", selections=_dig("Normal", "Alarm"), grpseq=1),
    ]
    for i in range(1, 17):
        points.append(_pt(f"StageOut{i}", f"STAGE OUT {i}", "Stage Outs", funct="output",
                          dtype="dig", val=_sv(store, f"StageOut{i}", "0"), selections=_dig(), grpseq=i))
    return {"header": _header(name, "Enhanced Suct", groups), "points": points}


# ---------------------------------------------------------------------------
# Condenser
# ---------------------------------------------------------------------------
def build_condenser(name: str, store: dict) -> dict:
    groups = [
        _grp("Status_Group", 1), _grp("General", 2), _grp("Control", 3),
        _grp("Setpoints", 4), _grp("Fans", 5), _grp("Split", 6),
        _grp("Fast Recovery", 7), _grp("Alarms", 8), _grp("Inputs", 9),
        _grp("Outputs", 10), _grp("Associations", 11),
        _grp("Input/Output Status", 12), _grp("Generic Alarms", 13),
    ]
    points = [
        _pt("CtrlValOut", "CTRL VAL OUT", "Status_Group", funct="output", dtype="float",
            prec=2, val=_sv(store, "CtrlValOut", "212.75"), grpseq=1),
        _pt("CtrlValStpt", "CTRL VAL STPT", "Status_Group", funct="param", dtype="float",
            prec=2, val=_sv(store, "CtrlValStpt", "210.00"), attr=["setpt"], min_v=50, max_v=400, grpseq=2),
        _pt("TCtrlValOut", "T CTRL VAL OUT", "Status_Group", cls="temp", funct="output",
            dtype="float", prec=1, val=_sv(store, "TCtrlValOut", NONE_VAL), grpseq=3),
        _pt("TCtrlValStpt", "T CTRL VAL STPT", "Status_Group", cls="temp", funct="param",
            dtype="float", prec=1, val=_sv(store, "TCtrlValStpt", NONE_VAL), attr=["setpt"], grpseq=4),
        _pt("SplitValve", "SPLIT VALVE", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "SplitValve", "1"), selections=LIST_SELECTIONS["SplitValve"], grpseq=5),
        _pt("CondState", "CONDENSER STATE", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "CondState", "1"), selections=LIST_SELECTIONS["CondState"], grpseq=6),
        _pt("FastRecStpt", "FAST REC STPT", "Status_Group", funct="param", dtype="float",
            prec=2, val=_sv(store, "FastRecStpt", "325.00"), attr=["setpt"], grpseq=7),
        _pt("FastRecIn", "FAST REC IN", "Status_Group", funct="output", dtype="float",
            prec=2, val=_sv(store, "FastRecIn", "212.62"), grpseq=8),
        _pt("CtrlMethod", "CONTROL METHOD", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "CtrlMethod", "0"), selections=LIST_SELECTIONS["CtrlMethod"], grpseq=9),
        _pt("CtrlPid", "CONTROL PID", "Status_Group", funct="output", dtype="float",
            prec=2, val=_sv(store, "CtrlPid", "66.77"), grpseq=10),
        _pt("AppName", "Application Name", "General", funct="param", dtype="str", val=name, grpseq=1),
        _pt("CP^Category", "Category", "General", funct="param", dtype="str",
            val="Refrigeration", attr=["lock"], grpseq=2),
        _pt("CtrlEnable", "Control Enable", "Control", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=1),
        _pt("PidGain", "PID Gain", "Control", funct="param", dtype="float",
            prec=2, val="1.50", attr=["setpt"], grpseq=2),
        _pt("PidReset", "PID Reset", "Control", funct="param", dtype="float",
            prec=2, val="0.20", attr=["setpt"], grpseq=3),
        _pt("CtrlValStptParam", "Discharge Pressure Stpt", "Setpoints", funct="param", dtype="float",
            prec=2, val=_sv(store, "CtrlValStpt", "210.00"), attr=["setpt"], grpseq=1),
        _pt("PresDB", "Pressure Deadband", "Setpoints", funct="param", dtype="float",
            prec=2, val="5.00", attr=["setpt"], grpseq=2),
        _pt("TotalFans", "Number of Fans", "Fans", funct="param", dtype="uint",
            val="12", attr=["setpt"], grpseq=1),
        _pt("FanUpDelay", "Fan Up Delay (sec)", "Fans", funct="param", dtype="uint",
            val="20", attr=["setpt"], grpseq=2),
        _pt("FanDownDelay", "Fan Down Delay (sec)", "Fans", funct="param", dtype="uint",
            val="30", attr=["setpt"], grpseq=3),
        _pt("SplitEnable", "Split Enable", "Split", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=1),
        _pt("SplitStpt", "Split Setpoint", "Split", funct="param", dtype="float",
            prec=2, val="180.00", attr=["setpt"], grpseq=2),
        _pt("FastRecEnable", "Fast Recovery Enable", "Fast Recovery", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=1),
        _pt("FastRecStptParam", "Fast Recovery Stpt", "Fast Recovery", funct="param", dtype="float",
            prec=2, val=_sv(store, "FastRecStpt", "325.00"), attr=["setpt"], grpseq=2),
        _pt("HiDischAlm", "Hi Discharge Alarm", "Alarms", funct="param", dtype="float",
            prec=2, val="350.00", attr=["setpt"], grpseq=1),
        _pt("LoDischAlm", "Lo Discharge Alarm", "Alarms", funct="param", dtype="float",
            prec=2, val="100.00", attr=["setpt"], grpseq=2),
        _pt("DischPresIn", "Discharge Pressure In", "Inputs", funct="input", dtype="float",
            prec=2, val=_sv(store, "CtrlValOut", "212.75"), grpseq=1),
        _pt("CondEnableOut", "Condenser Enable", "Outputs", funct="output", dtype="dig",
            val="1", selections=_dig(), attr=["no_ovr"], grpseq=1),
        _pt("AssocCount", "Associations", "Associations", funct="output", dtype="uint", val="0", grpseq=1),
        _pt("IOSummary", "I/O Summary", "Input/Output Status", funct="output", dtype="str",
            val="OK", attr=["lock"], grpseq=1),
        _pt("GenericAlm", "Generic Alarm", "Generic Alarms", funct="output", dtype="dig",
            val="0", selections=_dig("Normal", "Alarm"), grpseq=1),
    ]
    for i in range(1, 13):
        points.append(_pt(f"FanOut{i}", f"FAN OUT {i}", "Fans", funct="output", dtype="dig",
                          val=_sv(store, f"FanOut{i}", "1" if i <= 4 else "0"),
                          selections=_dig(), grpseq=10 + i))
    return {"header": _header(name, "Condenser", groups), "points": points}


# ---------------------------------------------------------------------------
# RLDS
# ---------------------------------------------------------------------------
def build_rlds(name: str, store: dict) -> dict:
    groups = [
        _grp("Status_Group", 1), _grp("General", 2), _grp("Zones", 3),
        _grp("Setup", 4), _grp("Alarms", 5), _grp("Inputs", 6),
        _grp("Outputs", 7), _grp("Communications", 8),
        _grp("Associations", 9), _grp("Input/Output Status", 10),
        _grp("Generic Alarms", 11),
    ]
    points = [
        _pt("Mode", "Mode", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "Mode", "0"), selections=LIST_SELECTIONS["Mode"], grpseq=1),
        _pt("State", "State", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "State", "1"), selections=LIST_SELECTIONS["State"], grpseq=2),
        _pt("ActiveZone", "Active Zone", "Status_Group", funct="output", dtype="uint",
            val=_sv(store, "ActiveZone", "2"), grpseq=3),
        _pt("CommStatus", "COMM STATUS", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "CommStatus", "1"), selections=LIST_SELECTIONS["CommStatus"], grpseq=4),
        _pt("Online", "Online", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "Online", "1"), selections=_dig("Offline", "Online"), grpseq=5),
        _pt("PPM_LEVEL", "Refrigerant PPM", "Status_Group", funct="output", dtype="float",
            prec=0, val=_sv(store, "PPM_LEVEL", "0"), grpseq=6),
        _pt("AppName", "Application Name", "General", funct="param", dtype="str", val=name, grpseq=1),
        _pt("CP^Category", "Category", "General", funct="param", dtype="str",
            val="Refrigeration", attr=["lock"], grpseq=2),
        _pt("DeviceAddr", "Device Address", "General", funct="param", dtype="uint",
            val="1", attr=["setpt"], grpseq=3),
    ]
    for z in range(1, 5):
        points.append(_pt(f"Zone{z}PPM", f"Zone {z} PPM", "Zones", funct="output", dtype="float",
                          prec=0, val=str(0 if z != 2 else 12), grpseq=z))
        points.append(_pt(f"Zone{z}Alm", f"Zone {z} Alarm Level", "Zones", funct="param", dtype="float",
                          prec=0, val="100", attr=["setpt"], grpseq=10 + z))
    points.extend([
        _pt("SampleRate", "Sample Rate (sec)", "Setup", funct="param", dtype="uint",
            val="30", attr=["setpt"], grpseq=1),
        _pt("NumZones", "Number of Zones", "Setup", funct="param", dtype="uint",
            val="4", attr=["setpt"], grpseq=2),
        _pt("GasType", "Gas Type", "Setup", funct="param", dtype="list",
            val="0", selections=[{"key": "0", "val": "R404A"}, {"key": "1", "val": "R448A"},
                                 {"key": "2", "val": "R507"}], grpseq=3),
        _pt("AlarmPPM", "Alarm PPM Level", "Alarms", funct="param", dtype="float",
            prec=0, val="100", attr=["setpt"], grpseq=1),
        _pt("WarnPPM", "Warning PPM Level", "Alarms", funct="param", dtype="float",
            prec=0, val="50", attr=["setpt"], grpseq=2),
        _pt("EnLeakAlm", "Enable Leak Alarm", "Alarms", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=3),
        _pt("SensorIn", "Sensor Input", "Inputs", funct="input", dtype="float",
            prec=0, val=_sv(store, "PPM_LEVEL", "0"), grpseq=1),
        _pt("AlarmRelay", "Alarm Relay", "Outputs", funct="output", dtype="dig",
            val="0", selections=_dig(), attr=["no_ovr"], grpseq=1),
        _pt("HornRelay", "Horn Relay", "Outputs", funct="output", dtype="dig",
            val="0", selections=_dig(), attr=["no_ovr"], grpseq=2),
        _pt("CommBaud", "Baud Rate", "Communications", funct="param", dtype="uint",
            val="9600", attr=["setpt"], grpseq=1),
        _pt("CommProtocol", "Protocol", "Communications", funct="param", dtype="str",
            val="Modbus RTU", attr=["lock"], grpseq=2),
        _pt("AssocCount", "Associations", "Associations", funct="output", dtype="uint", val="0", grpseq=1),
        _pt("IOSummary", "I/O Summary", "Input/Output Status", funct="output", dtype="str",
            val="OK", attr=["lock"], grpseq=1),
        _pt("GenericAlm", "Generic Alarm", "Generic Alarms", funct="output", dtype="dig",
            val="0", selections=_dig("Normal", "Alarm"), grpseq=1),
    ])
    return {"header": _header(name, "RLDS", groups), "points": points}


# ---------------------------------------------------------------------------
# MULTIFLEX ESR
# ---------------------------------------------------------------------------
def build_multiflex_esr(name: str, store: dict) -> dict:
    groups = [
        _grp("Status_Group", 1), _grp("General", 2), _grp("Valves", 3),
        _grp("Setup", 4), _grp("Alarms", 5), _grp("Inputs", 6),
        _grp("Outputs", 7), _grp("Communications", 8),
        _grp("Associations", 9), _grp("Input/Output Status", 10),
        _grp("Generic Alarms", 11),
    ]
    points = [
        _pt("Online", "Online", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "Online", "1"), selections=_dig("Offline", "Online"), grpseq=9),
        _pt("AppName", "Application Name", "General", funct="param", dtype="str", val=name, grpseq=1),
        _pt("CP^Category", "Category", "General", funct="param", dtype="str",
            val="Refrigeration", attr=["lock"], grpseq=2),
        _pt("BoardAddr", "Board Address", "General", funct="param", dtype="uint",
            val="2", attr=["setpt"], grpseq=3),
        _pt("ValveCount", "Number of Valves", "Setup", funct="param", dtype="uint",
            val="8", attr=["setpt"], grpseq=1),
        _pt("UpdateRate", "Update Rate (sec)", "Setup", funct="param", dtype="uint",
            val="5", attr=["setpt"], grpseq=2),
        _pt("HiPosAlm", "Hi Position Alarm %", "Alarms", funct="param", dtype="float",
            prec=0, val="100", attr=["setpt"], grpseq=1),
        _pt("LoPosAlm", "Lo Position Alarm %", "Alarms", funct="param", dtype="float",
            prec=0, val="0", attr=["setpt"], grpseq=2),
        _pt("EnValveAlm", "Enable Valve Alarms", "Alarms", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=3),
        _pt("CommStatus", "COMM STATUS", "Communications", funct="output", dtype="dig",
            val="1", selections=LIST_SELECTIONS["CommStatus"], grpseq=1),
        _pt("AssocCount", "Associations", "Associations", funct="output", dtype="uint", val="0", grpseq=1),
        _pt("IOSummary", "I/O Summary", "Input/Output Status", funct="output", dtype="str",
            val="OK", attr=["lock"], grpseq=1),
        _pt("GenericAlm", "Generic Alarm", "Generic Alarms", funct="output", dtype="dig",
            val="0", selections=_dig("Normal", "Alarm"), grpseq=1),
    ]
    defaults = ["6.56", "8.64", "0.00", "8.27", "100.00", "100.00", "100.00", "100.00"]
    for i in range(1, 9):
        v = _sv(store, f"ValvePos{i}", defaults[i - 1])
        points.insert(i - 1, _pt(f"ValvePos{i}", f"VALVE POS {i}", "Status_Group", funct="output",
                                 dtype="float", prec=2, val=v, grpseq=i))
        points.append(_pt(f"ValvePos{i}Cmd", f"Valve {i} Command %", "Valves", funct="param",
                          dtype="float", prec=2, val=v, attr=["setpt"], min_v=0, max_v=100, grpseq=i))
        points.append(_pt(f"Valve{i}In", f"Valve {i} Feedback", "Inputs", funct="input",
                          dtype="float", prec=2, val=v, grpseq=i))
        points.append(_pt(f"Valve{i}Out", f"Valve {i} Output", "Outputs", funct="output",
                          dtype="float", prec=2, val=v, attr=["no_ovr"], grpseq=i))
    return {"header": _header(name, "MULTIFLEX ESR", groups), "points": points}


# ---------------------------------------------------------------------------
# AHULarge
# ---------------------------------------------------------------------------
def build_ahu(name: str, store: dict, *, temp_f: float = 70.0, stpt_f: float = 70.0) -> dict:
    wire = _sv(store, "ActCtrlTemp", f"{f2c(temp_f):.3f}")
    sp = _sv(store, "ActiveClStpt", f"{f2c(stpt_f):.3f}")
    groups = [
        _grp("Status_Group", 1), _grp("General", 2), _grp("Setpoints", 3),
        _grp("Economizer", 4), _grp("Stages", 5), _grp("Alarms", 6),
        _grp("Inputs", 7), _grp("Outputs", 8), _grp("Schedule", 9),
        _grp("Associations", 10), _grp("Input/Output Status", 11),
        _grp("Generic Alarms", 12),
    ]
    points = [
        _pt("ActCtrlTemp", "ACT CTRL TEMP", "Status_Group", cls="temp", funct="output",
            dtype="float", prec=1, val=wire, grpseq=1),
        _pt("ActiveClStpt", "ACTIVE SETPT", "Status_Group", cls="temp", funct="output",
            dtype="float", prec=1, val=sp, grpseq=2),
        _pt("OccState", "OCC STATE", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "OccState", "1"), selections=LIST_SELECTIONS["OccState"], grpseq=3),
        _pt("AHStatus", "AIR HANDLER STATUS", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "AHStatus", "0"), selections=LIST_SELECTIONS["AHStatus"], grpseq=4),
        _pt("ModHeatOut", "MOD HEAT OUT", "Status_Group", funct="output", dtype="float",
            prec=2, val=_sv(store, "ModHeatOut", "0.00"), grpseq=5),
        _pt("ModCoolOut", "MOD COOL OUT", "Status_Group", funct="output", dtype="float",
            prec=2, val=_sv(store, "ModCoolOut", "0.00"), grpseq=6),
        _pt("Fan", "Fan", "Status_Group", funct="output", dtype="dig",
            val=_sv(store, "Fan", "1"), selections=_dig(), grpseq=7),
        _pt("AppName", "Application Name", "General", funct="param", dtype="str", val=name, grpseq=1),
        _pt("CP^Category", "Category", "General", funct="param", dtype="str",
            val="HVAC", attr=["lock"], grpseq=2),
        _pt("SUPPLY_STPT", "Supply Temp Setpoint", "Setpoints", cls="temp", funct="param",
            dtype="float", prec=1, val=sp, attr=["setpt"], grpseq=1),
        _pt("OccCoolStpt", "Occupied Cool Stpt", "Setpoints", cls="temp", funct="param",
            dtype="float", prec=1, val=sp, attr=["setpt"], grpseq=2),
        _pt("UnoccCoolStpt", "Unoccupied Cool Stpt", "Setpoints", cls="temp", funct="param",
            dtype="float", prec=1, val=f"{f2c(stpt_f + 5):.3f}", attr=["setpt"], grpseq=3),
        _pt("OccHeatStpt", "Occupied Heat Stpt", "Setpoints", cls="temp", funct="param",
            dtype="float", prec=1, val=f"{f2c(stpt_f - 4):.3f}", attr=["setpt"], grpseq=4),
        _pt("UnoccHeatStpt", "Unoccupied Heat Stpt", "Setpoints", cls="temp", funct="param",
            dtype="float", prec=1, val=f"{f2c(stpt_f - 8):.3f}", attr=["setpt"], grpseq=5),
        _pt("EconEnable", "Economizer Enable", "Economizer", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=1),
        _pt("EconDamper", "Economizer Damper %", "Economizer", funct="output", dtype="float",
            prec=1, val="15.0", grpseq=2),
        _pt("MinOA", "Min Outdoor Air %", "Economizer", funct="param", dtype="float",
            prec=1, val="10.0", attr=["setpt"], grpseq=3),
        _pt("CoolStages", "Cool Stages", "Stages", funct="param", dtype="uint",
            val="2", attr=["setpt"], grpseq=1),
        _pt("HeatStages", "Heat Stages", "Stages", funct="param", dtype="uint",
            val="2", attr=["setpt"], grpseq=2),
        _pt("CoolStage1", "Cool Stage 1", "Stages", funct="output", dtype="dig",
            val="0", selections=_dig(), grpseq=3),
        _pt("HeatStage1", "Heat Stage 1", "Stages", funct="output", dtype="dig",
            val="1" if float(_sv(store, "ModHeatOut", "0")) > 0 else "0", selections=_dig(), grpseq=4),
        _pt("HiLim", "Supply Hi Limit", "Alarms", cls="temp", funct="param", dtype="float",
            prec=1, val=f"{f2c(stpt_f + 8):.3f}", attr=["setpt"], grpseq=1),
        _pt("LoLim", "Supply Lo Limit", "Alarms", cls="temp", funct="param", dtype="float",
            prec=1, val=f"{f2c(stpt_f - 8):.3f}", attr=["setpt"], grpseq=2),
        _pt("EnTempAlm", "Enable Temp Alarm", "Alarms", funct="param", dtype="dig",
            val="1", selections=_dig("Disabled", "Enabled"), grpseq=3),
        _pt("SupplyTempIn", "Supply Temp Sensor", "Inputs", cls="temp", funct="input",
            dtype="float", prec=1, val=wire, grpseq=1),
        _pt("ReturnTempIn", "Return Temp Sensor", "Inputs", cls="temp", funct="input",
            dtype="float", prec=1, val=f"{f2c(temp_f + 2):.3f}", grpseq=2),
        _pt("OATempIn", "Outdoor Air Temp", "Inputs", cls="temp", funct="input",
            dtype="float", prec=1, val=f"{f2c(65.0):.3f}", grpseq=3),
        _pt("CoolOut", "Cooling Output", "Outputs", funct="output", dtype="dig",
            val="1" if float(_sv(store, "ModCoolOut", "0")) > 0 else "0",
            selections=_dig(), attr=["no_ovr"], grpseq=1),
        _pt("HeatOut", "Heating Output", "Outputs", funct="output", dtype="dig",
            val="1" if float(_sv(store, "ModHeatOut", "0")) > 0 else "0",
            selections=_dig(), attr=["no_ovr"], grpseq=2),
        _pt("FanOut", "Supply Fan", "Outputs", funct="output", dtype="dig",
            val=_sv(store, "Fan", "1"), selections=_dig(), attr=["no_ovr"], grpseq=3),
        _pt("SchedState", "Schedule State", "Schedule", funct="output", dtype="dig",
            val="1", selections=LIST_SELECTIONS["SchedState"], grpseq=1),
        _pt("OccSchedule", "Occupied Schedule", "Schedule", funct="param", dtype="str",
            val="Mon-Sat 05:30-22:30", attr=["setpt"], grpseq=2),
        _pt("AssocCount", "Associations", "Associations", funct="output", dtype="uint", val="0", grpseq=1),
        _pt("IOSummary", "I/O Summary", "Input/Output Status", funct="output", dtype="str",
            val="OK", attr=["lock"], grpseq=1),
        _pt("GenericAlm", "Generic Alarm", "Generic Alarms", funct="output", dtype="dig",
            val="0", selections=_dig("Normal", "Alarm"), grpseq=1),
    ]
    return {"header": _header(name, "AHULarge", groups), "points": points}


# ---------------------------------------------------------------------------
# Generic / System / Other — Status from DASHBOARD + Setup/Alarms
# ---------------------------------------------------------------------------
def build_from_dashboard(name: str, apptype: str, store: dict) -> dict:
    dash = DASHBOARD.get(apptype) or {"points": []}
    groups = [
        _grp("Status_Group", 1), _grp("General", 2), _grp("Setup", 3),
        _grp("Alarms", 4), _grp("Inputs", 5), _grp("Outputs", 6),
        _grp("Associations", 7), _grp("Input/Output Status", 8),
        _grp("Generic Alarms", 9),
    ]
    # Extra groups by type
    if apptype == "SerialPortConfig":
        groups.insert(3, _grp("COM Ports", 3))
    elif apptype == "SystemSettings":
        groups.insert(3, _grp("SystemSettings", 3))
    elif apptype == "Log Group":
        groups.insert(3, _grp("Logging", 3))
    elif apptype in ("16 Analog Inputs", "8 Relay Outputs"):
        groups.insert(3, _grp("Channels", 3))
    elif apptype == "TimeSchedule":
        groups.insert(3, _grp("Events", 3))
    elif apptype == "Lighting":
        groups.insert(3, _grp("Lighting", 3))

    points = [
        _pt("AppName", "Application Name", "General", funct="param", dtype="str", val=name, grpseq=1),
        _pt("CP^Category", "Category", "General", funct="param", dtype="str",
            val=_sv(store, "CP^Category", "System"), attr=["lock"], grpseq=2),
        _pt("DisplayStatus", "Status", "Status_Group", funct="output", dtype="str",
            val=_sv(store, "DisplayStatus", "Online"), attr=["lock"], grpseq=99),
        _pt("AssocCount", "Associations", "Associations", funct="output", dtype="uint", val="0", grpseq=1),
        _pt("IOSummary", "I/O Summary", "Input/Output Status", funct="output", dtype="str",
            val="OK", attr=["lock"], grpseq=1),
        _pt("GenericAlm", "Generic Alarm", "Generic Alarms", funct="output", dtype="dig",
            val="0", selections=_dig("Normal", "Alarm"), grpseq=1),
    ]
    seq = 1
    for p in dash.get("points") or []:
        pid = p["pid"]
        dtype = p.get("dtype") or "float"
        cls = p.get("class") or ""
        val = _sv(store, pid, "0")
        sels = LIST_SELECTIONS.get(pid)
        if dtype == "dig" and not sels:
            sels = _dig()
        points.append(_pt(
            pid, p.get("name") or pid, "Status_Group",
            cls=cls, funct="output", dtype=dtype if dtype != "list" else "dig",
            prec=p.get("prec", 1), val=val, selections=sels, grpseq=seq,
        ))
        seq += 1

    if apptype == "SerialPortConfig":
        points.extend([
            _pt("BaudRate", "Baud Rate", "COM Ports", funct="param", dtype="uint",
                val=_sv(store, "BaudRate", "38400"), attr=["setpt"], grpseq=1),
            _pt("PortName", "Port Name", "COM Ports", funct="param", dtype="str",
                val=_sv(store, "PortName", name), grpseq=2),
            _pt("Parity", "Parity", "COM Ports", funct="param", dtype="list",
                val="0", selections=[{"key": "0", "val": "None"}, {"key": "1", "val": "Even"},
                                     {"key": "2", "val": "Odd"}], grpseq=3),
        ])
    elif apptype == "SystemSettings":
        points.extend([
            _pt("SiteName", "Site Name", "SystemSettings", funct="param", dtype="str",
                val=_sv(store, "SiteName", SITE["SiteName"]), attr=["setpt"], grpseq=1),
            _pt("UnitName", "Unit Name", "SystemSettings", funct="param", dtype="str",
                val=_sv(store, "UnitName", SITE["unitname"]), attr=["setpt"], grpseq=2),
            _pt("EngUnits", "Engineering Units", "SystemSettings", funct="param", dtype="str",
                val="fahren", attr=["setpt"], grpseq=3),
        ])
    elif apptype == "Log Group":
        points.extend([
            _pt("LogInterval", "Log Interval (sec)", "Logging", funct="param", dtype="uint",
                val=_sv(store, "LogInterval", "60"), attr=["setpt"], grpseq=1),
            _pt("LogDuration", "Log Duration (hr)", "Logging", funct="param", dtype="uint",
                val="48", attr=["setpt"], grpseq=2),
            _pt("PercentUsed", "PERCENT USED", "Logging", funct="output", dtype="float",
                prec=1, val=_sv(store, "PercentUsed", "12.5"), grpseq=3),
        ])
    elif apptype == "16 Analog Inputs":
        for i in range(1, 17):
            points.append(_pt(f"AI{i}", f"AI {i}", "Channels", cls="temp", funct="input",
                              dtype="float", prec=1,
                              val=_sv(store, f"AI{i}", f"{f2c(72.0 + i * 0.1):.3f}"), grpseq=i))
    elif apptype == "8 Relay Outputs":
        for i in range(1, 9):
            points.append(_pt(f"RO{i}", f"RO {i}", "Channels", funct="output", dtype="dig",
                              val=_sv(store, f"RO{i}", "0"), selections=_dig(), grpseq=i))
    elif apptype == "TimeSchedule":
        points.extend([
            _pt("Event1", "Event 1", "Events", funct="param", dtype="str",
                val="Mon-Fri ON 06:00 OFF 22:00", attr=["setpt"], grpseq=1),
            _pt("Event2", "Event 2", "Events", funct="param", dtype="str",
                val="Sat ON 07:00 OFF 23:00", attr=["setpt"], grpseq=2),
            _pt("Event3", "Event 3", "Events", funct="param", dtype="str",
                val="Sun ON 08:00 OFF 21:00", attr=["setpt"], grpseq=3),
        ])
    elif apptype == "Lighting":
        points.extend([
            _pt("LightsOutput", "LIGHTS OUTPUT", "Lighting", funct="output", dtype="dig",
                val=_sv(store, "LightsOutput", "1"), selections=_dig(), grpseq=1),
            _pt("DimLevel", "Dim Level %", "Lighting", funct="param", dtype="float",
                prec=0, val="100", attr=["setpt"], grpseq=2),
        ])
    elif apptype == "Analog Sensor":
        points.extend([
            _pt("SENSOR_STPT", "Sensor Setpoint", "Setup", cls="temp", funct="param",
                dtype="float", prec=1, val=_sv(store, "SENSOR_STPT", f"{f2c(72):.3f}"),
                attr=["setpt"], grpseq=1),
            _pt("HiLimit", "Hi Limit", "Alarms", cls="temp", funct="param", dtype="float",
                prec=1, val=f"{f2c(85):.3f}", attr=["setpt"], grpseq=1),
            _pt("LoLimit", "Lo Limit", "Alarms", cls="temp", funct="param", dtype="float",
                prec=1, val=f"{f2c(50):.3f}", attr=["setpt"], grpseq=2),
        ])
    elif apptype == "AreaCtrl":
        points.extend([
            _pt("UnitName", "UNIT NAME", "Setup", funct="param", dtype="str",
                val=_sv(store, "UnitName", SITE["unitname"]), attr=["setpt"], grpseq=1),
            _pt("UnitNumber", "UNIT NUMBER", "Setup", funct="param", dtype="uint",
                val=_sv(store, "UnitNumber", "1"), attr=["setpt"], grpseq=2),
            _pt("FwVersion", "Firmware", "Setup", funct="output", dtype="str",
                val=SITE["unitversion"], attr=["lock"], grpseq=3),
        ])

    # Setup catch-all
    points.append(_pt("Enabled", "Enabled", "Setup", funct="param", dtype="dig",
                      val="1", selections=_dig("Disabled", "Enabled"), grpseq=90))
    return {"header": _header(name, apptype, groups), "points": points}


BUILDERS: dict[str, Callable[..., dict]] = {
    "StdCircuit": build_std_circuit,
    "Enhanced Suct": build_enhanced_suct,
    "Condenser": build_condenser,
    "RLDS": build_rlds,
    "MULTIFLEX ESR": build_multiflex_esr,
    "AHULarge": build_ahu,
}


def build_description(
    *,
    iid: str,
    name: str,
    apptype: str,
    store: dict[str, str],
    pt=None,
) -> dict[str, Any]:
    """Return {header, points} for GetAppDescription."""
    store = dict(store or {})
    if apptype == "StdCircuit":
        ctrl = getattr(pt, "value", 30.0) if pt else 30.0
        stpt = getattr(pt, "setpoint", ctrl) if pt else ctrl
        desc = build_std_circuit(name, store, ctrl_f=ctrl, stpt_f=stpt)
    elif apptype == "Enhanced Suct":
        pres = getattr(pt, "value", 40.0) if pt else float(store.get("SuctionPres") or 40)
        stpt = getattr(pt, "setpoint", 40.0) if pt else float(store.get("CurPresStpt") or 40)
        desc = build_enhanced_suct(name, store, pres=pres, stpt=stpt)
    elif apptype == "Condenser":
        desc = build_condenser(name, store)
    elif apptype == "RLDS":
        desc = build_rlds(name, store)
    elif apptype == "MULTIFLEX ESR":
        desc = build_multiflex_esr(name, store)
    elif apptype == "AHULarge":
        temp = getattr(pt, "value", 70.0) if pt else 70.0
        stpt = getattr(pt, "setpoint", 70.0) if pt else 70.0
        desc = build_ahu(name, store, temp_f=temp, stpt_f=stpt)
    elif apptype == "Analog Sensor":
        # keep dedicated thin path via dashboard builder (includes sensor setpoints)
        desc = build_from_dashboard(name, apptype, store)
    else:
        desc = build_from_dashboard(name, apptype, store)

    # Deduplicate pids (keep first) — SPA point map is keyed by pid
    seen = set()
    uniq = []
    for p in desc["points"]:
        pid = p.get("pid")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        uniq.append(p)
    desc["points"] = uniq
    return desc
