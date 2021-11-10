from .watch import start_watch, end_watch
from .get_list import get_watched_tasks


def watch(link, activity, status=None, channel=None, ts=None):
    if activity == 'start':
        assert channel is not None and ts is not None and status is not None
        return start_watch(link, channel, ts, status)
    elif activity == 'end':
        deleted_rows = end_watch(link)
        return deleted_rows
    else:
        raise Exception('no such activity')


def get_list(start=1, limit=50):
    assert start >= 1 and limit >= 1
    tasks = get_watched_tasks(start, limit)
    if len(tasks) == limit:
        return tasks, start + limit, limit
    return tasks, None, None
