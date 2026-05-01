import os, json, base64, urllib.parse
import redis, pymysql, stripe

stripe.api_key = "<STRIPE_API_TEST_SECRET_KEY>" # Use your test secret key (starts with sk_test_)
CUSTOMER_ID = "<CUSTOMER_ID>"  # Replace with your test customer ID (starts with cus_)
PAYMENT_METHOD_ID = "<PAYMENT_METHOD_ID>"  # Replace with your test payment method ID (starts with pm_)
USER_ID = os.getenv("USER_ID", "admin_user") # Hardcoded, user auth & handling out of scope

def lambda_handler(event, context):
    """
    POST /ticket/{ticketId}/booking/confirm
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

    # 1. Check lock
    lock_key = f"reserved:{ticket_id}_{price}"
    current_owner = r.get(lock_key)
    if not current_owner:
        return {"statusCode": 410, "body": json.dumps({"message": "Ticket lock missing or expired."})}
    if current_owner != USER_ID:
        return {"statusCode": 403, "body": json.dumps({"message": "Ticket lock owned by another user."})}

    # 2. Try to book in DB
    try:
        rows_updated = update_ticket_details(ticket_id, USER_ID)
        if rows_updated == 0:
            return {"statusCode": 409, "body": "Ticket was already booked or does not exist."}
    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}

    # 3. Try to charge card
    try:
        intent = stripe.PaymentIntent.create(
            amount=int(float(price) * 100),
            currency="usd",
            customer=CUSTOMER_ID,
            payment_method=PAYMENT_METHOD_ID,
            off_session=True,
            confirm=True,
            description=f"Confirm booking for ticket {ticket_id} by {USER_ID}"
        )
    except Exception as e:
        rollback_ticket_updates(ticket_id)
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Unexpected stripe error", "details": str(e)})
        }

    # 4. Clean up redis
    r.delete(lock_key)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "Booking confirmed",
            "ticketId": ticket_id,
            "price": price,
            "userId": USER_ID, 
            "paymentIntentId": intent.id
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

def update_ticket_details(ticket_id, user_id):
    conn, cursor = get_db_connection_cursor()
    try:
        cursor.execute("UPDATE Tickets SET isBooked = TRUE, userId = %s WHERE ticketId = %s AND isBooked = FALSE", (user_id, ticket_id))
        conn.commit()
        return cursor.rowcount
    finally:
        cursor.close()
        conn.close()

def rollback_ticket_updates(ticket_id):
    conn, cursor = get_db_connection_cursor()
    try:
        cursor.execute("UPDATE Tickets SET isBooked = FALSE, userId = NULL WHERE ticketId = %s", (ticket_id,))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    booking_confirm_request = {
        "pathParameters": {
            "ticketId": "1:1H"
        },
        "body": "price=99.99"
    }
    res = lambda_handler(booking_confirm_request, None)
    print("\n----- Booking Confirm Request (Phase 2) -----")
    print(res["statusCode"])
    print(json.dumps(json.loads(res["body"]), indent=2))
