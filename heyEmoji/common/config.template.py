"""
Please Replace your own

* BOT_USER_OAUTH_TOKEN : slack bot token
* DB_URL: your database

"""

from dataclasses import dataclass
from os import environ, path

base_dir = path.dirname(path.dirname(path.dirname(path.abspath(__file__))))


@dataclass
class Config:
    """
    Basic Configuration
    """

    BASE_DIR = base_dir
    DB_POOL_RECYCLE: int = 900
    DB_ECHO: bool = False
    BOT_USER_OAUTH_TOKEN: str = "BOT_USER_OAUTH_TOKEN"
    EMOJI: str = ":love:"


@dataclass
class LocalConfig(Config):
    """
    Local Configuration
    """

    DB_URL: str = "DB_URL"
    PROJ_RELOAD: bool = True
    TRUSTED_HOSTS = ["*"]
    ALLOW_SITE = ["*"]


@dataclass
class ProdConfig(Config):
    """
    Production Configuration
    """

    DB_URL: str = "DB_URL"
    PROJ_RELOAD: bool = False
    TRUSTED_HOSTS = ["*"]
    ALLOW_SITE = ["*"]


@dataclass
class TestConfig(Config):
    """
    Test Configuration
    """

    DB_URL: str = "DB_URL"
    TRUSTED_HOSTS = ["*"]
    ALLOW_SITE = ["*"]
    TEST_MODE: bool = True


def conf():
    """
    Load Configuration
    :return:
    """
    config = dict(prod=ProdConfig(), local=LocalConfig(), test=TestConfig())
    return config.get(environ.get("API_ENV", "local"))
