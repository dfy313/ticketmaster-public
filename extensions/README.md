# 📺 Ticketmaster – Extensions

This section explores several potential enhancements that could be made to the Ticketmaster architecture. While the current implementation is fully functional, real-world systems often evolve over time to address additional scalability, reliability, and operational concerns.

Each extension below highlights a limitation of the current design, discusses possible implementation approaches, and explains the benefits that the enhancement would provide.

## Extension #1 — CDC Pipeline for OpenSearch

<details>
<summary><strong>Show Details</strong></summary>

### Current Limitation

The current **Search Service** queries OpenSearch directly, but the system does not yet include a synchronization pipeline between MySQL and OpenSearch.

As a result, event data stored in OpenSearch can become stale over time. If events are created, updated, or deleted in MySQL, those changes are not automatically reflected in the search index.

### Proposed Enhancement

Introduce a **Change Data Capture (CDC) pipeline** between MySQL and OpenSearch that automatically captures event and ticket changes and propagates them to OpenSearch. This keeps the search index synchronized with MySQL while allowing updates to be applied asynchronously.

This architecture is similar to the CDC pipeline implemented in the **[URL Shortener Section 8](https://github.com/dfy313/url-shortener-public/tree/main/section_08)**, where database changes were streamed and processed by downstream consumers before being applied to additional data stores.

### Benefits

- Keeps OpenSearch eventually consistent with MySQL.
- Ensures newly created or updated events become searchable automatically.
- Reduces the risk of stale search results.
- More closely reflects real-world search architectures, where MySQL remains the source of truth and OpenSearch serves as a read-optimized search index.

<br>

</details>

## Extension #2 — Better Search Experience & UI

<details>
<summary><strong>Show Details</strong></summary>

### Current Limitation

The current **Search Service** supports a basic OpenSearch `match_phrase` query against event names.

While functional, this provides a fairly limited search experience. Users can only search by event name, and the home page simply redirects requests to a standalone search endpoint. Search results are not deeply integrated into the application UI and do not support common features such as filtering, sorting, or pagination.

### Proposed Enhancement

Expand search from simple event-name lookups into a richer event and ticket discovery experience. On the backend, the OpenSearch index could be expanded to include additional event and ticket metadata, such as:

- Event descriptions
- Event dates
- Venue information
- Ticket availability
- Ticket pricing
- Event categories and tags

On the frontend, the search experience could be enhanced with functionality commonly found in modern ticketing platforms, including:

- Filtering by date, price, availability, venue, category, etc.
- Sorting by relevance, date, price, etc.
- Pagination for large result sets
- Dedicated search results pages integrated into the main application UI

### Benefits

- Transforms search from a simple demo endpoint into a true event discovery feature.
- Allows users to discover events based on more than just exact event names.
- Improves the overall user experience by making large event catalogs easier to navigate.
- Provides a foundation for more advanced search and recommendation features in the future.

<br>

</details>

## Extension #3 — Event Creation & Management

<details>
<summary><strong>Show Details</strong></summary>

### Current Limitation

The current system focuses primarily on the customer-facing experience, including event discovery, ticket booking, the waiting queue, the live seat map, and search.

While users can browse and purchase tickets, the platform does not yet include an administrative workflow for creating, updating, or managing events and ticket inventory. As a result, event and ticket data must currently be populated outside of the application.

### Proposed Enhancement

Introduce an **Event Management Service** responsible for administering events and tickets. This service could expose APIs such as:

```text
POST /events
PATCH /events/{eventId}
DELETE /events/{eventId}

POST /events/{eventId}/tickets
PATCH /tickets/{ticketId}
DELETE /tickets/{ticketId}
```

### Benefits

- Completes the end-to-end lifecycle of the platform.
- Enables internal teams to manage events and ticket inventory directly.
- Provides a foundation for additional administrative tooling and workflows.

<br>

</details>

## Extension #4 — More Realistic Payment Processing

<details>
<summary><strong>Show Details</strong></summary>

### Current Limitation

The current booking flow demonstrates the overall reservation and purchase lifecycle, but payment processing is intentionally simplified.

While sufficient for demonstrating the booking flow, the current implementation omits many capabilities commonly found in production payment systems, such as saved payment methods, payment authorization and capture, refunds, payment history, and failure handling.

### Proposed Enhancement

Introduce a dedicated **Payment Service** responsible for managing customer payment methods and coordinating with an external payment provider such as Stripe. The Payment Service could expose APIs such as:

```text
POST /payment-methods
GET /payment-methods
DELETE /payment-methods/{paymentMethodId}

POST /payments
POST /payments/{paymentId}/capture
POST /payments/{paymentId}/refund
```

Payment methods would be associated with individual users and securely managed by the payment provider rather than stored directly within the Ticketmaster platform, helping isolate payment concerns from the core ticketing services.

### Benefits

- Separates payment concerns from booking and inventory management.
- Provides a foundation for additional capabilities such as fraud detection, chargeback handling, and multiple payment providers.
- Allows the booking workflow and payment workflow to evolve independently over time.

<br>

</details>

<br>
