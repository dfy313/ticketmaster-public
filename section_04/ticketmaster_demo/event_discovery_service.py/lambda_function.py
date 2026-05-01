import json
import pymysql, redis

def lambda_handler(event, context):
    """
    Supported Routes:
    1) GET /
       -> Returns a list of events (home page)
    2) GET /event/{eventId}
       -> Returns event details and all associated tickets
    3) GET /ticket/{ticketId}
       -> Returns details for a single ticket
    """
    path_params = event.get("pathParameters") or {}
    event_id = path_params.get("eventId")
    ticket_id = path_params.get("ticketId")

    if event_id and ticket_id:
        return {"statusCode": 400, "body": "Error: Only one of 'eventId' or 'ticketId' is allowed."}

    if event_id:
        return handle_event_request(event_id)
    elif ticket_id:
        return handle_ticket_request(ticket_id)
    else:
        return handle_home_request()

# =============== EVENT REQUEST HANDLERS ===============
def handle_home_request():
    try:
        events = fetch_all_events()
    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}
    return {
        "statusCode": 200,
        "body": json.dumps({
            "event": [{
                "eventId": event[0], "name": event[1], "description": event[2], "date": str(event[3])
            } for event in events ]
        })
    }

def handle_event_request(event_id):
    try:
        event_record, tickets = fetch_event_details(event_id)
        if not event_record:
            return {"statusCode": 404, "body": json.dumps({"message": "Event record for the provided eventId not found."})}
    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}
    return {
        "statusCode": 200,
        "body": json.dumps({
            "event": {
                "name": event_record[0], "description": event_record[1], "date": str(event_record[2])
            },
            "tickets": [{
                "ticketId": ticket[0], "seatNumber": ticket[1], "price": float(ticket[2])
            } for ticket in tickets ]
        })
    }

def handle_ticket_request(ticket_id):
    try:
        ticket_record = fetch_ticket_details(ticket_id)
        if not ticket_record:
            return {"statusCode": 404, "body": json.dumps({"message": "Ticket record for the provided ticketId not found."})}
    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}
    return {
        "statusCode": 200,
        "body": json.dumps({
            "ticket": {
                "eventId": ticket_record[0], "seatNumber": ticket_record[1], "price": float(ticket_record[2])
            }
        })
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

# =============== DATABASE HELPERS ===============
def get_db_connection_cursor():
    conn = pymysql.connect(
        host="<YOUR_TICKETMASTER_DB_URL>",
        user="admin",
        password="Password100!",
        database="ticketmaster_db",
    )
    return conn, conn.cursor()

def fetch_all_events():
    conn, cursor = get_db_connection_cursor()
    try:
        cursor.execute("SELECT eventId, name, description, date FROM Events")
        events = cursor.fetchall()
        return events
    finally:
        cursor.close()
        conn.close()

def fetch_event_details(event_id):
    r = get_redis_client()
    conn, cursor = get_db_connection_cursor()
    try:
        cursor.execute("SELECT name, description, date FROM Events WHERE eventId = %s", (event_id,))
        event_record = cursor.fetchone()
        if not event_record:
            return None, None
        cursor.execute("SELECT ticketId, seatNumber, price FROM Tickets WHERE eventId = %s AND isBooked = False", (event_id,))
        tickets = cursor.fetchall()
        ticket_lock_keys = [f"reserved:{ticket[0]}_{ticket[2]}" for ticket in tickets]
        locked_tickets = r.mget(ticket_lock_keys)
        available_tickets = [ticket for i, ticket in enumerate(tickets) if locked_tickets[i] is None]
        return event_record, available_tickets
    finally:
        cursor.close()
        conn.close()

def fetch_ticket_details(ticket_id):
    r = get_redis_client()
    conn, cursor = get_db_connection_cursor()
    try:
        cursor.execute("SELECT eventId, seatNumber, price FROM Tickets WHERE ticketId = %s AND isBooked = False", (ticket_id,))
        ticket_record = cursor.fetchone()
        lock_key = f"reserved:{ticket_id}_{ticket_record[2]}" if ticket_record else None 
        if r.get(lock_key) or not ticket_record:
            return None
        return ticket_record
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    home_request = {
        "pathParameters": {}
    }
    res = lambda_handler(home_request, None)
    print("\n----- Home Request -----")
    print(res["statusCode"])
    print(json.dumps(json.loads(res["body"]), indent=2))

    event_request = {
        "pathParameters": {
            "eventId": "1H"
        }
    }
    res = lambda_handler(event_request, None)
    print("\n----- Event Request -----")
    print(res["statusCode"])
    print(json.dumps(json.loads(res["body"]), indent=2))

    ticket_request = {
        "pathParameters": {
            "ticketId": "1:1H"
        }
    }
    res = lambda_handler(ticket_request, None)
    print("\n----- Ticket Request -----")
    print(res["statusCode"])
    print(json.dumps(json.loads(res["body"]), indent=2))
