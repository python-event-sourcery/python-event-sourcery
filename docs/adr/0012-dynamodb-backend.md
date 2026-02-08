# 12. DynamoDB Backend for Event Store

Date: 2024-02-08

## Status

Proposed

## Context

Python Event Sourcery needs to support AWS-native applications, particularly those built on serverless architectures using AWS Lambda and DynamoDB. The growing adoption of serverless computing creates demand for an event store backend that integrates naturally with AWS services without requiring managed relational databases.

DynamoDB offers:
- Serverless, fully managed NoSQL database
- Automatic scaling and high availability
- Pay-per-request pricing model
- Global tables for multi-region deployments
- Native integration with AWS Lambda and other AWS services

However, DynamoDB lacks:
- ACID transactions across multiple items/tables
- Strong consistency guarantees by default
- Complex querying capabilities
- Native ordering guarantees beyond partition keys

## Decision

We will implement a non-transactional DynamoDB backend that extends the base `Backend` class (not `TransactionalBackend`). This backend will prioritize scalability and AWS-native integration over transactional guarantees.

### Table Design

**Events Table Schema:**
- Partition Key: `stream_id` (String)
- Sort Key: `position` (Number)
- Attributes:
  - `event_id` (String) - UUID
  - `event_type` (String)
  - `event_version` (String)
  - `created_at` (String) - ISO timestamp
  - `metadata` (Map)
  - `data` (Binary) - Serialized event data
  - `tenant_id` (String) - For multi-tenancy
  - `global_position` (Number) - For subscriptions

**Global Secondary Indexes:**
1. **GlobalPositionIndex**
   - Partition Key: `tenant_id`
   - Sort Key: `global_position`
   - Purpose: Enable subscription queries across all streams

2. **EventTypeIndex** (Optional)
   - Partition Key: `event_type`
   - Sort Key: `created_at`
   - Purpose: Query events by type

**Snapshots Table Schema:**
- Partition Key: `stream_id` (String)
- Sort Key: `position` (Number)
- Attributes:
  - `snapshot_id` (String)
  - `created_at` (String)
  - `data` (Binary)
  - `tenant_id` (String)

**Subscriptions Table Schema:**
- Partition Key: `subscription_id` (String)
- Sort Key: `tenant_id` (String)
- Attributes:
  - `position` (Number)
  - `updated_at` (String)

### Implementation Approach

1. **Non-Transactional Nature**: Clearly document that this backend does not provide transactional guarantees
2. **Eventual Consistency**: Use eventually consistent reads by default, with option for strongly consistent reads
3. **Batch Operations**: Utilize DynamoDB batch operations for performance
4. **Position Tracking**: Use atomic counters for maintaining global position
5. **Subscription Polling**: Implement efficient polling with exponential backoff

## Consequences

### Positive

- **Serverless-First**: Natural fit for AWS Lambda and serverless architectures
- **Scalability**: Virtually unlimited scalability with DynamoDB
- **Cost-Effective**: Pay-per-request model ideal for variable workloads
- **Global Distribution**: Support for global tables enables multi-region deployments
- **Operational Simplicity**: No database management required

### Negative

- **No Transactions**: Cannot guarantee atomicity across multiple operations
- **Eventual Consistency**: May see stale data in certain scenarios
- **Limited Querying**: Complex queries require careful GSI design or scanning
- **Outbox Pattern Limitations**: Without transactions, exactly-once delivery is challenging
- **Cost at Scale**: Can become expensive with high-frequency polling or large payloads

### Neutral

- **Different Mental Model**: Developers must understand DynamoDB's consistency model
- **AWS Lock-in**: Tightly coupled to AWS ecosystem
- **Learning Curve**: Requires understanding of DynamoDB best practices

## Implementation Guidelines

1. **Clear Documentation**: Extensively document when to use/not use this backend
2. **Configuration Options**: Provide tuning options for consistency, polling intervals
3. **Cost Awareness**: Include utilities to estimate DynamoDB costs
4. **Migration Support**: Provide tools to migrate between backends
5. **Testing**: Ensure all generic event store tests pass, with appropriate markers for non-transactional behavior

## References

- [DynamoDB Best Practices](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/best-practices.html)
- [Event Sourcing on AWS](https://aws.amazon.com/blogs/database/building-an-event-store-on-amazon-dynamodb/)
- [DynamoDB Consistency Models](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/HowItWorks.ReadConsistency.html)