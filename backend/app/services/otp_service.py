import random
import time

OTP_DB = {}

def generate_otp(user_id: int):
    otp = random.randint(100000, 999999)
    OTP_DB[user_id] = {
        "otp": otp,
        "expires": time.time() + 120  # 2 minutes validity
    }
    return otp

def verify_otp(user_id: int, entered_otp: int):
    if user_id not in OTP_DB:
        return False, "No OTP generated"

    record = OTP_DB[user_id]

    if time.time() > record["expires"]:
        return False, "OTP expired"

    if record["otp"] != entered_otp:
        return False, "Incorrect OTP"

    return True, "Payment Successful"