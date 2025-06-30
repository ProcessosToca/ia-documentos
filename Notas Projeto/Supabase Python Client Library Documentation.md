# Supabase Python Client Library Documentation

## Python Client Library

`supabase-py`

This reference documents every object and method available in Supabase's Python library, `supabase-py`. You can use `supabase-py` to interact with your Postgres database, listen to database changes, invoke Deno Edge Functions, build login and user management functionality, and manage large files.

## Installing

### Install with PyPi

YouYou can install `supabase-py` via the terminal. (for Python > 3.8)

```bash
pip install supabase
```

## Initializing

You can initialize a new Supabase client using the `create_client()` method.

The Supabase client is your entrypoint to the rest of the Supabase functionality and is the easiest way to interact with everything we offer within the Supabase ecosystem.

### Parameters

*   `supabase_url` (Required, string)
    The unique Supabase URL which is supplied when you create a new project in your project dashboard.

*   `supabase_key` (Required, string)
    The unique Supabase Key which is supplied when you create a new project in your project dashboard.

*   `options` (Optional, ClientOptions)
    Options to change the Auth behaviors.

### `create_client()`

```python
import os
from supabase import create_client, Client

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)
```

## Fetch data

By default, Supabase projects return a maximum of 1,000 rows. This setting can be changed in your project's [API settings](https://supabase.com/docs/guides/api/rest/api-settings). It's recommended that you keep it low to limit the payload size of accidental or malicious requests. You can use `range()` queries to paginate through your data.

*   `select()` can be combined with [Filters](https://supabase.com/docs/reference/python/filters)
*   `select()` can be combined with [Modifiers](https://supabase.com/docs/reference/python/modifiers)
*   `apikey` is a reserved keyword if you're using the [Supabase Platform](https://supabase.com/platform) and [should be avoided as a column name](https://supabase.com/docs/guides/database/tables#column-names).

### Parameters

*   `columns` (Optional, string)
    The columns to retrieve, defaults to `*`.

*   `count` (Optional, CountMethod)
    The property to use to get the count of rows returned.


### Getting your data

*   Selecting specific columns
*   Query referenced tables
*   Query referenced tables through a join table
*   Query the same referenced table multiple times
*   Filtering through referenced tables
*   Querying referenced table with count
*   Querying with count option
*   Querying JSON data
*   Querying referenced table with inner join
*   Switching schemas per query

```python
response = (
    supabase.table("planets")
    .select("*")
    .execute()
)
```

### Data source

### Response

## Insert data

### Parameters

*   `json` (Required, dict, list)
    The values to insert. Pass a dict to insert a single row or a list to insert multiple rows.

*   `count` (Optional, CountMethod)
    The property to use to get the count of rows returned.

*   `returning` (Optional, ReturnMethod)
    Either 'minimal' or 'representation'. Defaults to 'representation'.

*   `default_to_null` (Optional, bool)
    Make missing fields default to `null`. Otherwise, use the default value for the column. Only applies for bulk inserts.

### Create a record

### Bulk create

```python
response = (
    supabase.table("planets")
    .insert({"id": 1, "name": "Pluto"})
    .execute()
)
```

### Data source

### Response

## Update data

`update()` should always be combined with [Filters](https://supabase.com/docs/reference/python/filters) to target the item(s) you wish to update.

### Parameters

*   `json` (Required, dict, list)
    The values to insert. Pass a dict to insert a single row or a list to insert multiple rows.

*   `count` (Optional, CountMethod)
    The property to use to get the count of rows returned.

### Updating your data

### Updating JSON data

```python
response = (
    supabase.table("instruments")
    .update({"name": "piano"})
    .eq("id", 1)
    .execute()
)
```

### Data source

### Response

## Upsert data

Primary keys must be included in the `values` dict to use upsert.

### Parameters

*   `json` (Required, dict, list)
    The values to insert. Pass a dict to insert a single row or a list to insert multiple rows.

*   `count` (Optional, CountMethod)
    The property to use to get the count of rows returned.

*   `returning` (Optional, ReturnMethod)
    Either 'minimal' or 'representation'. Defaults to 'representation'.

*   `ignore_duplicates` (Optional, bool)
    Whether duplicate rows should be ignored.

*   `on_conflict` (Optional, string)
    Specified columns to be made to work with UNIQUE constraint.

*   `default_to_null` (Optional, bool)
    Make missing fields default to `null`. Otherwise, use the default value for the column. Only applies for bulk inserts.

### Upsert your data

### Bulk Upsert your data

### Upserting into tables with constraints

```python
response = (
    supabase.table("instruments")
    .upsert({"id": 1, "name": "piano"})
    .execute()
)
```

### Data source

### Response

## Delete data

`delete()` should always be combined with [filters](https://supabase.com/docs/reference/python/filters) to target the item(s) you wish to delete.
If you use `delete()` with filters and you have [RLS](https://supabase.com/docs/guides/auth/row-level-security) enabled, only rows visible through `SELECT` policies are deleted. Note that by default no rows are visible, so you need at least one `SELECT`/`ALL` policy that makes the rows visible.
When using `delete().in_()`, specify an array of values to target multiple rows with a single query. This is particularly useful for batch deleting entries that share common criteria, such as deleting users by their IDs. Ensure that the array you provide accurately represents all records you intend to delete to avoid unintended data removal.

### Parameters

*   `count` (Optional, CountMethod)
    The property to use to get the count of rows returned.

*   `returning` (Optional, ReturnMethod)
    Either 'minimal' or 'representation'. Defaults to 'representation'.

### Delete records

### Delete multiple records

```python
response = (
    supabase.table("countries")
    .delete()
    .eq("id", 1)
    .execute()
)
```

### Data source

### Response

## Call a Postgres function

You can call Postgres functions as Remote Procedure Calls, logic in your database that you can execute from anywhere. Functions are useful when the logic rarely changes—like for password resets and updates.

```sql
create or replace function hello_world() returns text as $$
  select 'Hello world';
$$ language sql;
```

### Parameters

*   `fn` (Required, callable)
    The stored procedure call to be executed.

*   `params` (Optional, dict of any)
    Parameters passed into the stored procedure call.

*   `get` (Optional, dict of any)
    When set to true, data will not be returned. Useful if you only need the count.

*   `head` (Optional, dict of any)
    When set to true, the function will be called with read-only access mode.

*   `count` (Optional, CountMethod)
    Count algorithm to use to count rows returned by the function. Only applicable for [set-returning functions](https://www.postgresql.org/docs/current/xfunc-sql.html#XFUNC-SQL-SET-RETURN). "exact": Exact but slow count algorithm. Performs a `COUNT(*)` under the hood. "planned": Approximated but fast count algorithm. Uses the Postgres statistics under the hood. "estimated": Uses exact count for low numbers and planned count for high numbers.

### Call a Postgres function without arguments

### Call a Postgres function with arguments

### Bulk processing

### Call a Postgres function with filters

### Call a read-only Postgres function

```python
response = (
    supabase.rpc("hello_world")
    .execute()
)
```

### Data source

### Response

## Using filters

Filters allow you to only return rows that match certain conditions.

Filters can be used on `select()`, `update()`, `upsert()`, and `delete()` queries.

If a Postgres function returns a table response, you can also apply filters.

### Applying Filters

### Chaining

### Conditional chaining

### Filter by values within JSON column

### Filter Foreign Tables

```python
# Correct
response = (
    supabase.table("instruments")
    .select("name, section_id")
    .eq("name", "flute")
    .execute()
)
# Incorrect
response = (
    supabase.table("instruments")
    .eq("name", "flute")
    .select("name, section_id")
    .execute()
)
```

### Data source

### Notes

### Column is equal to a value

Match only rows where `column` is equal to `value`.

#### Parameters

*   `column` (Required, string)
    The column to filter on

*   `value` (Required, any)
    The value to filter by

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .eq("name", "Earth")
    .execute()
)
```

### Data source

### Response

### Column is not equal to a value

Match only rows where `column` is not equal to `value`.

#### Parameters

*   `column` (Required, string)
    The column to filter on

*   `value` (Required, any)
    The value to filter by

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .neq("name", "Earth")
    .execute()
)
```

### Data source

### Response

### Column is greater than a value

Match only rows where `column` is greater than `value`.

#### Parameters

*   `column` (Required, string)
    The column to filter on

*   `value` (Required, any)
    The value to filter by

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .gt("id", 2)
    .execute()
)
```

### Data source

### Response

### Notes

### Column is greater than or equal to a value

Match only rows where `column` is greater than or equal to `value`.

#### Parameters

*   `column` (Required, string)
    The column to filter on

*   `value` (Required, any)
    The value to filter by

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .gte("id", 2)
    .execute()
)
```

### Data source

### Response

### Column is less than a value

Match only rows where `column` is less than `value`.

#### Parameters

*   `column` (Required, string)
    The column to filter on

*   `value` (Required, any)
    The value to filter by

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .lt("id", 2)
    .execute()
)
```

### Data source

### Response

### Column is less than or equal to a value

Match only rows where `column` is less than or equal to `value`.

#### Parameters

*   `column` (Required, string)
    The column to filter on

*   `value` (Required, any)
    The value to filter by

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .lte("id", 2)
    .execute()
)
```

### Data source

### Response

### Column matches a pattern

Match only rows where `column` matches `pattern` case-sensitively.

#### Parameters

*   `column` (Required, string)
    The name of the column to apply a filter on

*   `pattern` (Required, string)
    The pattern to match by

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .like("name", "%Ea%")
    .execute()
)
```

### Data source

### Response

### Column matches a case-insensitive pattern

Match only rows where `column` matches `pattern` case-insensitively.

#### Parameters

*   `column` (Required, string)
    The name of the column to apply a filter on

*   `pattern` (Required, string)
    The pattern to match by

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .ilike("name", "%ea%")
    .execute()
)
```

### Data source

### Response

### Column is a value

Match only rows where `column` IS `value`.

#### Parameters

*   `column` (Required, string)
    The name of the column to apply a filter on

*   `value` (Required, null | boolean)
    The value to match by

### Checking for nullness, True or False

```python
response = (
    supabase.table("planets")
    .select("*")
    .is_("name", "null")
    .execute()
)
```

### Data source

### Response

### Notes

### Column is in an array

Match only rows where `column` is included in the `values` array.

#### Parameters

*   `column` (Required, string)
    The column to filter on

*   `values` (Required, array)
    The values to filter by

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .in_("name", ["Earth", "Mars"])
    .execute()
)
```

### Data source

### Response

### Column contains every element in a value

Only relevant for `jsonb`, `array`, and `range` columns. Match only rows where `column` contains every element appearing in `value`.

#### Parameters

*   `column` (Required, string)
    The column to filter on

*   `values` (Required, object)
    The `jsonb`, `array`, or `range` value to filter with

### On array columns

### On range columns

### On `jsonb` columns

```python
response = (
    supabase.table("issues")
    .select("*")
    .contains("tags", ["is:open", "priority:low"])
    .execute()
)
```

### Data source

### Response

### Contained by value

Only relevant for `jsonb`, `array`, and `range` columns. Match only rows where every element appearing in `column` is contained by `value`.

#### Parameters

*   `column` (Required, string)
    The `jsonb`, `array`, or `range` column to filter on

*   `value` (Required, object)
    The `jsonb`, `array`, or `range` value to filter with

### On array columns

### On range columns

### On `jsonb` columns

```python
response = (
    supabase.table("classes")
    .select("name")
    .contained_by("days", ["monday", "tuesday", "wednesday", "friday"])
    .execute()
)
```

### Data source

### Response

### Greater than a range

Only relevant for `range` columns. Match only rows where every element in `column` is greater than any element in `range`.

#### Parameters

*   `column` (Required, string)
    The `range` column to filter on

*   `range` (Required, array)
    The range to filter with

#### With `select()`

```python
response = (
    supabase.table("reservations")
    .select("*")
    .range_gt("during", ["2000-01-02 08:00", "2000-01-02 09:00"])
    .execute()
)
```

### Data source

### Response

### Notes

### Greater than or equal to a range

Only relevant for `range` columns. Match only rows where every element in `column` is either contained in `range` or greater than any element in `range`.

#### Parameters

*   `column` (Required, string)
    The `range` column to filter on

*   `range` (Required, string)
    The range to filter with

#### With `select()`

```python
response = (
    supabase.table("reservations")
    .select("*")
    .range_gte("during", ["2000-01-02 08:30", "2000-01-02 09:30"])
    .execute()
)
```

### Data source

### Response

### Notes

### Less than a range

Only relevant for `range` columns. Match only rows where every element in `column` is less than any element in `range`.

#### Parameters

*   `column` (Required, string)
    The `range` column to filter on

*   `range` (Required, array)
    The range to filter with

#### With `select()`

```python
response = (
    supabase.table("reservations")
    .select("*")
    .range_lt("during", ["2000-01-01 15:00", "2000-01-01 16:00"])
    .execute()
)
```

### Data source

### Response

### Notes

### Less than or equal to a range

Only relevant for `range` columns. Match only rows where every element in `column` is less than any element in `range`.

#### Parameters

*   `column` (Required, string)
    The `range` column to filter on

*   `range` (Required, array)
    The range to filter with

#### With `select()`

```python
response = (
    supabase.table("reservations")
    .select("*")
    .range_lte("during", ["2000-01-01 14:00", "2000-01-01 16:00"])
    .execute()
)
```

### Data source

### Response

### Notes

### Mutually exclusive to a range

Only relevant for `range` columns. Match only rows where `column` is mutually exclusive to `range` and there can be no element between the two ranges.

#### Parameters

*   `column` (Required, string)
    The `range` column to filter on

*   `range` (Required, array)
    The range to filter with

#### With `select()`

```python
response = (
    supabase.table("reservations")
    .select("*")
    .range_adjacent("during", ["2000-01-01 12:00", "2000-01-01 13:00"])
    .execute()
)
```

### Data source

### Response

### Notes

### With a common element

Only relevant for `array` and `range` columns. Match only rows where `column` and `value` have an element in common.

#### Parameters

*   `column` (Required, string)
    The `array` or `range` column to filter on

*   `value` (Required, Iterable[Any])
    The `array` or `range` value to filter with

### On array columns

### On range columns

```python
response = (
    supabase.table("issues")
    .select("title")
    .overlaps("tags", ["is:closed", "severity:high"])
    .execute()
)
```

### Data source

### Response

### Match a string

Only relevant for `text` and `tsvector` columns. Match only rows where `column` matches the query string in `query`.

For more information, see [Postgres full text search](https://www.postgresql.org/docs/current/textsearch.html).

#### Parameters

*   `column` (Required, string)
    The `text` or `tsvector` column to filter on

*   `query` (Required, string)
    The query text to match with

*   `options` (Optional, object)
    Named parameters

### Details

### Text search

### Basic normalization

### Full normalization

### Websearch

```python
response = (
    supabase.table("texts")
    .select("content")
    .text_search(
        "content",
        "'eggs' & 'ham'",
        options={"config": "english"},
    )
    .execute()
)
```

### Data source

### Response

### Match an associated value

Match only rows where each column in `query` keys is equal to its associated value. Shorthand for multiple `.eq()`s.

#### Parameters

*   `query` (Required, dict)
    The object to filter with, with column names as keys mapped to their filter values

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .match({"id": 2, "name": "Earth"})
    .execute()
)
```

### Data source

### Response

### Don't match the filter

Match only rows which doesn't satisfy the filter. `not_` expects you to use the raw PostgREST syntax for the filter values.

`.not_.in_('id', '(5,6,7)')`  # Use `()` for `in` filter
`.not_.contains('arraycol', '{"a","b"}')`  # Use `{}` for array values

#### With `select()`

```python
response = (
    supabase.table("planets")
    .select("*")
    .not_.is_("name", "null")
    .execute()
)
```

### Data source



