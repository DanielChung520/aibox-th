from pydantic import BaseModel
from typing import Optional


class LINEChannel(BaseModel):
    _key: str
    official_account_key: str
    channel_name: str
    channel_id: str
    channel_secret: Optional[str] = None
    channel_access_token: Optional[str] = None
    webhook_url: str
    webhook_enabled: bool = False
    bot_user_id: Optional[str] = None
    publication_status: str = "unpublished"
    published_bot_key: Optional[str] = None
    published_bot_name: Optional[str] = None
    last_connected_at: Optional[str] = None
    created_at: str


class LINEOfficialAccount(BaseModel):
    _key: str
    provider_name: str
    name: str
    status: str = "active"
    channels: list[LINEChannel] = []
    created_at: str
    updated_at: str


class CreateOfficialAccountRequest(BaseModel):
    provider_name: str
    name: str


class CreateChannelRequest(BaseModel):
    channel_name: str
    channel_id: str
    channel_secret: str
    channel_access_token: str
    channel_icon: Optional[str] = None
    channel_description: Optional[str] = None


class UpdateChannelRequest(BaseModel):
    channel_name: Optional[str] = None
    channel_id: Optional[str] = None
    channel_secret: Optional[str] = None
    channel_access_token: Optional[str] = None
    webhook_enabled: Optional[bool] = None
    channel_icon: Optional[str] = None
    channel_description: Optional[str] = None


class PublishChannelRequest(BaseModel):
    bot_key: str
    greeting: Optional[str] = None
    delay: Optional[int] = 0


class TestConnectionResult(BaseModel):
    success: bool
    bot_user_id: Optional[str] = None
    error: Optional[str] = None