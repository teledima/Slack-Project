from flask import Blueprint, request, make_response
from znatoks import authorize
from . import base_api

watch_blueprint = Blueprint('watch', __name__)


@watch_blueprint.route(base_api + 'watch', methods=['POST'])
def watch():
    link_id = str(request.json['link_id'])
    activity = request.json['activity']
    sheet = authorize().open('Кандидаты(версия 2)').worksheet('watched_tasks')
    if activity == 'start':
        channel_id = request.json['channel_id']
        ts = request.json['ts']
        sheet.append_row([link_id, channel_id, ts])
        return make_response(dict(ok=True), 200)
    elif activity == 'end':
        rows = [cell.row for cell in sheet.findall(query=link_id, in_column=1)]
        rows.sort(reverse=True)
        [sheet.delete_row(row) for row in rows]
        return make_response(dict(ok=True, deleted_rows=len(rows)), 200)
    else:
        return make_response(dict(ok=False, error='no such activity'), 200)
