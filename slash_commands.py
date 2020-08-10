import constants
import requests
import json
from flask import Flask, request, make_response, jsonify
from znatoks import find_user_spreadsheet
from slack.web.classes import blocks
from slack.web.client import WebClient
from slack.errors import SlackApiError
from tasks import async_task

app = Flask(__name__)


def ephemeral_message(response_url, text):
    requests.post(response_url, data=json.dumps({'content_type': 'ephemeral', 'text': text}))


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


@app.route('/get_info', methods=['POST'])
def get_info():
    req = request.form
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN)
    if not is_admin(client, req):
        return reply("You don't have permission")
    if not req['text']:
        return reply('Query is empty')
    get_info_background(client, request.form)
    return reply('Got it!')


@async_task
def get_info_background(client, req):
    info = find_user_spreadsheet(req['text'])
    if all(i is None for i in info):
        ephemeral_message(req['response_url'], 'User does not found')
        return
    sections = []
    for row in info:
        if row is not None:
            for key in row.keys():
                sections.append(
                    blocks.SectionBlock(text=blocks.TextObject(f'_*{key}*_: {row[key]}', 'mrkdwn')).to_dict())
            sections.append(blocks.DividerBlock().to_dict())
    client.chat_postEphemeral(channel=req['channel_id'], user=req['user_id'], blocks=sections)


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
