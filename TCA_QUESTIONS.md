# TCA questions: changes held for a separate decision

These four changes touch code that produces or stores TCA results, so they were held back from the other fixes until
each had been looked at on its own: what it does, whether calculation results can change, and what breaks without it.

**Decision: all four approved.** They are committed one per change; see "TCA fixes" in
[MIGRATION_NOTES.md](MIGRATION_NOTES.md). With all four, the reference TCA calculation (EURUSD, 1-12 May 2017) gives
identical results: 25 trades, mean slippage -0.000013700306, sum of arrival prices 27.2910554409.

---

## 1. `tcapy/analysis/algos/resultssummary.py`: histogram min/max as scalars

**Change** (`_create_histogram_distribution`):

```diff
-        min_hist_x = df.min()
-        max_hist_x = df.max()
+        min_hist_x = float(np.nanmin(df.values))
+        max_hist_x = float(np.nanmax(df.values))
```

**Why:** given a one-column DataFrame, `df.min()` returns a one-element Series, so `np.linspace` builds a 2-D array and
pandas raises `ValueError: Index data must be 1-dimensional`.

**Can results change?** Not for production paths. `field_distribution()` always passes a Series
(`metric_df[metric_name] * scalar`). For a Series, `Series.min()` and `np.nanmin(values)` both skip NaN and return the
same number. The only behaviour change is that a one-column DataFrame now works instead of crashing.

**Without it:** `test/test_tcapy/test_results_agg.py::test_histogram_generator` fails (it passes a DataFrame). The web
UI's distribution charts are unaffected either way.

**Decision:** approved.

---

## 2. `tcapy/util/timeseries.py`: `is` -> `==` for string comparisons

**Change** (8 lines):
- `TimeSeriesOps.date_parse()`: `date is 'midnight'`, `'decade'`, `'_year'`, `'month'`, `'week'`, `'day'`, `'hour'`
- `RandomiseTimeSeries.create_random_time_series()`: `freq is 'daily'`

**Why:** `is` tests object identity, not equality. It is only True when both strings happen to be the same object,
which is common for literals but not guaranteed (eg. strings built at runtime or read from config/web input). Python
3.8+ warns about this (`SyntaxWarning`).

**Can results change?** Only in the cases the old code got wrong:
- `date_parse('week')` etc.: if a caller passed an equal string that wasn't the same object, the old code skipped these
  branches and fell through to `strptime` parsing (which then failed or parsed differently). With `==` it always
  resolves the relative date. When the old `is` happened to be True, the result is identical.
- `create_random_time_series(freq='daily')`: same logic; generates business-day dates instead of 1-minute dates in the
  cases where the old check silently failed. Used by tests and sample data, not by TCA calculations.

**Without it:** behaviour stays as before (correct whenever the strings are the same object).

The same fix in three files outside the calculations (`tcapy/vis/candlestick.py`, `tcapy/vis/displaylisteners.py`,
`tcapy/data/databasepopulator.py`) went in with the general bug fixes, since none of them affects TCA numbers.

**Decision:** approved.

---

## 3. `tcapy/util/utilfunc.py`: empty-data check

**Change** (`check_data_frame_points_in_every_hour`):

```diff
+        if df is None or df.empty:
+            return False
+
         start_date_t = pd.Timestamp(start_date).replace(tzinfo=df.index.tz)
```

**Why:** with no data it crashed with `AttributeError: 'NoneType' object has no attribute 'index'` instead of
answering "no, data is missing".

**Can results change?** No TCA calculation calls it. It's only used by the data-vendor tests
(`test_data_vendor_feed.py`) to check downloaded data is complete. Returning `False` for no data is the answer the
function's docstring implies.

**Without it:** those tests fail with an `AttributeError` instead of a clear assertion that the data is missing. (They
can't pass either way while Dukascopy blocks findatapy's download requests.)

**Decision:** approved.

---

## 4. `tcapy/util/deltaizeserialize.py`: Parquet index fallback for the Redis cache

**Change:** new helper `_df_to_parquet()` used for both Parquet writes in `convert_python_to_binary()`. If writing a
table to Parquet fails **and** its index is a mixed-type object index, retry with the index converted to strings.
Tables that already serialise are written exactly as before.

**Why:** the markout table (`table_trade_df_markout_by_all`) has an index of trade timestamps plus one `'Avg'` summary
row. pyarrow 2.0 can't serialise that mixed index (`TypeError: an integer is required (got type str)`), so caching the
results failed.

**Can results change?** The numbers don't change. The one difference: in that fallback case the cached table's index
comes back from Redis as strings (eg. `'2017-05-01 12:56:50.596000+00:00'`, `'Avg'`) instead of Timestamps + `'Avg'`.
It's only used for HTML tables and CSV downloads, which render it as text anyway.

**Without it:** every **Detailed** and **Compliance** calculation in the web UI fails with "an integer is required
(got type str)", and the **tcapyboard** upload calculation fails the same way. All three build a table with an `'Avg'`
summary row: the markout table (Detailed, tcapyboard) and the trade-outliers table (Compliance).

**Decision:** approved.
