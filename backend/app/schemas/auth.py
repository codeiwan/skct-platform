from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skala_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("skala_id", "name", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("skala_id")
    @classmethod
    def validate_skala_id(cls, value: str) -> str:
        if len(value.casefold()) > 64:
            raise ValueError(
                "SKALA 고유번호는 정규화 후 64자를 초과할 수 없습니다."
            )
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if value.isspace():
            raise ValueError(
                "비밀번호를 공백만으로 구성할 수 없습니다."
            )
        return value


class RegisterResponse(BaseModel):
    id: int
    skala_id: str
    name: str
    status: Literal["PENDING"]
