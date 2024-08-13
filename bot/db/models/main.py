from .. import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String
from datetime import datetime


class Main(Base):
    __tablename__ = "data"
    owner: Mapped[str]
    tasks: Mapped[str]
    experience: Mapped[int] 
    progress: Mapped[int]
    due_dates: Mapped[str]
    last_active: Mapped[datetime] = mapped_column(default=datetime.now())