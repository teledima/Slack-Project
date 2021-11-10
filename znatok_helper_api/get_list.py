from slack_core.sheets import authorize
from gspread.utils import fill_gaps

UNIQUE_RANGE = 'A{}:D{}'
COUNT_COLS = 4


def get_watched_tasks(start=1, limit=50):
    if start <= 0 or limit <= 0:
        raise Exception("start or limit less 0")
    sheet = authorize().open('Кандидаты(версия 2)').worksheet('watched_tasks_unique')
    try:
        tasks = fill_gaps(sheet.get(UNIQUE_RANGE.format(start, start+limit-1)), cols=COUNT_COLS)
    except KeyError:
        tasks = []
    return [dict(taskId=int(task[0].split('/').pop()), channel=task[1], ts=task[2], status=task[3]) for task in tasks]
