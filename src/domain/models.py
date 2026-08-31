from typing import Optional

from sqlmodel import Column, Field, SQLModel, String


class Car(SQLModel, table=True):
    __tablename__ = "cars"
    id: int = Field(primary_key=True)
    name: str
    power: float
    torque: float
    weight: float
    length: float
    width: float
    height: float
    train: str
    class_: str = Field(sa_column=Column("class", String))


class Track(SQLModel, table=True):
    __tablename__ = "tracks"

    id: int = Field(primary_key=True)
    name: str
    length: int
    num_turns: int
    country: str


class Race(SQLModel, table=True):
    __tablename__ = "sessions"

    id: str = Field(primary_key=True)
    track_id: Optional[int] = Field(nullable=True, default=None)
    car_id: int
    racer: Optional[str] = Field(nullable=True, default=None)
    best_lap_time: int
    end_ts: int


class Lap(SQLModel, table=True):
    id: str = Field(primary_key=True)
    number: int
    race_id: int
    time: int
