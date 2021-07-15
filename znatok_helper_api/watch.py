from flask import Blueprint, request, make_response
from znatoks import authorize
from . import base_api
from slack_core.functions_sheets import find_rows

watch_blueprint = Blueprint('watch', __name__)


@watch_blueprint.route(base_api + 'watch', methods=['POST'])
def watch():
    link_id = str(request.json['link_id'])
    activity = request.json['activity']
    sheet = authorize().open('Кандидаты(версия 2)').worksheet('watched_tasks')
    if activity == 'start':
        channel_id = str(request.json['channel_id'])
        ts = str(request.json['ts'])
        status = request.json['status'] if 'status' in request.json else ''
        row_cells = find_rows(sheet, [link_id, channel_id, ts])

        if len(row_cells) >= 1:
            if len(row_cells) > 1:
                sheet.delete_row(row_cells.pop().row)
            [sheet.update_cell(row=cell.row, col=4, value=status)
             for cell in sheet.findall(query=link_id, in_column=1)]
        else:
            sheet.append_row([link_id, channel_id, ts, status])
        return make_response(dict(ok=True), 200)
    elif activity == 'end':
        channel_id = str(request.json['channel_id']) if 'channel_id' in request.json else ''
        ts = str(request.json['ts']) if 'ts' in request.json and 'channel_id' in request.json else ''
        rows = [row_cells[0].row for row_cells
                in find_rows(sheet, row_values=[link_id, channel_id, ts]) if len(row_cells) > 0]
        rows.sort(reverse=True)
        [sheet.delete_row(row) for row in rows]
        return make_response(dict(ok=True, deleted_rows=len(rows)), 200)
    else:
        return make_response(dict(ok=False, error='no such activity'), 200)
