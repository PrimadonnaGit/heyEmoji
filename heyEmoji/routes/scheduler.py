from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import APIRouter

from heyEmoji.database.schema import User

router = APIRouter()


def reset_user_today_reaction():
    User.filter().update(auto_commit=True, today_reaction=5)


@router.on_event("startup")
async def set_scheduler():
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    scheduler.add_job(reset_user_today_reaction, 'cron', hour='0')
    scheduler.start()
    print("scheduler start")
