import redis

def lambda_handler(event, context):
    r = get_redis_client()

    request_context = event.get("requestContext", {})
    route_key = request_context.get("routeKey")  # This will be "$connect" or "$disconnect"
    connection_id = request_context.get("connectionId")

    print(f"ROUTE KEY: {route_key}")
    print(f"CONNECTION ID: {connection_id}")

    if route_key == "$connect":
        r.sadd("live_seatmap_connections", connection_id)
    elif route_key == "$disconnect":
        r.srem("live_seatmap_connections", connection_id)

    return { "statusCode": 200 }

# =============== REDIS HELPERS ===============
def get_redis_client():
    """TICKETMASTER_REDIS_URL=redis://default:<password>@<host>:<port>"""
    return redis.StrictRedis(
        host='<YOUR_REDIS_HOST>',
        port='<YOUR_REDIS_PORT>',
        password='<YOUR_REDIS_PASSWORD>',
        decode_responses=True
    )
