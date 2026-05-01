#!/usr/bin/env python3
import redis

WAIT_TTL = 300  # 5 minutes
ALLOW_TTL = 1800  # 30 minutes

"""TICKETMASTER_REDIS_URL=redis://default:<password>@<host>:<port>"""
r = redis.StrictRedis(
    host='<YOUR_REDIS_HOST>',
    port='<YOUR_REDIS_PORT>',
    password='<YOUR_REDIS_PASSWORD>',
    decode_responses=True
)

# Enable notifications (run this once at startup)
r.config_set('notify-keyspace-events', 'Ex')
# Subscribe to expired keys
pubsub = r.pubsub()
pubsub.psubscribe('__keyevent@0__:expired')

print("Listening for key expirations...")
for message in pubsub.listen():
    if message['type'] == 'pmessage':
        expired_key = message['data']
        print(f"Key expired: {expired_key}")
        if expired_key.startswith("waiting:"):
            _, event_id, user_id = expired_key.split(":")
            queue_key = f"queue:{event_id}"
            queue_head = r.lindex(queue_key, 0)
            next_user = None
            if queue_head == user_id:
                r.lrem(queue_key, 0, user_id)
                r.setex(f"allowed:{event_id}:{user_id}", ALLOW_TTL, user_id)
                print(f"\tPromoted {user_id} for event {event_id}")
                # Promote next user in queue by creating a new waiting key
                next_user = r.lindex(queue_key, 0)
            if next_user:
                r.setex(f"waiting:{event_id}:{next_user}", WAIT_TTL, next_user)
                print(f"\tStarted wait timer for next user in line: {next_user}")
            else:
                print(f"\tNo more users waiting in the queue")
