from dataclasses import asdict

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from heyEmoji.common.config import conf
from heyEmoji.database.conn import db
from heyEmoji.routes import index, scheduler, slack


def create_app():
    """
    앱 함수 실행
    :return: app : FastAPI instance
    """
    # Config
    c = conf()
    conf_dict = asdict(conf())
    # APP
    app = FastAPI()
    # DB

    db.init_app(app, **conf_dict)

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=c.ALLOW_SITE,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Router
    app.include_router(index.router)
    app.include_router(scheduler.router, tags=["Scheduler"], prefix="/scheduler")
    app.include_router(slack.router, tags=["Slack"], prefix="/slack")

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
