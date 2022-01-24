from . import constants

import re
import json
import random
from string import ascii_letters

import firebase_admin
from firebase_admin import credentials
from slack_sdk import WebClient


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


def generate_random_id(length=10):
    return ''.join(random.choice(ascii_letters) for _ in range(length))


def _get_last_message_by_ts(channel, ts):
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    return client.conversations_history(channel=channel,
                                        latest=str(float(ts)+1),
                                        limit=1)


def extract_link_from_message(channel, ts):
    response = _get_last_message_by_ts(channel, ts)
    try:
        # find link
        if response['messages']:
            last_message = response['messages'][0]
            # in attachments
            if 'attachments' in last_message:
                return last_message['attachments'][0]['title_link']
            # directly in message text
            else:
                return re.search(r'https:/{2,}znanija\.com/+task/+\d+', last_message['text']).group()
    # if something went wrong
    except KeyError:
        raise KeyError('Ссылка в проверке не найдена')
