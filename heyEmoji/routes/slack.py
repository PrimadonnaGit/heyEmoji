from pprint import pprint

from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from slack_sdk import WebClient
from dataclasses import asdict
import re
from sqlalchemy.sql import func
from sqlalchemy import text
from heyEmoji.database.conn import db
from heyEmoji.common.config import conf
from heyEmoji.database.schema import User, Reaction
from heyEmoji.models import SlackEventHook
from datetime import datetime
from pprint import pprint

conf_dict = asdict(conf())

client = WebClient(token=conf_dict.get("BOT_USER_OAUTH_TOKEN"))
router = APIRouter()
users_store = {}


# TODO:
# 1. Daily Reaction 초기화
# 2. 전체 멤버의 받은/보낸 개수 홈화면 표시

# service
def save_users_from_slack_api():
    users = User.get_all()
    for user in users:
        users_store[user.slack_id] = user.as_dict()


@router.on_event("startup")
async def startup_event():
    save_users_from_slack_api()  # 로컬 스토리지 활용 유저정보 저장


@router.get("/init")
async def init_user(session: Session = Depends(db.session)):
    result = client.users_list()
    for user in result["members"]:
        if not user.get('is_bot'):
            User.create(session=session,
                        auto_commit=True,
                        username=user.get('profile').get('display_name'),
                        slack_id=user.get("id"),
                        avatar_url=user.get('profile').get('image_32'))
    return Response(status_code=200)


@router.post("/events")
async def action_endpoint(event_hook: SlackEventHook, session: Session = Depends(db.session)):
    channel = event_hook.event.channel
    from_user = event_hook.event.user
    send_text = event_hook.event.text
    event_type = event_hook.event.type

    if event_type == 'url_verification':
        return JSONResponse(status_code=200, content=dict(challenge=event_hook.challenge))
    elif event_type == 'app_home_opened':
        sub_query1 = session.query(Reaction.to_user, func.sum(Reaction.count).label('count')).group_by(
            Reaction.to_user).subquery('received_reaction')
        sub_query2 = session.query(Reaction.from_user, func.sum(Reaction.count).label('count')).group_by(
            Reaction.from_user).subquery('send_reaction')

        user_count = session \
            .query(User.id, User.username, User.my_reaction,
                   func.coalesce(sub_query1.c.count, 0).label('received_reaction'),
                   func.coalesce(sub_query2.c.count, 0).label('send_reaction')) \
            .outerjoin(sub_query1, sub_query1.c.to_user == User.id) \
            .outerjoin(sub_query2, sub_query2.c.from_user == User.id) \
            .order_by(text('received_reaction desc')) \
            .all()

        view_text = '\n'.join(
            [f'{uc.username} : {uc.my_reaction}/{uc.received_reaction}/{uc.send_reaction}' for uc in user_count])

        result = client.views_publish(
            user_id=from_user,
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Welcome home, <@{}> :house:*\n 남은 이모지/받은 이모지/보낸 이모지".format(from_user),
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": view_text,
                            }
                        ],
                    },
                    {"type": "divider"},
                ],
            },
        )
        return JSONResponse(status_code=200, content=dict(msg="ok"))

    else:
        if not from_user in users_store.keys():
            # bot event
            return JSONResponse(status_code=200, content=dict(msg="ok"))

    from_user_display_name = users_store[from_user].get('username')
    from_user_id = users_store[from_user].get('id')

    to_users = re.findall(r'\<\@\S+\>', send_text)
    to_users = set(to_users)

    if to_users and conf_dict.get("EMOJI") in send_text:  # emoji 확인
        emoji_count = send_text.count(conf_dict.get("EMOJI"))
        for to_user in to_users:
            # 남은 갯수 리마인드
            from_user_db = User.get(session=session, id=from_user_id)

            if from_user_db.my_reaction >= emoji_count:
                from_user_db.my_reaction -= emoji_count
                to_user_id = users_store[to_user[2:-1]].get('id')
                # 전송 확인
                now = datetime.now()
                Reaction.create(session=session,
                                auto_commit=True,
                                year=now.year,
                                month=now.month,
                                to_user=to_user_id,
                                from_user=from_user_id,
                                type=conf_dict.get("EMOJI"),
                                count=emoji_count)
                # 선물 메세지
                client.chat_postMessage(channel=channel,
                                        text=f"{from_user_display_name}님이 {to_user}님에게 이모지를 {emoji_count}개 선물하셨습니다.")

                # 확인 메세지
                client.chat_postMessage(channel=from_user,
                                        text=f"{from_user_display_name}님이 오늘 선물 가능한 이모지 개수는 {from_user_db.my_reaction}개 입니다.")
            else:
                client.chat_postMessage(channel=from_user,
                                        text=f"{from_user_display_name}님은 오늘 선물 가능한 이모지를 모두 소진하셨습니다.")
    else:
        return JSONResponse(status_code=200, content=dict(msg="normal"))
