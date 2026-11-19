from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class F1ConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=512)
    remember_credentials: bool = True
    personal_use_acknowledged: bool


class BrowserConnectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    personal_use_acknowledged: bool
