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
from znatoks import authorize


event_endpoint_blueprint = Blueprint('event_endpoint', __name__)
slack_event_adapter = SlackEventAdapter(constants.SLACK_SIGNING_SECRET, endpoint='/event_endpoint',
                                        server=event_endpoint_blueprint)


def get_answered_users(link):
    request = requests.get(link, json.load(open('files/headers.json', 'r')))
    if request.status_code == 200:
        beautiful_soup = BeautifulSoup(request.text, 'lxml')
        return [div_el.span.text.replace('\n', '').lower()
                for div_el
                in beautiful_soup.find_all('div', {'class': "brn-qpage-next-answer-box-author__description"})]
    else:
        return []


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
        current_timestamp = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%m/%d/%Y %H:%M:%S')
        if expert_name:
            expert_name = expert_name[0]
            try:
                # find link in attachments
                if response['messages']:
                    link = response['messages'][0]['attachments'][0]['title_link']
            except KeyError:
                # TODO: find link in text
                return
            if expert_name.lower() in get_answered_users(link):
                client = authorize()
                spreadsheet = client.open('Кандидаты(версия 2)').worksheet('test_list')
                spreadsheet.append_row([current_timestamp, 'решение', expert_name, link])
        conn.execute('insert into events_history(link, nickname, smile, event_time)'
                     'values (:link, :nickname, :smile, :event_time)',
                     {"link": link, "nickname": expert_name, "smile": emoji, "event_time": current_timestamp})
        conn.commit()