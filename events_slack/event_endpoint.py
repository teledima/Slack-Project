from flask import Blueprint
from slackeventsapi import SlackEventAdapter
from slack_sdk.web import WebClient
from slack_core import constants
import sqlite3
import pytz
from datetime import datetime
from brainly_core import BrainlyTask, RequestError, BlockedError
from events_slack.expert_errors import *
from znatoks import authorize
from slack_core.limiter import limiter
import re

event_endpoint_blueprint = Blueprint('event_endpoint', __name__)
slack_event_adapter = SlackEventAdapter(constants.SLACK_SIGNING_SECRET, endpoint='/event_endpoint',
                                        server=event_endpoint_blueprint)

limiter.limit("1 per 5 seconds")(event_endpoint_blueprint)


def get_last_message_by_ts(channel, ts):
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
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
            client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
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
                    last_message = response['messages'][0]
                    if 'attachments' in last_message:
                        link = last_message['attachments'][0]['title_link']
                    else:
                        link = re.search(r'https:/{2,}znanija\.com/+task/+\d+', last_message['text']).group()
            except KeyError:
                # TODO: find link in text
                raise KeyError('Ссылка в проверке не найдена')

            client = authorize()
            if event_data['event']['item']['channel'] == 'C5X27V19S':
                worksheet = client.open('Кандидаты(версия 2)').worksheet('test_list_popular')
            else:
                worksheet = client.open('Кандидаты(версия 2)').worksheet('test_list')
            try:
                answered_users = [answer.username.lower() for answer in BrainlyTask.get_info(link).answered_users]
                if expert_name.lower() in answered_users:
                    worksheet.append_row([current_timestamp, 'решение', expert_name, link])
                else:
                    raise SmileExistsButUserHasNotAnswer(f'Смайл "{emoji}" существует но пользователь, который к нему привязан не отвечал на данный вопрос. Пользатель, к которому привязан смайл: {expert_name}. Пользователи, ответившие на вопрос "{link}": {answered_users}')
            except (RequestError, BlockedError):
                worksheet.append_row([current_timestamp, 'решение', expert_name, link, '?'])
        except TypeError:
            if not expert_name:
                raise ExpertNameNotFound(f'Ник пользователя со смайлом {emoji} отсутствует в базе данных')
            else:
                raise TypeError
