import requests
import json
import constants
import slack.errors as slack_errors
from flask import jsonify
from slack import WebClient


def is_admin(client: WebClient, req):
    user_info_resp = client.users_info(user=req['user_id'])
    if user_info_resp['user']['is_admin'] or user_info_resp['user']['id'] in constants.WHITE_LIST:
        return True
    else:
        return False


def check_empty(req):
    if not req['text']:
        ephemeral_message(req['response_url'], "Запрос пустой")
        return True
    return False


def ephemeral_message(response_url, text=None, blocks=None):
    requests.post(response_url, data=json.dumps({'content_type': 'ephemeral', 'text': text, 'blocks': blocks}))


def reply(text: str):
    return jsonify(
        content_type='ephemeral',
        text=text
    )


def get_view(filename):
    with open(filename, 'r', encoding='utf-8') as form_file:
        return json.load(form_file)


def get_info_user(user_id):
    try:
        info = WebClient(token=constants.SLACK_OAUTH_TOKEN).users_info(user=user_id).data
        if info['ok']:
            return info
    except slack_errors.SlackApiError as e:
        raise e