import json
import redis, pymysql

WEBSOCKET_API_URL = "<YOUR_WEBSOCKET_API_URL>"

def lambda_handler(event, context):
    """
    GET /high_traffic_event/{eventId}
      -> Returns event details and associated tickets for high-traffic events,
         rendered with a dynamic, real-time seat map.
    """
    path_params = event.get("pathParameters") or {}
    event_id = path_params.get("eventId")
    if event_id:
        return handle_event_request(event_id)
    else:
        return {"statusCode": 400, "body": "Missing eventId in pathParameters"}

# =============== REQUEST HANDLERS ===============
def handle_event_request(event_id):
    try:
        event_record, tickets = fetch_event_details(event_id)
        if not event_record:
            return {"statusCode": 404, "body": json.dumps({"message": "Event record for the provided eventId not found."})}
    except pymysql.MySQLError as e:
        return {"statusCode": 500, "body": json.dumps({"message": f"Database error: {str(e)}"})}

    name, description, date = event_record
    html_content = f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <title>{name}</title>
        <script>
            const socket = new WebSocket('{WEBSOCKET_API_URL}');
            socket.onopen = () => {{
                console.log('WebSocket connection established');
            }};
            socket.onmessage = (event) => {{
                console.log('Message from server:', event.data);
                const data = JSON.parse(event.data);

                // Display message in message box
                const messageContainer = document.getElementById('ws-messages');
                const messageElement = document.createElement('p');
                messageElement.textContent = data.message || event.data;
                messageContainer.appendChild(messageElement);

                const ticketId = data.ticketId;
                const status = data.status;
                if (!ticketId || !status) return;
                const ticketElement = document.getElementById("ticket-" + ticketId);

                // Handle ticket reservation updates
                if (status === "reserved") {{
                    if (ticketElement) {{
                        const parts = ticketId.split(":");
                        const seatNumber = parts[0];
                        const newHtml = "<span style='color: gray;'>Seat " + seatNumber + " (reserved)</span>: $" + parseFloat(data.price).toFixed(2);
                        ticketElement.innerHTML = newHtml;
                    }}
                }}
                // Handle ticket confirmation updates
                else if (status === "confirmed") {{
                    if (ticketElement) {{
                        ticketElement.remove();  // Remove from DOM
                    }}
                }}
                // Handle ticket available updates 
                else if (status === "available") {{
                    const parts = ticketId.split(":");
                    const seatNumber = parts[0];
                    const newHtml = "<a href='" + "/ticket/" + ticketId + "'>Seat " + seatNumber + "</a> <span style='color: gray;'>(reservation expired)</span>: $" + parseFloat(data.price).toFixed(2);

                    if (ticketElement) {{
                        // Replace grayed-out reserved entry with clickable link
                        ticketElement.innerHTML = newHtml;                    
                    }} else {{
                        // Ticket was missing from list (e.g., expired lock after page loaded)
                        const list = document.querySelector("ul");
                        const newLi = document.createElement("li");
                        newLi.id = "ticket-" + ticketId;
                        newLi.innerHTML = newHtml;
                        list.appendChild(newLi);
                    }}
                }}
            }};
            socket.onerror = (error) => {{
                console.error('WebSocket error:', error);
            }};
            socket.onclose = () => {{
                console.log('WebSocket connection closed');
            }};
        </script>
    </head>
    <body>
        <h1>{name}</h1>
        <p>{description}</p>
        <p><strong>Date:</strong> {date}</p>
        <h2>Live Updates</h2>
        <div id="ws-messages" style="border: 1px solid #ccc; padding: 10px; min-height: 50px;"></div>
        <h2>Available Tickets</h2>
        <ul>
    """
    if tickets:
        for ticket in tickets:
            ticket_id, seat_number, price = ticket
            html_content += f"<li id='ticket-{ticket_id}'><a href='/ticket/{ticket_id}'>Seat {seat_number}</a>: ${float(price):.2f}</li>"
    else:
        html_content += "<li>No available tickets.</li>"
    html_content += "</ul><p><a href='/'>← Back to events</a></p></body></html>"

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


if __name__ == "__main__":
    event_request = {
        "pathParameters": {
            "eventId": "1H"
        }
    }
    res = lambda_handler(event_request, None)
    print("\n----- Event Request -----")
    print(res["statusCode"])
    print(res)
