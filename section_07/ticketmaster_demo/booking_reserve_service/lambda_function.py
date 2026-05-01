import os, json, base64, urllib.parse
import redis, pymysql

USER_ID = os.getenv("USER_ID", "admin_user") # Hardcoded, user auth & handling out of scope

def lambda_handler(event, context):
    """
    POST /ticket/{ticketId}/booking/reserve
      Request Body: price=<REQUIRED>
      Content-Type: application/x-www-form-urlencoded
    """
    r = get_redis_client()
    path_params = event.get("pathParameters") or {}
    body_raw = event.get("body") or ""
    if event.get("isBase64Encoded"): # API Gateway occasionally base64-encodes the body on form posts
        body_raw = base64.b64decode(body_raw).decode("utf-8")
    
    price = urllib.parse.parse_qs(body_raw).get("price", [None])[0] # Parse form-encoded body
    ticket_id = path_params.get("ticketId")
    if not ticket_id or not price:
        return {"statusCode": 400, "body": "Error: Path param 'ticketId' and form field 'price' are required."}

    try:
        ticket_record = fetch_ticket_record(ticket_id)
        if not ticket_record:
            return {"statusCode": 409, "body": f"Error: {ticket_id} is already booked or does not exist."}
    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}

    # Attempt to acquire a lock on the ticket.
    # - ex=600 sets the expiration time to 600 seconds (10 minutes)
    # - nx=True ensures the key is only set if it does not already exist (i.e., not already locked)
    lock_key = f"reserved:{ticket_id}_{price}"
    lock_acquired = r.set(lock_key, USER_ID, ex=600, nx=True)
    current_owner, ttl_seconds = r.get(lock_key), r.ttl(lock_key)

    confirm_button_html = ""
    if current_owner == USER_ID:
        confirm_button_html = (
            f"<form method='POST' action='/ticket/{ticket_id}/booking/confirm'>"
            f"<input type='hidden' name='price' value='{price}'>"
            f"<button type='submit'>Confirm Booking</button></form>"
        )

    if lock_acquired:
        html_content = f"<html><body><h2>Reserved {ticket_id} for ${price}.</h2><p>Locked by: {current_owner} (TTL: {ttl_seconds}s)</p>{confirm_button_html}<a href='/'>Home</a></body></html>"
        return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html_content}
    else:
        html_content = f"<html><body><h2>{ticket_id} is already reserved.</h2><p>Locked by: {current_owner} (TTL: {ttl_seconds}s)</p>{confirm_button_html}<a href='/'>Home</a></body></html>"
        return {"statusCode": 423, "headers": {"Content-Type": "text/html"}, "body": html_content}

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

def fetch_ticket_record(ticket_id):
    conn, cursor = get_db_connection_cursor()
    try:
        cursor.execute("SELECT * FROM Tickets WHERE ticketId = %s AND isBooked = FALSE", (ticket_id,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    booking_reserve_request = {
        "pathParameters": {
            "ticketId": "1:1H"
        },
        "body": "price=99.99"
    }
    res = lambda_handler(booking_reserve_request, None)
    print("\n----- Booking Reserve Request (Phase 1) -----")
    print(res["statusCode"])
    print(json.dumps(json.loads(res["body"]), indent=2))
