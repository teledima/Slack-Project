from flask import Blueprint, request, make_response
from multiprocessing.pool import ThreadPool

import re
import cfscrape
from fp.fp import FreeProxy

from znatoks import authorize
from brainly_core import BrainlyTask, BlockedError, RequestError


popular_filtering_blueprint = Blueprint('popular_filtering', __name__)
spreadsheet = authorize().open('Кандидаты(версия 2)')
popular_sheet = spreadsheet.worksheet('popular-tasks')
deleted_tasks_sheet = spreadsheet.worksheet('deleted-tasks')


@popular_filtering_blueprint.route('/tasks/popular_filtering', methods=['GET'])
def popular_filter():
    if 'X-Appengine-Cron' not in request.headers or request.headers['X-Appengine-Cron'] is False:
        return make_response('', 403)
    try:
        subjects_filter = popular_sheet.get('H1:H', major_dimension='COLUMNS')[0]
    except KeyError:
        return make_response('', 200)
    deleted_tasks_sheet.clear()
    # получить все задачи в предметах, в которых хотим отбирать
    tasks = popular_sheet.batch_get(list(map(lambda cell: f'E{cell.row}:G{cell.row}',
                                             popular_sheet.findall(re.compile('|'.join(subjects_filter)), in_column=6)
                                             )
                                         ),
                                    major_dimension='ROWS'
                                    )

    # отфильтровать уже отмеченные задачи
    tasks_no_marked = [task_info[0] for _, task_info in enumerate(tasks) if len(task_info[0]) == 2]
    chunked_tasks = chunks(tasks_no_marked, 20)
    with ThreadPool(len(chunked_tasks)) as pool:
        pool.map(chunk_filter, chunked_tasks)
    return make_response('', 200)


def chunks(lst, n):
    """Return successive n-sized chunks from lst."""
    n = max(1, n)
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def chunk_filter(tasks_list):
    scraper = cfscrape.Session()
    scraper.proxies = {'http': FreeProxy().get()}
    for task_info_raw in tasks_list:
        try:
            task_info = BrainlyTask.get_info(task_info_raw[0], session=scraper)
            # если есть два ответа
            if len(task_info.answered_users) == 2:
                task_info_raw += ['two-answers']
        except RequestError as req_err:
            # задача удалена
            if req_err.code == 10:
                task_info_raw += ['deleted']
        except BlockedError:
            pass
    marked_link = [[task_info[0]] for _, task_info in enumerate(tasks_list) if len(task_info) == 3]
    deleted_tasks_sheet.insert_rows(marked_link)
