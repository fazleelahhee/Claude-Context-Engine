# Examples

Real conversations showing CCE in action. Each example shows exactly what you type, what Claude does behind the scenes, and what you get back.

---

## Before You Start

Run this once per project:

```bash
cd /path/to/your/project
cce init
```

Then restart Claude Code. CCE's tools are now available in every session automatically — no setup needed per conversation.

---

## Example 1: Your First Session

This is what a session looks like from the moment you open Claude Code on a project CCE has indexed.

**You open Claude Code and say:**

```
What does this project do and how is it structured?
```

**Claude runs automatically:**

```
session_recall()
index_status()
```

**What Claude sees from session_recall:**

```
3 past decisions found:

[2026-04-14] Chose Stripe over Braintree
  Reason: team already has Stripe accounts, SDK better maintained
  Files: payments/gateway.py, payments/webhooks.py

[2026-04-12] Using Redis for session storage, not JWT
  Reason: need server-side revocation for enterprise customers
  Files: auth/session.py, config/redis.py

[2026-04-10] Orders table uses soft deletes (deleted_at column)
  Reason: legal requirement to retain order history for 7 years
  Files: models/order.py, db/migrations/
```

**What Claude sees from index_status:**

```
Project: my-ecommerce-app
Chunks indexed: 1,847
Files indexed: 134
Last indexed: 4 minutes ago
```

**Claude responds:**

```
This is an e-commerce application. Based on the index and past session decisions:

Architecture: Python backend, Stripe for payments, Redis for sessions.
Key decisions already made: Stripe (not Braintree), Redis sessions (not JWT),
soft deletes on orders for 7-year legal retention.

The codebase has 134 files across payments, auth, orders, products, and shipping.
What would you like to work on?
```

Claude already knows the project history, the past decisions, and the structure — without you pasting a single file. Total tokens used: ~800.

---

## Example 2: Finding and Understanding Code

**You say:**

```
How does the checkout flow work? I need to add Apple Pay support.
```

**Claude searches:**

```
context_search(query="checkout flow payment processing")
```

**Claude receives:**

```
[payments/checkout.py:12] (confidence: 0.96)
def start_checkout(cart_id: str, user: User) -> CheckoutSession:
    """Begin checkout. Creates a Stripe PaymentIntent and returns
    a session token for the frontend."""
    cart = Cart.get(cart_id)
    intent = stripe.PaymentIntent.create(
        amount=cart.total_cents,
        currency="usd",
        customer=user.stripe_customer_id,
        metadata={"cart_id": cart_id}
    )
    return CheckoutSession(intent_id=intent.id, client_secret=intent.client_secret)

---

[payments/checkout.py:44] (confidence: 0.91)
def confirm_checkout(intent_id: str, payment_method_id: str) -> Order:
    """Confirm payment and create order."""
    intent = stripe.PaymentIntent.confirm(
        intent_id,
        payment_method=payment_method_id
    )
    if intent.status != "succeeded":
        raise PaymentError(f"Payment failed: {intent.status}")
    return _create_order_from_intent(intent)

---

[payments/webhooks.py:22] (confidence: 0.84)  ← graph expansion
def handle_payment_intent_succeeded(event: dict) -> None:
    """Stripe webhook: payment confirmed. Trigger fulfilment."""
    intent = event["data"]["object"]
    order = Order.get_by_intent(intent["id"])
    order.mark_paid()
    fulfilment.queue(order.id)
```

**Claude responds:**

```
The checkout flow has two steps:

1. start_checkout() — creates a Stripe PaymentIntent and returns a client_secret
   to the frontend (payments/checkout.py:12)
2. confirm_checkout() — confirms the payment and creates the order (payments/checkout.py:44)
3. A webhook handler catches payment_intent.succeeded to trigger fulfilment
   (payments/webhooks.py:22)

For Apple Pay: Stripe handles Apple Pay through the same PaymentIntent API —
no backend changes needed. Apple Pay is a payment method the frontend passes as
payment_method_id. You would need to:
- Add the Apple Pay domain association file (.well-known/apple-developer-merchantid-domain-association)
- Register the domain in your Stripe dashboard
- Update the frontend to show the Apple Pay button when available

The confirm_checkout() function already handles any Stripe payment method,
including Apple Pay. No backend code changes required.
```

You got a complete answer in one exchange. Claude read 3 relevant functions (not 134 files).

---

## Example 3: Debugging an Error

**You say:**

```
I'm getting this error in production:

KeyError: 'express' at payments/shipping.py line 34
Traceback shows it's in calculate_shipping_cost()
```

**Claude searches:**

```
context_search(query="calculate_shipping_cost SHIPPING_RATES express KeyError")
```

**Claude receives:**

```
[payments/shipping.py:12] (confidence: 0.98)
SHIPPING_RATES = {
    "standard": {"domestic": 4.99, "international": 14.99},
    "overnight": {"domestic": 24.99, "international": 49.99},
}

---

[payments/shipping.py:28] (confidence: 0.95)
def calculate_shipping_cost(order, method: str) -> float:
    """Calculate shipping cost based on method and destination."""
    zone = "international" if order.is_international else "domestic"
    return SHIPPING_RATES[method][zone]   # ← line 34

---

[payments/checkout.py:18] (confidence: 0.79)  ← graph expansion
ALLOWED_SHIPPING_METHODS = ["standard", "express", "overnight"]

def validate_checkout_options(method: str, ...) -> None:
    if method not in ALLOWED_SHIPPING_METHODS:
        raise ValueError(...)
```

**Claude responds:**

```
Found the bug. SHIPPING_RATES (shipping.py:12) only defines "standard" and "overnight",
but validate_checkout_options (checkout.py:18) allows "standard", "express", and "overnight".

Someone added "express" to the allowed methods list without adding it to the rate table.

Fix — add express rates to SHIPPING_RATES:

    "express": {"domestic": 12.99, "international": 29.99},

Or remove "express" from ALLOWED_SHIPPING_METHODS if it is not meant to be available yet.

The graph expansion also found that checkout.py calls into shipping.py, so if you add
"express" to SHIPPING_RATES you do not need to change the checkout validation.
```

The graph expansion found the inconsistency automatically — Claude had the rate table AND the allowed methods list without you pointing it out.

---

## Example 4: Adding a New Feature

**You say:**

```
I need to add order cancellation. Users should be able to cancel within 1 hour of placing an order.
```

**Claude searches:**

```
context_search(query="order model status fulfilment")
context_search(query="order cancellation refund")
```

**Claude receives (first search):**

```
[models/order.py:8] (confidence: 0.94)
class Order(Base):
    __tablename__ = "orders"
    id = Column(UUID, primary_key=True, default=uuid4)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # soft delete
    stripe_intent_id = Column(String, nullable=True)

---

[models/order.py:44] (confidence: 0.88)
class OrderStatus(Enum):
    PENDING    = "pending"
    PAID       = "paid"
    PROCESSING = "processing"
    SHIPPED    = "shipped"
    DELIVERED  = "delivered"
```

**Claude receives (second search):**

```
No results above confidence threshold.
```

No cancellation code exists yet. Claude knows to build it from scratch.

**Claude responds:**

```
No existing cancellation logic found. Here is what needs to be built:

1. Add CANCELLED to OrderStatus in models/order.py:44

2. Add a cancel() method to the Order model:

    def cancel(self) -> None:
        if self.status not in (OrderStatus.PENDING, OrderStatus.PAID):
            raise ValueError("Cannot cancel an order in status: " + self.status.value)
        age = datetime.utcnow() - self.created_at
        if age.total_seconds() > 3600:
            raise ValueError("Cancellation window has passed (1 hour)")
        self.status = OrderStatus.CANCELLED

3. Add a refund step if status is PAID (Stripe refund via stripe_intent_id)

4. Add a POST /orders/{id}/cancel endpoint

Should I start with the model change and work outward?
```

Claude read the exact Order model and status enum, understood the soft-delete pattern already in use, found no existing cancellation code, and gave a concrete plan grounded in the actual code — not generic advice.

---

## Example 5: Picking Up Where You Left Off

**You worked on the auth system last Tuesday. Today you open a new session and say:**

```
I want to continue the auth refactor from last week.
```

**Claude runs:**

```
session_recall(query="auth refactor")
```

**Claude receives:**

```
[Code area recorded 2026-04-15]
File: auth/session.py
Work: Replaced JWT tokens with Redis-backed sessions. Session keys use
      SHA-256 of (user_id + timestamp + secret). Expiry set to 24h.
      Still TODO: migrate existing JWT sessions gracefully (users logged
      in before the deploy should not be logged out).

[Decision recorded 2026-04-15]
Title: Redis sessions, not JWT
Context: Enterprise customers need server-side revocation. JWT cannot be
         revoked without a blocklist, which is equivalent to a session store
         anyway. Redis gives revocation + simpler logout.
Files: auth/session.py, config/redis.py
```

**Claude responds:**

```
Found the auth refactor context from last Tuesday.

You replaced JWT with Redis sessions in auth/session.py. The remaining TODO
is a migration path for existing JWT sessions — users logged in before the
deploy should not be logged out unexpectedly.

The typical approach is a dual-validation period:
1. On login/token check: try Redis session first, fall back to JWT validation
2. If the JWT validates, create a Redis session and return the new session key
3. After a reasonable window (1-2 weeks), remove the JWT fallback

Want to start with the fallback logic in auth/session.py?
```

You did not explain any of this. The history was stored at the end of last Tuesday's session and recalled automatically today.

---

## Example 6: Asking About a Decision

**You say:**

```
Why are we using Redis for sessions? Can we just use the database?
```

**Claude runs:**

```
session_recall(query="Redis sessions database")
```

**Claude receives:**

```
[Decision recorded 2026-04-12]
Title: Redis sessions, not JWT
Context: Enterprise customers need server-side revocation. JWT cannot be
         revoked without a blocklist, which is equivalent to a session store
         anyway. Redis gives revocation + simpler logout.
```

**Claude responds:**

```
The decision was made on 2026-04-12: enterprise customers require the ability
to revoke sessions immediately (e.g., force-logout when an employee is terminated).

JWT cannot be revoked without maintaining a blocklist — and a blocklist is
effectively a session store. Redis was chosen over the database because it
is faster for per-request session lookups (no SQL query overhead) and supports
TTL natively (sessions expire without a cleanup job).

Using the database would work, but you would need either a background job to
purge expired rows or a partial index on the expiry column. Redis handles both
automatically.

If you want to move to the database anyway (e.g., to reduce infrastructure
dependencies), that is viable — the tradeoff is slightly higher latency per
request and a cleanup job to manage.
```

Claude did not guess. It recalled the exact reasoning from the session where the decision was made.

---

## Example 7: Checking the Index

**You say:**

```
How many files have you indexed? Is anything stale?
```

**Claude runs:**

```
index_status()
```

**Claude receives:**

```
Project: my-ecommerce-app
Chunks: 1,847
Files: 134
Stale files: 2
  - payments/apple_pay.py  (modified 8 minutes ago, not yet indexed)
  - tests/test_checkout.py (modified 8 minutes ago, not yet indexed)
Queries run: 67
Tokens saved: 71% (est. 284,000 tokens saved vs full-file reads)
```

**Claude responds:**

```
1,847 chunks across 134 files indexed. Two files modified in the last 8 minutes
are not yet indexed: payments/apple_pay.py and tests/test_checkout.py.

If you want me to see your latest changes to those files, run:

    cce index

or commit your changes (the git hook re-indexes automatically on commit).
```

---

## Tips for Getting the Most Out of CCE

**Ask naturally.** CCE searches automatically — you do not need to say "search for" or reference file names. Just describe what you want.

```
✓  "How does user authentication work?"
✓  "Show me how we handle failed payments"
✓  "Where is the order status updated?"

—  "Search for the authenticate function"  (works, but unnecessary)
—  "Read auth/session.py"                  (bypasses CCE, reads the whole file)
```

**Let Claude find the files.** Do not paste code unless Claude specifically asks for it. Pasting defeats the purpose of the index.

```
✓  "There's a bug in the shipping cost calculation. The method 'express' isn't found."
—  "Here is the entire shipping.py file: [pastes 400 lines]"
```

**Tell Claude what you decided.** When you make a choice that future sessions should know about, ask Claude to record it:

```
"We decided to use Celery for background jobs instead of RQ.
 Record that decision — the reason is that Celery has better Django integration
 and the team already knows it."
```

Claude will call `record_decision` and the reasoning will be available in every future session.

**Adjust verbosity if you want shorter answers:**

```
"Switch to max output compression"   ← shorter, more direct responses
"Turn off output compression"        ← full responses
```

---

## When CCE Searches Automatically

You do not invoke these tools — Claude does. They trigger on natural questions:

| What you ask | Tool Claude calls |
|---|---|
| "How does X work?" | `context_search` |
| "Find the function that does Y" | `context_search` |
| "Why did we choose Z?" | `session_recall` |
| "What did we work on last week?" | `session_recall` |
| "Show me the full body of that function" | `expand_chunk` |
| "Is the index up to date?" | `index_status` |

---

## See Also

- [CCE In Practice](CCE-In-Practice) — the same scenarios with token counts and internals
- [CLI Reference](CLI-Reference) — all `cce` commands
- [Configuration](Configuration) — tuning retrieval, compression, and ignored files
