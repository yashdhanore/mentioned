from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PushPlatformValue = Literal["ios", "android"]


class RegisterPushTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expo_push_token: str = Field(min_length=1, max_length=512)
    platform: PushPlatformValue


class RegisterPushTokenResponse(BaseModel):
    registered: bool


class DisablePushTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expo_push_token: str = Field(min_length=1, max_length=512)


class DisablePushTokenResponse(BaseModel):
    disabled: bool
