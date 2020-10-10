import requests
import json
import constants
from flask import jsonify
from slack import WebClient


def is_admin(client: WebClient, user_id):
    user_info_resp = client.users_info(user=user_id)
    if user_info_resp['user']['is_admin'] or user_info_resp['user']['id'] in client.conversations_members(channel=constants.ADMIN_CHANNEL_ID):
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