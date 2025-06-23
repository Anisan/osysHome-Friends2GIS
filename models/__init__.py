from app.database import Column, SurrogatePK, db

class FriendLocation(SurrogatePK, db.Model):
    __tablename__ = '2gis_locations'
    id_user = Column(db.String(255), nullable=False)
    name = Column(db.String(255), nullable=False)
    image = Column(db.String(2048), nullable=False)
    last_update = Column(db.DateTime())
    address = Column(db.String(512), nullable=True)
    lat = Column(db.Float(), default=0.0)
    lng = Column(db.Float(), default=0.0)
    accuracy = Column(db.Float(), default=0.0)
    speed = Column(db.Float(), default=0.0)
    battery_level = Column(db.Integer(), default=0)
    battery_charging = Column(db.Integer(), default=0)
    sendtogps = Column(db.Boolean(), default=False)
    