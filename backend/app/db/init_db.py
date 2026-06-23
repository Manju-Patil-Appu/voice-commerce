from app.db.session import Base, engine
from app.models import user, product, cart, order, order_item, voice

Base.metadata.create_all(bind=engine)
