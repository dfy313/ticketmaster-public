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
    authorizer_context = event.get("requestContext", {}).get("authorizer", {}).get("lambda", {})
    is_queued = authorizer_context.get("isQueued") if authorizer_context else None
    if is_queued == 'true':
        queue_ttl = authorizer_context.get("queueTtlSeconds") if authorizer_context else None
        place_in_line = authorizer_context.get("placeInLine") if authorizer_context else None
        return handle_waiting_queue_request(queue_ttl, place_in_line)

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
def handle_waiting_queue_request(queue_ttl=None, place_in_line=None):
    if queue_ttl is not None:
        html_content = f"<html><body><h2>You're in line</h2><p>Please refresh in {queue_ttl} seconds.</p></body></html>"
    elif place_in_line is not None:
        html_content = f"<html><body><h2>You're in line</h2><p>Your current place in line is <strong>{place_in_line}</strong>.</p></body></html>"
    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html_content}

def handle_home_request():
    try:
        events = fetch_all_events()
    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}

    html_content = "<html><body><h1>Event Listings</h1><ul>"
    for event in events:
        event_id, name, description, date = event
        html_content += f"<li><a href='/event/{event_id}'>{name}</a>: {description} ({date})</li>"
    html_content += "</ul></body></html>"

    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html_content}

def handle_event_request(event_id):
    if str(event_id).endswith("H"):  # Redirect high-traffic events to special endpoint
        return {
            "statusCode": 302,
            "headers": {
                "Location": f"/high_traffic_event/{event_id}"
            }
        }

    try:
        event_record, tickets = fetch_event_details(event_id)
        if not event_record:
            return {"statusCode": 404, "body": json.dumps({"message": "Event record for the provided eventId not found."})}
    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}

    name, description, date = event_record
    html_content = f"<html><head><meta charset='UTF-8'><title>{name}</title></head><body><h1>{name}</h1><p>{description}</p><p><strong>Date:</strong> {date}</p><h2>Available Tickets</h2><ul>"
    if tickets:
        for ticket in tickets:
            ticket_id, seat_number, price = ticket
            html_content += f"<li><a href='/ticket/{ticket_id}'>Seat {seat_number}</a>: ${float(price):.2f}</li>"
    else:
        html_content += "<li>No available tickets.</li>"
    html_content += "</ul><p><a href='/'>← Back to events</a></p></body></html>"

    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html_content}

def handle_ticket_request(ticket_id):
    try:
        ticket_record = fetch_ticket_details(ticket_id)
        if not ticket_record:
            return {"statusCode": 404, "body": json.dumps({"message": "Ticket record for the provided ticketId not found."})}
    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}

    event_id, seat_number, price = ticket_record
    html_content = (
        f"<html><head><meta charset='UTF-8'><title>Ticket {ticket_id}</title></head><body><h1>Ticket Details</h1>"
        f"<ul><li><strong>Ticket ID:</strong> {ticket_id}</li><li><strong>Seat Number:</strong> {seat_number}</li><li><strong>Price:</strong> ${float(price):.2f}</li></ul>"
        f"<form method='POST' action='/ticket/{ticket_id}/booking/reserve'>"
        f"<input type='hidden' name='price' value='{price}'>"
        f"<button type='submit'>Reserve Ticket</button></form>"
        f"<p><a href='/event/{event_id}'>← Back to event details</a></p>"
    )

    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html_content}

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
    print(res["body"])

    event_request = {
        "pathParameters": {
            "eventId": "1H"
        }
    }
    res = lambda_handler(event_request, None)
    print("\n----- Event Request -----")
    print(res["statusCode"])
    print(res["body"])

    ticket_request = {
        "pathParameters": {
            "ticketId": "1:1H"
        }
    }
    res = lambda_handler(ticket_request, None)
    print("\n----- Ticket Request -----")
    print(res["statusCode"])
    print(res["body"])
