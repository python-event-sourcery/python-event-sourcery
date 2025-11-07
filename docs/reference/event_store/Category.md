Represents a logical grouping or classification of event streams.

`Category` is typically used to organize streams by aggregate type, business domain, or other criteria.

It allows for efficient querying, filtering, and subscription to related streams as a group. In most implementations, it is simply an alias for `str`, but its semantic meaning is important for event sourcing patterns such as category-based subscriptions.

::: event_sourcery.Category
