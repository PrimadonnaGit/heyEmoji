import re
from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends
from slack_sdk import WebClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from starlette.responses import JSONResponse, Response

from heyEmoji.common.config import conf
from heyEmoji.database.conn import db
from heyEmoji.database.schema import Reaction, User
from heyEmoji.models import SlackEventHook

conf_dict = asdict(conf())

client = WebClient(token=conf_dict.get("BOT_USER_OAUTH_TOKEN"))
router = APIRouter()


@router.get("/users")
async def get_users(session: Session = Depends(db.session)):
    users = User.get_all()
    return JSONResponse(status_code=200, content=dict(user=[user.as_dict() for user in users]))


@router.get("/reactions")
async def get_users(session: Session = Depends(db.session)):
    reactions = Reaction.get_all()
    return JSONResponse(status_code=200, content=dict(reaction=[reaction.as_dict() for reaction in reactions]))


@router.get("/init")
async def init_user(session: Session = Depends(db.session)):
    result = client.users_list()
    for user in result["members"]:
        if not user.get('is_bot'):
            if user.get('profile').get('display_name') and user.get('profile').get('display_name') is not 'Slackbot':
                User.create(session=session,
                            auto_commit=True,
                            username=user.get('profile').get('display_name'),
                            slack_id=user.get("id"),
                            avatar_url=user.get('profile').get('image_32'))
    return Response(status_code=200)


@router.post("/events")
async def action_endpoint(event_hook: SlackEventHook, session: Session = Depends(db.session)):
    event_type = event_hook.type

    if event_type == 'url_verification':
        return JSONResponse(status_code=200, content=dict(challenge=event_hook.challenge))
    elif event_type == 'app_home_opened':
        from_user = event_hook.event.user

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
        channel = event_hook.event.channel
        from_user = event_hook.event.user
        send_text = event_hook.event.text

        from_user_db = User.get(session=session, slack_id=from_user)
        from_user_display_name = from_user_db.username
        from_user_id = from_user_db.id

        to_users = re.findall(r'\<\@\S+\>', send_text)
        to_users = set(to_users)

        if to_users and conf_dict.get("EMOJI") in send_text:  # emoji 확인
            emoji_count = send_text.count(conf_dict.get("EMOJI"))
            for to_user in to_users:
                # 남은 갯수 리마인드
                from_user_db = User.get(session=session, id=from_user_id)

                if from_user_db.my_reaction >= emoji_count:
                    from_user_db.my_reaction -= emoji_count
                    to_user_db = User.get(session=session, slack_id=to_user[2:-1])
                    to_user_id = to_user_db.id
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

    return JSONResponse(status_code=200)
