from .. import Base
from sqlalchemy.orm import Mapped



class Main(Base):
    __tablename__ = "data"
    owner: Mapped[str]
    tasks: Mapped[str]

