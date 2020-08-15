import constants
import requests
import json
import znatoks
import re
import gspread.exceptions as errors_sheet
from flask import Flask, request, make_response, jsonify
from slack.web.classes import blocks
from slack.web.client import WebClient
from slack.errors import SlackApiError
from tasks import async_task


app = Flask(__name__)


def ephemeral_message(response_url, text=None, blocks=None):
    requests.post(response_url, data=json.dumps({'content_type': 'ephemeral', 'text': text, 'blocks': blocks}))


def reply(text: str):
    return jsonify(
        content_type='ephemeral',
        text=text
    )


def is_admin(client, req):
    user_info_resp = client.users_info(user=req['user_id'])
    if user_info_resp['user']['is_admin'] or user_info_resp['user']['id'] in constants.WHITE_LIST:
        return True
    else:
        return False

def check_empty(req):
    if not req['text']:
        ephemeral_message(req['response_url'], req['text'])


@app.route('/')
def hello():
    return "Hello, Slack App!"


@app.route('/get_info', methods=['POST'])
def get_info():
    req = request.form
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_TEST)
    if not is_admin(client, req):
        return reply("You don't have permission")
    check_empty(req)
    get_info_background(request.form)
    return reply('Got it!')


@async_task
def get_info_background(req):
    info = znatoks.find_user_spreadsheet(req['text'])
    if all(i is None for i in info):
        ephemeral_message(req['response_url'], 'User is not found')
        return
    sections = []
    for row in info:
        if row is not None:
            for key in row.keys():
                sections.append(
                    blocks.SectionBlock(text=blocks.TextObject(f'_*{key}*_: {row[key]}', 'mrkdwn')).to_dict())
            sections.append(blocks.DividerBlock().to_dict())
    ephemeral_message(req['response_url'], blocks=sections)


@app.route('/wonderful_answer', methods=['POST'])
def wonderful_answer():
    req = request.form
    check_empty(req)
    wonderful_answer_background(req)
    return reply('Привет! Сейчас мы немного проверим и посчитаем этот ответ')


@async_task
def wonderful_answer_background(req):
    params = req['text'].split()
    url = params[0]
    who_add_ans = None if len(params) == 1 else params[1]
    result = znatoks.is_correct_request(url, req['user_id'], who_add_ans)
    if not result['ok']:
        if result['cause'] == 'same_user':
            ephemeral_message(req['response_url'], 'Вы не можете отправлять свои ответы')
            return
        elif result['cause'] == 'blocked_error':
            ephemeral_message(req['response_url'], 'Извините, произошла ошибка при проверке ответа. Попробуйте позже')
            return
        elif result['cause'] == 'slack_api_error':
            ephemeral_message(req['response_url'], f'Ошибка при запросе к Slack API: {result["description"]}')
            return
    wonderful_answer_table = znatoks.authorize().open('Copy of Кандидаты').worksheet('wonderful answer')
    cells = wonderful_answer_table.findall(url, in_column=1)
    if len(cells) == 1:
        count_cell = wonderful_answer_table.cell(cells[0].row, cells[0].col+1)
        wonderful_answer_table.update_cell(count_cell.row, count_cell.col, int(count_cell.value)+1)
        pass
    elif len(cells) > 1:
        for cell in cells:
            nick_name = wonderful_answer_table.cell(cell.row, cell.col+2)
        pass
    else:  # url doesn't exist in the table yet
        wonderful_answer_table.insert_row([url, 0], znatoks.next_available_row(wonderful_answer_table))
    ephemeral_message(req['response_url'], 'Answer added!')


@app.route('/entry_point', methods=["POST"])
def entry_point():
    payload = json.loads(request.form['payload'])
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN)
    if payload['type'] == 'shortcut':
        try:
            client.views_open(trigger_id=payload['trigger_id'], view=get_view('files/validate_form.json'))
            return make_response('', 200)
        except SlackApiError as e:
            code = e.response["error"]
            return make_response(f"Failed to open a modal due to {code}", 200)
    elif payload['type'] == 'block_actions':
        if payload['view']['callback_id'] == 'valid_form':
            value = payload['actions'][0]['selected_option']['value']
            client.views_update(view=get_view(f'files/form_add_{value}.json'), view_id=payload['view']['id'])
    elif payload['type'] == 'view_submission':
        if payload['view']['callback_id'] == 'expert_form':
            form_expert_submit(client, payload)
        elif payload['view']['callback_id'] == 'candidate_form':
            form_candidate_submit(client, payload)
        return make_response('', 200)

    return make_response('', 404)


@async_task
def form_candidate_submit(client, payload):
    user_info = {'profile': None, 'nick': None, 'name': None,
                 'statuses': None, 'tutor': None, 'subject': None, 'happy_birthday': None, 'is_auto_check': False}
    pass


@async_task
def form_expert_submit(client, payload):
    pass


def get_view(filename):
    with open(filename, 'r', encoding='utf-8') as form_file:
        return json.load(form_file)
