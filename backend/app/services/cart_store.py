# Simple in-memory cart store

CART_DB = {}

def get_cart(user_id: int):
    return CART_DB.get(user_id, [])

def add_to_cart(user_id: int, product: dict):
    if user_id not in CART_DB:
        CART_DB[user_id] = []
    CART_DB[user_id].append(product)

def clear_cart(user_id: int):
    CART_DB[user_id] = []