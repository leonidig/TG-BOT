from sqlalchemy import create_engine
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, sessionmaker

engine = create_engine("sqlite:///tasks.db", echo=True)
Session = sessionmaker(engine)


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True)


def up():
    Base.metadata.create_all(engine)

def down():
    Base.metadata.drop_all(engine)


from .models import Main


# down()
up()