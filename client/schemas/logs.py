import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

SEVERITIES = ("emerg", "alert", "crit", "err", "warning", "notice", "info", "debug")

LINE = re.compile(
    r"^(?P<facility>\S+) (?P<timestamp>\S+Z) (?P<severity>\w+) (?P<host>\S+) "
    r"(?P<process>[\w.-]+?)(?:\[(?P<pid>\d+)\])?: (?P<message>.*)$"
)


class LogEntry(BaseModel):
    facility: str
    timestamp: datetime
    severity: str
    host: str
    process: str
    pid: Optional[int] = None
    message: str
    raw: str

    @property
    def level(self) -> int:
        return (
            SEVERITIES.index(self.severity)
            if self.severity in SEVERITIES
            else len(SEVERITIES)
        )


class LogsResponse(BaseModel):
    api_raw_values: dict[str, str] = Field(default_factory=dict, alias="apiRawValues")

    @property
    def lines(self) -> list[str]:
        text = next(iter(self.api_raw_values.values()), "")
        return text.splitlines()

    @property
    def entries(self) -> list[LogEntry]:
        entries = []
        for line in self.lines:
            line = line.strip()
            if m := LINE.match(line):
                entries.append(LogEntry(**m.groupdict(), raw=line))
        return entries
