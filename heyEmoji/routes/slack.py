import re
from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends
from slack_sdk import WebClient
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from starlette.responses import JSONResponse

from heyEmoji.common.config import conf
from heyEmoji.database.conn import db
from heyEmoji.database.schema import Reaction, User
from heyEmoji.models import SlackEventHook

conf_dict = asdict(conf())

client = WebClient(token=conf_dict.get("BOT_USER_OAUTH_TOKEN"))
router = APIRouter()


@router.on_event("startup")
async def init_user_startup():
    """
        workspace 유저 목록을 db에 초기화
    :return:
    """
    result = client.users_list()
    for user in result["members"]:
        if not user.get('is_bot'):
            if user.get('profile').get('display_name') and user.get("id") is not 'USLACKBOT':
                User.create(
                    auto_commit=True,
                    username=user.get('profile').get('display_name'),
                    slack_id=user.get("id"),
                    avatar_url=user.get('profile').get('image_32'))


@router.get("/users")
async def get_users(session: Session = Depends(db.session)):
    """
    유저 현황
    :param session: db session
    :return:
    """
    users = User.get_all(session=session)
    return JSONResponse(status_code=200, content=dict(user=[user.as_dict() for user in users]))


@router.get("/reactions")
async def get_users(session: Session = Depends(db.session)):
    """
    리액션 현황
    :param session: db session
    :return:
    """
    reactions = Reaction.get_all(session=session)
    return JSONResponse(status_code=200, content=dict(reaction=[reaction.as_dict() for reaction in reactions]))


@router.post("/events")
async def action_endpoint(event_hook: SlackEventHook, session: Session = Depends(db.session)):
    from_user = event_hook.event.user

    if event_hook.type == 'url_verification':  # slack event subscription verify
        return JSONResponse(status_code=200, content=dict(challenge=event_hook.challenge))
    elif event_hook.event.type == 'app_home_opened':  # slack app home

        sub_query1 = session.query(Reaction.to_user, func.sum(Reaction.count).label('count')).group_by(
            Reaction.to_user).subquery('received_reaction')
        sub_query2 = session.query(Reaction.from_user, func.sum(Reaction.count).label('count')).group_by(
            Reaction.from_user).subquery('send_reaction')

        user_count = session \
            .query(User.id, User.slack_id, User.username, User.today_reaction,
                   func.coalesce(sub_query1.c.count, 0).label('received_reaction'),
                   func.coalesce(sub_query2.c.count, 0).label('send_reaction')) \
            .outerjoin(sub_query1, sub_query1.c.to_user == User.id) \
            .outerjoin(sub_query2, sub_query2.c.from_user == User.id) \
            .order_by(text('received_reaction desc')) \
            .all()

        ranking_view_text = '\n'.join(
            [
                f'{uc.username} : 받은 {conf_dict.get("EMOJI")} {uc.received_reaction} 보낸 {conf_dict.get("EMOJI")} {uc.send_reaction}'
                for uc in user_count])

        personal_view_text = ''
        for uc in user_count:
            if uc.slack_id == from_user:
                personal_view_text += f'남은 {conf_dict.get("EMOJI")} : {uc.today_reaction}개 \n'
                personal_view_text += f'받은 {conf_dict.get("EMOJI")} : {uc.received_reaction}개 \n'
                personal_view_text += f'보낸 {conf_dict.get("EMOJI")} : {uc.send_reaction}개'

        client.views_publish(
            user_id=from_user,
            view={
                "type": "home",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ":waving-from-afar-left: 헤이 이모지로 당신의 감사를 표현하세요! :waving-from-afar-right:",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "\n*나의 현황*",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": personal_view_text,
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "\n*전체 순위표*"
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": ranking_view_text,
                            }
                        ],
                    },
                    {"type": "divider"},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "Developed by Primadonna",
                            }
                        ],
                    },
                ],
            },
        )
        return JSONResponse(status_code=200, content=dict(msg="ok"))

    else:  # normal event
        send_text = event_hook.event.text

        from_user_db = User.get(session=session, slack_id=from_user)
        if not from_user_db:
            return JSONResponse(status_code=200)
        from_user_id = from_user_db.id

        to_users = re.findall(r'\<\@\S+\>', send_text)
        to_users = set(to_users)

        if to_users and conf_dict.get("EMOJI") in send_text:  # emoji 확인
            emoji_count = send_text.count(conf_dict.get("EMOJI"))

            for to_user in to_users:
                # 남은 갯수 리마인드
                from_user_db = User.get(session=session, id=from_user_id)

                if from_user_db.today_reaction >= emoji_count:
                    from_user_db.today_reaction -= emoji_count
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
                    # 보낸 메세지
                    client.chat_postMessage(channel=from_user,
                                            text=f"{to_user}님에게 이모지를 {emoji_count}개 선물하셨습니다. 남은 이모지는 {from_user_db.today_reaction}개 입니다.")
                    # 받은 메세지
                    client.chat_postMessage(channel=to_user[2:-1],
                                            text=f"<@{from_user}>님이 이모지를 {emoji_count}개 선물하셨습니다.")
                else:
                    client.chat_postMessage(channel=from_user,
                                            text=f"<@{from_user}>님은 오늘 선물 가능한 이모지를 모두 소진하셨습니다.")

    return JSONResponse(status_code=200)
