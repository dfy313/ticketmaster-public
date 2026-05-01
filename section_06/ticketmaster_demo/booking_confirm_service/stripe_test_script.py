import stripe

stripe.api_key = "<STRIPE_API_TEST_SECRET_KEY>" # Use your test secret key (starts with sk_test_)
CUSTOMER_ID = "<CUSTOMER_ID>"  # Replace with your test customer ID (starts with cus_)
PAYMENT_METHOD_ID = "<PAYMENT_METHOD_ID>"  # Replace with your test payment method ID (starts with pm_)

balance = stripe.Balance.retrieve()
print("✅ Connected to Stripe. Balance object received:")
print(balance)

# Create a payment (charge) using the saved card
intent = stripe.PaymentIntent.create(
    amount=1045,  # $10.45
    currency="usd",
    customer=CUSTOMER_ID,
    payment_method=PAYMENT_METHOD_ID,
    off_session=True,
    confirm=True,
    description="Test ticket purchase for customer"
)

print("\n✅ Payment successful:", intent.id)
print(intent)
