from flask import Blueprint, request, make_response
from . import base_api
from znatoks import authorize

get_list_blueprint = Blueprint('get_watched_tasks', __name__)
UNIQUE_RANGE = 'D{}:F{}'


@get_list_blueprint.route(base_api + 'get_list', methods=['GET'])
def get_list():
    start = request.args.get('start', default=1, type=int)
    limit = request.args.get('limit', default=50, type=int)
    if start <= 0 or limit <= 0:
        return make_response(dict(ok=False, error='incorrect parameters. "start" and "limit" must be greater than 0'), 200)
    sheet = authorize().open('Кандидаты(версия 2)').worksheet('watched_tasks')
    tasks = sheet.get(UNIQUE_RANGE.format(start, start+limit-1))
    next_page = None
    if len(tasks) == limit:
        next_page = request.base_url + '?start={}&limit={}'.format(start + limit, limit)
    return make_response(dict(ok=True, tasks=tasks, next=next_page), 200)
