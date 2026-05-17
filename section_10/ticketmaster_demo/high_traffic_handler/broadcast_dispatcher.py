#!/usr/bin/env python3
import json
import boto3, redis

# Must be base URL, do not include trailing `/@connections`
WEBSOCKET_CONNECTIONS_BASE_URL = "<YOUR_WEBSOCKET_CONNECTIONS_BASE_URL>"
AWS_ACCESS_KEY_ID = "<YOUR_AWS_ACCESS_KEY_ID>"
AWS_SECRET_ACCESS_KEY = "<YOUR_AWS_SECRET_ACCESS_KEY>"

# Create boto3 client to talk to WebSocket management API
apigw = boto3.client(
    'apigatewaymanagementapi',
    region_name='us-east-2',  # Must match the AWS region where your WebSocket API was deployed
    endpoint_url=WEBSOCKET_CONNECTIONS_BASE_URL,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

"""TICKETMASTER_REDIS_URL=redis://default:<password>@<host>:<port>"""
r = redis.StrictRedis(
    host='<YOUR_REDIS_HOST>',
    port='<YOUR_REDIS_PORT>',
    password='<YOUR_REDIS_PASSWORD>',
    decode_responses=True
)

# Enable keyspace notifications for expired events (run once per Redis instance)
r.config_set('notify-keyspace-events', 'Ex')  # Ex = expired events
# Subscribe to both ticket reservations and key expiration events
pubsub = r.pubsub()
pubsub.subscribe("ticket_updates")
pubsub.psubscribe("__keyevent@0__:expired")
print("🔌 Subscribed to Redis channel: ticket_updates and key expirations")

def broadcast_to_clients(payload):
    connection_ids = r.smembers("live_seatmap_connections")
    print(f"\t🔄 Broadcasting to {len(connection_ids)} connections")
    for connection_id in connection_ids:
        try:
            apigw.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(payload).encode('utf-8')
            )
            print(f"\t✅ Sent message to {connection_id}")
        except Exception as e:
            print(f"\t⚠️ Error sending to {connection_id}: {e}")

# Message loop
for message in pubsub.listen():
    try:
        if message["type"] == "message":
            # Redis pub/sub from ticket_reservations
            payload = json.loads(message["data"])
            print(f"📨 Received pub/sub message: {payload}")
            broadcast_to_clients(payload)
        elif message["type"] == "pmessage":
            # Redis key expiration event
            expired_key = message["data"]  # e.g. reserved:1:1H_99.99
            if expired_key.startswith("reserved:"):
                ticket_info = expired_key[len("reserved:"):]
                ticket_id, price = ticket_info.split("_")
                print(f"⏱️ Redis key expired: {expired_key}")
                broadcast_to_clients({"ticketId": ticket_id, "price": price, "status": "available"})

    except Exception as e:
        print(f"❌ Failed to process pub/sub message: {e}")
