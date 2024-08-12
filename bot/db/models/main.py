from .. import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String



class Main(Base):
    __tablename__ = "data"
    owner: Mapped[str]
    tasks: Mapped[str]
    experience: Mapped[int] 
    progress: Mapped[int]
    due_dates: Mapped[str]
    #reminder_time: Mapped[str] = mapped_column(String(5))