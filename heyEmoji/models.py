from pydantic import BaseModel
from typing import Optional, List


# about User
class User(BaseModel):
    id: int
    username: str
    slack_id: str
    my_reaction: int

    class Config:
        orm_mode = True


class UserCreate(BaseModel):
    username: str
    slack_id: str
    avatar_url: str


class UserReaction(BaseModel):
    username: str
    slack_id: str
    avatar_url: str
    my_reaction: int
    total_reaction: int


# about Reaction
class Reaction(BaseModel):
    id: int
    year: int
    month: int
    to_user: int
    from_user: int
    type: str
    count: int

    class Config:
        orm_mode = True


class ReactionCreate(BaseModel):
    year: int
    month: int
    to_user: int
    from_user: int
    type: str


class SlackEvent(BaseModel):
    type: str
    user: Optional[str] = ""
    channel: Optional[str] = ""
    text: Optional[str] = ""


# ETC
class SlackEventHook(BaseModel):
    token: str
    type: str
    challenge: Optional[str] = None
    team_id: Optional[str] = None
    api_app_id: Optional[str] = None
    event: Optional[SlackEvent] = None
    authorizations: Optional[List[dict]] = None
    event_context: Optional[str] = None
    event_id: Optional[str] = None
    event_time: Optional[int] = None
