from flask import make_response
from znatoks import authorize
from gspread.utils import fill_gaps

UNIQUE_RANGE = 'A{}:D{}'
COUNT_COLS = 4


def get_watched_tasks(start=1, limit=50):
    if start <= 0 or limit <= 0:
        return make_response(dict(ok=False, error='incorrect parameters. "start" and "limit" must be greater than 0'), 200)
    sheet = authorize().open('Кандидаты(версия 2)').worksheet('watched_tasks_unique')
    tasks = fill_gaps(sheet.get(UNIQUE_RANGE.format(start, start+limit-1)), cols=COUNT_COLS)
    return tasks
