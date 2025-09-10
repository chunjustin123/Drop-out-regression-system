from pydantic import BaseSettings, Field
from typing import Optional


class AppSettings(BaseSettings):
    timezone: str = Field(default="Asia/Colombo")
    slack_bot_token: Optional[str] = None
    slack_channel_id: Optional[str] = None
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    parent_sms_country_prefix: str = Field(default="+1")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = AppSettings()
