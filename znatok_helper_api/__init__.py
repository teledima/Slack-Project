from flask import Blueprint, request, make_response

from .watch import start_watch, end_watch
from .get_list import get_watched_tasks

znatok_helper_blueprint = Blueprint('znatok_helper_blueprint', __name__, url_prefix='/znatok_helper_api')


@znatok_helper_blueprint.route('/watch', methods=['POST'])
def watch():
    link_id = str(request.json['link_id'])
    channel_id = str(request.json['channel_id']) if 'channel_id' in request.json else None
    ts = str(request.json['ts']) if 'ts' in request.json and 'channel_id' in request.json else None
    activity = request.json['activity']
    if activity == 'start':
        status = request.json['status'] if 'status' in request.json else None

        return make_response(
            dict(ok=start_watch(link_id, channel_id, ts, status)),
            200
        )
    elif activity == 'end':
        deleted_rows = end_watch(link_id, channel_id, ts)
        return make_response(dict(ok=True, deleted_rows=deleted_rows), 200)
    else:
        return make_response(dict(ok=False, error='no such activity'), 200)


@znatok_helper_blueprint.route('/get_list', methods=['GET'])
def get_list():
    start = request.args.get('start', default=1, type=int)
    limit = request.args.get('limit', default=50, type=int)
    if start <= 0 or limit <= 0:
        return make_response(dict(ok=False, error='incorrect parameters. "start" and "limit" must be greater than 0'), 200)
    tasks = get_watched_tasks(start, limit)
    next_page = None
    if len(tasks) == limit:
        next_page = request.base_url + '?start={}&limit={}'.format(start + limit, limit)
    return make_response(dict(ok=True, tasks=tasks, next=next_page), 200)
