from pydantic import BaseModel, Field


class Rule(BaseModel):
    name: str
    full_path: str = Field(alias="fullPath")
    partition: str
    definition: str = Field("", alias="apiAnonymous")


class Rules(BaseModel):
    items: list[Rule] = Field(default_factory=list)
