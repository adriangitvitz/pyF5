# ruff: noqa: FA100
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StatValue(BaseModel):
    value: int


class StatDescription(BaseModel):
    description: str


class VirtualServerStatEntries(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    actual_pva_accel: Optional[str] = Field(None, alias="actualPvaAccel")

    clientside_bits_in: Optional[int] = Field(None, alias="clientside.bitsIn")
    clientside_bits_out: Optional[int] = Field(None, alias="clientside.bitsOut")
    clientside_cur_conns: Optional[int] = Field(None, alias="clientside.curConns")
    clientside_evicted_conns: Optional[int] = Field(
        None, alias="clientside.evictedConns"
    )
    clientside_max_conns: Optional[int] = Field(None, alias="clientside.maxConns")
    clientside_pkts_in: Optional[int] = Field(None, alias="clientside.pktsIn")
    clientside_pkts_out: Optional[int] = Field(None, alias="clientside.pktsOut")
    clientside_slow_killed: Optional[int] = Field(None, alias="clientside.slowKilled")
    clientside_tot_conns: Optional[int] = Field(None, alias="clientside.totConns")

    cmp_enable_mode: Optional[str] = Field(None, alias="cmpEnableMode")
    cmp_enabled: Optional[str] = Field(None, alias="cmpEnabled")

    cs_max_conn_dur: Optional[int] = Field(None, alias="csMaxConnDur")
    cs_mean_conn_dur: Optional[int] = Field(None, alias="csMeanConnDur")
    cs_min_conn_dur: Optional[int] = Field(None, alias="csMinConnDur")

    destination: Optional[str] = Field(None, alias="destination")

    ephemeral_bits_in: Optional[int] = Field(None, alias="ephemeral.bitsIn")
    ephemeral_bits_out: Optional[int] = Field(None, alias="ephemeral.bitsOut")
    ephemeral_cur_conns: Optional[int] = Field(None, alias="ephemeral.curConns")
    ephemeral_evicted_conns: Optional[int] = Field(None, alias="ephemeral.evictedConns")
    ephemeral_max_conns: Optional[int] = Field(None, alias="ephemeral.maxConns")
    ephemeral_pkts_in: Optional[int] = Field(None, alias="ephemeral.pktsIn")
    ephemeral_pkts_out: Optional[int] = Field(None, alias="ephemeral.pktsOut")
    ephemeral_slow_killed: Optional[int] = Field(None, alias="ephemeral.slowKilled")
    ephemeral_tot_conns: Optional[int] = Field(None, alias="ephemeral.totConns")

    five_min_avg_usage_ratio: Optional[int] = Field(None, alias="fiveMinAvgUsageRatio")
    five_sec_avg_usage_ratio: Optional[int] = Field(None, alias="fiveSecAvgUsageRatio")
    one_min_avg_usage_ratio: Optional[int] = Field(None, alias="oneMinAvgUsageRatio")

    mr_msg_in: Optional[int] = Field(None, alias="mr.msgIn")
    mr_msg_out: Optional[int] = Field(None, alias="mr.msgOut")
    mr_req_in: Optional[int] = Field(None, alias="mr.reqIn")
    mr_req_out: Optional[int] = Field(None, alias="mr.reqOut")
    mr_resp_in: Optional[int] = Field(None, alias="mr.respIn")
    mr_resp_out: Optional[int] = Field(None, alias="mr.respOut")

    status_availability_state: Optional[str] = Field(
        None, alias="status.availabilityState"
    )
    status_enabled_state: Optional[str] = Field(None, alias="status.enabledState")
    status_status_reason: Optional[str] = Field(None, alias="status.statusReason")

    syncookie_accepts: Optional[int] = Field(None, alias="syncookie.accepts")
    syncookie_hw_accepts: Optional[int] = Field(None, alias="syncookie.hwAccepts")
    syncookie_hw_syncookies: Optional[int] = Field(None, alias="syncookie.hwSyncookies")
    syncookie_hwsyncookie_instance: Optional[int] = Field(
        None, alias="syncookie.hwsyncookieInstance"
    )
    syncookie_rejects: Optional[int] = Field(None, alias="syncookie.rejects")
    syncookie_swsyncookie_instance: Optional[int] = Field(
        None, alias="syncookie.swsyncookieInstance"
    )
    syncookie_syncache_curr: Optional[int] = Field(None, alias="syncookie.syncacheCurr")
    syncookie_syncache_over: Optional[int] = Field(None, alias="syncookie.syncacheOver")
    syncookie_syncookies: Optional[int] = Field(None, alias="syncookie.syncookies")

    syncookie_status: Optional[str] = Field(None, alias="syncookieStatus")
    tm_name: Optional[str] = Field(None, alias="tmName")
    tot_requests: Optional[int] = Field(None, alias="totRequests")

    @model_validator(mode="before")
    @classmethod
    def unwrap_entries(cls, data: dict) -> dict:
        return {
            key: (entry.get("value") if "value" in entry else entry.get("description"))
            for key, entry in data.items()
        }


class NestedStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entries: VirtualServerStatEntries
    kind: Optional[str] = None
    self_link: Optional[str] = Field(None, alias="selfLink")


class VirtualServerStats(BaseModel):
    nested_stats: NestedStats = Field(alias="nestedStats")


class VirtualServerStatsResponse(BaseModel):
    entries: dict[str, VirtualServerStats]

    @classmethod
    def from_api(cls, data: dict) -> "VirtualServerStatsResponse":
        return cls(
            entries={
                url: VirtualServerStats.model_validate(stat)
                for url, stat in data.items()
            }
        )
