"""fill cars and tracks

Revision ID: 5f2dfc826727
Revises: 15a323dd1d70
Create Date: 2025-09-25 20:25:33.979878

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import json
from src.domain.models import Car, Track

import os


# revision identifiers, used by Alembic.
revision: str = '5f2dfc826727'
down_revision: Union[str, Sequence[str], None] = '15a323dd1d70'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = f"{current_dir}/../../data"
    with sqlmodel.Session(op.get_bind()) as db:
        with open(f'data/cars.json') as f:
            cars_data = json.load(f)
        for car_data in cars_data.values():
            car = Car(
                id=int(car_data['id'][3:]),
                name=car_data['nameLong'],
                power=car_data['power_v'],
                torque=car_data['torque_v'],
                weight=car_data['weight_v'],
                length=car_data['length_v'],
                width=car_data['width_v'],
                height=car_data['height_v'],
                train=car_data['driveTrain'],
                class_=car_data['carClass'],
            )
            db.add(car)
            
        db.commit()

        with open(f'{data_dir}/tracks.json') as f:
            tracks_data = json.load(f)

        for track_data in tracks_data.values():
            track = Track(
                name=track_data["nameLong"],
                length=track_data["length_v"],
                num_turns=track_data["cornerCount"],
                country=track_data["countryName"],
            )
            db.add(track)
        db.commit()


def downgrade() -> None:
    ...
