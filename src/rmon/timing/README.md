## Code timings
This example code uses tools within this package to measure and report code timings. All of this
code adds overhead to program execution and so you should be aware of the impacts. You will likely
will not want to use this in code that is short in duration and called many times.

Note that you must configure logging and enable messages for the `resource_monitor` package.
If you are not familiar with this, consider creating a logger with this example code:

```
from rmon.loggers import setup_logging

setup_logging(filename="timing.log")
```

### Report function durations
If you decorate your function with `timed_info`, it will log the function execution duration
every time it runs.

```
from rmon import timed_info

@timed_info
def my_function():
    do_work()
```

If you only want to see log messages when a threshold is exceeded, use the code below instead.
```
from rmon.timing.timer_utils import timed_threshold

@timed_threshold(1.0)
def my_function():
    do_work()
```

### Report aggregated stats of frequently-called functions or code blocks.
```
from rmon import Timer, TimerStatsCollector, track_timing

timer_stats_collector = TimerStatsCollector(is_enabled=True)

@track_timing(timer_stats_collector)
def foo()
    do_work()

def bar():
    with Timer(timer_stats_collector, "my_code_block"):
        do_work()
```

Before your application exits call one or both of these functions to report min, max, average, and count
of those code blocks.

```
timer_stats_collector.log_stats()
timer_stats_collector.log_json_stats("timings.json")
```
*Note*: `log_json_stats` produces line-delimited JSON. You can install `jq` and use it to produce an
array of JSON objects.
```
jq -s . timings.json
```
