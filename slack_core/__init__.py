import json

import firebase_admin
from firebase_admin import credentials
from slack_sdk import WebClient

from . import constants

cred = credentials.Certificate('files/slash-commands-archive-99df74bbe787.json')
firebase_admin.initialize_app(cred)


def get_view(filename):
    with open(filename, 'r', encoding='utf-8') as form_file:
        return json.load(form_file)


def is_admin(user_id):
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    response = client.users_info(user=user_id)
    return not response['user']['deleted'] and response['user']['is_admin']


def get_username(user_id):
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    response = client.users_info(user=user_id)
    return response['user']['profile']['display_name']
