import os
import redis

WAIT_TTL = 300  # 5 minutes
USER_ID = os.getenv("USER_ID", "admin_user")

def lambda_handler(event, context):
    r = get_redis_client()
    path = event.get("rawPath", "")
    path_parts = path.strip("/").split("/") 
    if not path_parts or len(path_parts) < 2:
        return generate_policy(USER_ID, False) # Allow access on home page

    route_prefix = path_parts[0] if len(path_parts) > 0 else ""  # e.g. "event" or "ticket"
    resource_id = path_parts[1] if len(path_parts) > 1 else ""  # e.g. "1H", "1:1H"
    is_high_traffic = resource_id.endswith("H")
    if not is_high_traffic:
        return generate_policy(USER_ID, False) # Normal traffic: always allow.

    event_id = resource_id.split(":")[1] if route_prefix == "ticket" else resource_id
    allowed_key = f"allowed:{event_id}:{USER_ID}"
    if r.exists(allowed_key):
        return generate_policy(USER_ID, False) # User already allowed, bypass queue
    elif route_prefix != "event":
        return generate_deny_policy(USER_ID) # Block direct access to non /event routes until the user is allowed

    # Queue state for high-traffic event access (e.g. /event/1H)
    queue_key = f"queue:{event_id}"
    waiting_key = f"waiting:{event_id}:{USER_ID}"
    if r.exists(waiting_key):
        ttl = r.ttl(waiting_key)
        return generate_policy(USER_ID, True, queue_ttl=ttl) # If already waiting, return remaining TTL for countdown UI.

    waiting_queue = r.lrange(queue_key, 0, -1)
    if not waiting_queue: # Queue doesn't exist or is empty
        r.rpush(queue_key, USER_ID)
        r.setex(waiting_key, WAIT_TTL, USER_ID)
        return generate_policy(USER_ID, True, queue_ttl=WAIT_TTL) # Return TTL for countdown UI.

    if USER_ID not in waiting_queue:
        r.rpush(queue_key, USER_ID)

    position = r.lrange(queue_key, 0, -1).index(USER_ID) + 1
    return generate_policy(USER_ID, True, place_in_line=position) # Return queue position for place-in-line UI

# =============== POLICY GENERATION HELPERS ===============
def generate_policy(user_id, is_queued, queue_ttl=None, place_in_line=None):
    base_policy = {
        "principalId": user_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "execute-api:Invoke",
                "Effect": "Allow",
                "Resource": "*"
            }]
        }
    }
    if is_queued:
        context = { "isQueued": "true" }
        if queue_ttl is not None:
            context["queueTtlSeconds"] = str(queue_ttl)
        if place_in_line is not None:
            context["placeInLine"] = str(place_in_line)
        base_policy["context"] = context
    return base_policy

def generate_deny_policy(user_id):
    return {
        "principalId": user_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "execute-api:Invoke",
                "Effect": "Deny",
                "Resource": "*"
            }]
        }
    }

# =============== REDIS HELPERS ===============
def get_redis_client():
    """TICKETMASTER_REDIS_URL=redis://default:<password>@<host>:<port>"""
    return redis.StrictRedis(
        host='<YOUR_REDIS_HOST>',
        port='<YOUR_REDIS_PORT>',
        password='<YOUR_REDIS_PASSWORD>',
        decode_responses=True
    )


if __name__ == "__main__":
    home_request = {
        "rawPath": "/"
    }
    print("\n----- Home Request -----")
    res = lambda_handler(home_request, None)
    print(res)

    event_request = {
        "rawPath": "/event/1H"
    }
    print("\n----- Event Request -----")
    res = lambda_handler(event_request, None)
    print(res)

    ticket_request = {
        "rawPath": "/ticket/1:1H"
    }
    print("\n----- Ticket Request -----")
    res = lambda_handler(ticket_request, None)
    print(res)

    booking_reserve_request = {
        "rawPath": "/ticket/1:1H/booking/reserve"
    }
    print("\n----- Booking Reserve Request (Phase 1) -----")
    res = lambda_handler(booking_reserve_request, None)
    print(res)

    booking_confirm_request = {
        "rawPath": "/ticket/1:1H/booking/confirm"
    }
    print("\n----- Booking Confirm Request (Phase 2) -----")
    res = lambda_handler(booking_confirm_request, None)
    print(res)
