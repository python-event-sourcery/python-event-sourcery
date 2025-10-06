Subscriptions allow for asynchronous processing of events in another process.

Having [Backend] object after [integrating with your application](integrate.md), grab its `.subscriber` to start building a subscription.

## Iterating over events one by one

Let's say we want to know about all paid invoices and we have an event for that - `InvoicePaid`.

```python
--8<--
docs/code/test_recipes.py:subscriptions_01
--8<--
```

`subscription` is an iterable. Thus, it can be used with for loop:

```python
--8<--
docs/code/test_recipes.py:subscriptions_02
--8<--
```

With every iteration we're getting an instance of [Recorded] or `None` if there are no new events available.

!!! note

    `subscription` is an infinite iterator. Getting `None` means that you are 'up-to-date' with Event Store
    but as soon as a new event is appended, it will be returned in another iteration of the loop.

## Iterating over events in batches

When we have to process a bigger amount of events it makes sense to do it in batches instead of processing events one by one.

To do it, we need to slightly alter code responsible for building our `subscription`. Instead of `build_iter` we call `build_batch`:

```python
--8<--
docs/code/test_recipes.py:subscriptions_03
--8<--
```

Then we can pass `subscritpion` to for loop:

```python
--8<--
docs/code/test_recipes.py:subscriptions_04
--8<--
```

In this example, batch is a list of [Recorded].

Just like in previous case, `subscription` is an infinite iterator. It will be returning batches of given size as long as there is enough events.

If there are fewer 'new' events available, batch subscription will return whatever it can. For example, if you specify batch size of 10 but get a list with 7 events, it means there were only 7 new events and time limit has passed.

When batch subscription catches up with event store, it will be returning empty lists. At least until some new events are saved.

[Recorded]: ../reference/event_store/event.md#event_sourceryevent_storeeventrecorded
[Backend]: ../reference/event_store/backend.md#event_sourceryevent_storebackendbackend
