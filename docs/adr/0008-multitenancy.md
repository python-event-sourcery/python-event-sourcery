- stream id is unique per tenant and in tenantless context
Consequences:
- tenant_id would have to be used as another part of id in projections outboxes
- outbox and projects - global, not per tenant

- ? tenant_id type - int or something more like
TODO: to ask Bottega and Order of Devs
