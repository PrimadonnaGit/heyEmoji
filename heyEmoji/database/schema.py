from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import Session

from heyEmoji.database.conn import Base, db


class BaseMixin:
    id = Column(Integer, primary_key=True, index=True)

    def __init__(self):
        self._q = None
        self._session = None
        self.served = None

    def all_columns(self):
        return [
            c
            for c in self.__table__.columns
            if c.primary_key is False and c.name != "created_at"
        ]

    def as_dict(self):
        return {x.name: getattr(self, x.name) for x in self.__table__.columns}

    def __hash__(self):
        return hash(self.id)

    @classmethod
    def create(cls, session: Session = None, auto_commit=False, **kwargs):
        """
        테이블 데이터 적재 전용 함수
        :param session:
        :param auto_commit: 자동 커밋 여부
        :param kwargs: 적재 할 데이터
        :return:
        """
        sess = next(db.session()) if not session else session

        obj = cls()
        for col in obj.all_columns():
            col_name = col.name
            if col_name in kwargs:
                setattr(obj, col_name, kwargs.get(col_name))
        sess.add(obj)
        sess.flush()
        if auto_commit:
            sess.commit()
        return obj

    @classmethod
    def get_all(cls, session: Session = None):
        """
        Get All Row
        :param session:
        :param kwargs:
        :return:
        """
        sess = next(db.session()) if not session else session
        query = sess.query(cls)
        result = query.all()
        if not session:
            sess.close()
        return result

    @classmethod
    def get(cls, session: Session = None, **kwargs):
        """
        Simply get a Row
        :param session:
        :param kwargs:
        :return:
        """
        sess = next(db.session()) if not session else session
        query = sess.query(cls)
        for key, val in kwargs.items():
            col = getattr(cls, key)
            query = query.filter(col == val)
        if query.count() > 1:
            raise Exception(
                "Only one row is supposed to be returned, but got more than one."
            )
        result = query.first()
        if not session:
            sess.close()
        return result

    @classmethod
    def filter(cls, session: Session = None, **kwargs):
        """
        Simply get a Row
        :param session:
        :param kwargs:
        :return:
        """
        cond = []
        for key, val in kwargs.items():
            key = key.split("__")
            if len(key) > 2:
                raise Exception("No 2 more dunders")
            col = getattr(cls, key[0])
            if len(key) == 1:
                cond.append((col == val))
            elif len(key) == 2 and key[1] == "gt":
                cond.append((col > val))
            elif len(key) == 2 and key[1] == "gte":
                cond.append((col >= val))
            elif len(key) == 2 and key[1] == "lt":
                cond.append((col < val))
            elif len(key) == 2 and key[1] == "lte":
                cond.append((col <= val))
            elif len(key) == 2 and key[1] == "in":
                cond.append((col.in_(val)))
        obj = cls()
        if session:
            obj._session = session
            obj.served = True
        else:
            obj._session = next(db.session())
            obj.served = False
        query = obj._session.query(cls)
        query = query.filter(*cond)
        obj._q = query
        return obj

    @classmethod
    def cls_attr(cls, col_name=None):
        if col_name:
            col = getattr(cls, col_name)
            return col
        else:
            return cls

    def order_by(self, *args: str):
        for a in args:
            if a.startswith("-"):
                col_name = a[1:]
                is_asc = False
            else:
                col_name = a
                is_asc = True
            col = self.cls_attr(col_name)
            self._q = (
                self._q.order_by(col.asc()) if is_asc else self._q.order_by(col.desc())
            )
        return self

    def update(self, auto_commit: bool = False, **kwargs):
        qs = self._q.update(kwargs)
        get_id = self.id
        ret = None

        self._session.flush()
        if qs > 0:
            ret = self._q.all()

        if auto_commit:
            self._session.commit()
        return ret

    def first(self):
        result = self._q.first()
        self.close()
        return result

    def delete(self, auto_commit: bool = False):
        self._q.delete()
        if auto_commit:
            self._session.commit()

    def all(self):
        print(self.served)
        result = self._q.all()
        self.close()
        return result

    def count(self):
        result = self._q.count()
        self.close()
        return result

    def close(self):
        if not self.served:
            self._session.close()
        else:
            self._session.flush()


class User(Base, BaseMixin):
    __tablename__ = "users"
    username = Column(String(100), nullable=True)  # display name
    slack_id = Column(String(50), nullable=False)  # 슬랙 아이디
    today_reaction = Column(Integer, nullable=False, default=5)  # 사용할 수 있는 리액션(이모지) 개수
    avatar_url = Column(String(100), nullable=True)  # 프로필 이미지 url

    def __repr__(self):
        return "id : %s, username : %s, slack_id : %s, today_reaction : %d" % (
            self.id,
            self.username,
            self.slack_id,
            self.today_reaction,
        )


class Reaction(Base, BaseMixin):
    __tablename__ = "reactions"
    year = Column(Integer, nullable=False)  # 년
    month = Column(Integer, nullable=False)  # 월
    to_user = Column(Integer, ForeignKey("users.id"))  # 리액션을 받은 유저
    from_user = Column(Integer, ForeignKey("users.id"))  # 리액션을 보낸 유저
    type = Column(String(50), nullable=True)  # 리액션 타입 (이모지 종류)
    count = Column(Integer, default=0)  # 받은 개수

    def __repr__(self):
        return "year : %d, month : %d, to : %d, from : %d" % (
            self.year,
            self.month,
            self.to_user,
            self.from_user,
        )
