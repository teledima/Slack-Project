from flask import Blueprint
from slackeventsapi import SlackEventAdapter
from slack_sdk.web import WebClient
from bs4 import BeautifulSoup
import constants
import requests
import sqlite3
import json
import pytz
from datetime import datetime

from events_slack.expert_errors import *
from znatoks import authorize


event_endpoint_blueprint = Blueprint('event_endpoint', __name__)
slack_event_adapter = SlackEventAdapter(constants.SLACK_SIGNING_SECRET, endpoint='/event_endpoint',
                                        server=event_endpoint_blueprint)


def get_answered_users(link):
    request = requests.get(link, json.load(open('files/headers.json', 'r')))
    if request.status_code == 200:
        beautiful_soup = BeautifulSoup(request.text, 'lxml')
        return dict(ok=True, users=[div_el.span.text.replace('\n', '').lower()
                                    for div_el
                                    in beautiful_soup.find_all('div', {'class': "brn-qpage-next-answer-box-author__description"})])
    else:
        return dict(ok=False, users=[])


def get_last_message_by_ts(channel, ts):
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN)
    return client.conversations_history(channel=channel,
                                        latest=float(ts)+1,
                                        limit=1)


@slack_event_adapter.on('reaction_added')
def reaction_added(event_data):
    emoji = event_data["event"]["reaction"]
    response = get_last_message_by_ts(event_data['event']['item']['channel'], event_data['event']['item']['ts'])
    conn = sqlite3.connect('files/smiles.db')
    if emoji == 'lower_left_ballpoint_pen':
        res = conn.execute('select send_notifications from white_list where user_id = :user_id',
                           {"user_id": event_data['event']['item_user']}).fetchone()
        if res and bool(res[0]) is True:
            client = WebClient(token=constants.SLACK_OAUTH_TOKEN)
            if response['ok']:
                client.chat_postMessage(channel=event_data['event']['item_user'],
                                        text=f"See your message {response['messages'][0]['text']}")
    else:
        link = None
        expert_name = conn.execute('select expert_name from smiles where name = :name', {"name": emoji}).fetchone()
        current_timestamp = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S')
        try:
            expert_name = expert_name[0]
            try:
                # find link in attachments
                if response['messages']:
                    link = response['messages'][0]['attachments'][0]['title_link']
            except KeyError:
                # TODO: find link in text
                raise KeyError('Ссылка в проверке не найдена')
            answered_users = get_answered_users(link)
            client = authorize()
            spreadsheet = client.open('Кандидаты(версия 2)').worksheet('test_list')
            if answered_users['ok'] and expert_name.lower() in answered_users['users']:
                spreadsheet.append_row([current_timestamp, 'решение', expert_name, link])
            elif answered_users['ok'] == False:
                spreadsheet.append_row([current_timestamp, 'решение', expert_name, link, '?'])
            else:
                raise SmileExistsButUserHasNotAnswer(f'Смайл "{emoji}" существует но пользователь, который к нему привязан не отвечал на данный вопрос. Пользатель, к которому привязан смайл: {expert_name}. Пользователи, ответившие на вопрос "{link}": {answered_users}')
        except TypeError:
            if not expert_name:
                raise ExpertNameNotFound(f'Ник пользователя со смайлом {emoji} отсутствует в базе данных')
            else:
                raise TypeError
