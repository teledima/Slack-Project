from flask import Blueprint

from slack_sdk.web import WebClient
from slack_sdk.models.blocks import SectionBlock, MarkdownTextObject, DividerBlock, ActionsBlock, ButtonElement, PlainTextInputElement, InputBlock, HeaderBlock
from slack_core import constants, get_view
from events_slack.expert_errors import *
from slackeventsapi import SlackEventAdapter

import pytz
import cfscrape
import re
from datetime import datetime
from firebase_admin import firestore

from brainly_core import BrainlyTask, RequestError, BlockedError
from slack_core.sheets import authorize


event_endpoint_blueprint = Blueprint('event_endpoint', __name__)
slack_event_adapter = SlackEventAdapter(constants.SLACK_SIGNING_SECRET, endpoint='/event_endpoint',
                                        server=event_endpoint_blueprint)

smiles_collection = firestore.client().collection('smiles')


def get_last_message_by_ts(channel, ts):
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    return client.conversations_history(channel=channel,
                                        latest=float(ts)+1,
                                        limit=1)


@slack_event_adapter.on('reaction_added')
def reaction_added(event_data):
    emoji = event_data["event"]["reaction"]
    response = get_last_message_by_ts(event_data['event']['item']['channel'], event_data['event']['item']['ts'])
    link = None
    doc = smiles_collection.document(emoji).get()
    current_timestamp = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S')
    if doc.exists:
        expert_name = doc.to_dict()['expert_name']
        try:
            # find link
            if response['messages']:
                last_message = response['messages'][0]
                # in attachments
                if 'attachments' in last_message:
                    link = last_message['attachments'][0]['title_link']
                # directly in message text
                else:
                    link = re.search(r'https:/{2,}znanija\.com/+task/+\d+', last_message['text']).group()
        # if something went wrong
        except KeyError:
            raise KeyError('Ссылка в проверке не найдена')

        client = authorize()
        # open 'popular' sheet
        if event_data['event']['item']['channel'] == 'C5X27V19S':
            worksheet = client.open('Кандидаты(версия 2)').worksheet('test_list_popular')
        # open sheet for archive
        else:
            worksheet = client.open('Кандидаты(версия 2)').worksheet('test_list')
        try:
            answered_users = [answer.username.lower()
                              for answer in BrainlyTask.get_info(link, cfscrape.create_scraper()).answered_users]
            if expert_name.lower() in answered_users:
                worksheet.append_row([current_timestamp, 'решение', expert_name, link])
            else:
                raise SmileExistsButUserHasNotAnswer(f'Смайл "{emoji}" существует но пользователь, который к нему привязан не отвечал на данный вопрос. Пользатель, к которому привязан смайл: {expert_name}. Пользователи, ответившие на вопрос "{link}": {answered_users}')
        except (RequestError, BlockedError):
            worksheet.append_row([current_timestamp, 'решение', expert_name, link, '?'])
    else:
        # TODO: отправить уведомление пользователю
        raise ExpertNameNotFound(f'Ник пользователя со смайлом {emoji} отсутствует в базе данных')


@slack_event_adapter.on('app_home_opened')
def app_home_opened(event_data):
    bot = WebClient(constants.SLACK_OAUTH_TOKEN_BOT)
    home_form = get_view('files/app_home_initial.json')
    list_smiles = [dict(id=doc.id, user_id=doc.get().get('user_id')) for doc in smiles_collection.list_documents()]

    if not list(filter(lambda smile: smile['user_id'] == event_data['event']['user'], list_smiles)):
        home_form['blocks'].append(SectionBlock(text=MarkdownTextObject(text='У вас ещё нет смайла. Добавьте его, чтобы отмечать свои ответы.')).to_dict())
        home_form['blocks'].append(InputBlock(block_id='new_smile_input_block', label='Смайлик',
                                              element=PlainTextInputElement(action_id='new_smile_input_action',  placeholder='Вставьте название вашего смайлика')).to_dict())
        home_form['blocks'].append(ActionsBlock(elements=[ButtonElement(action_id='add_new_smile', text='Добавить смайл', style='primary')]).to_dict())

    home_form['blocks'].append(HeaderBlock(text='Список смайликов').to_dict())
    home_form['blocks'].append(DividerBlock().to_dict())

    _ = [
            [
                home_form['blocks'].append(
                    SectionBlock(text=MarkdownTextObject(text=f':{smile["id"]}: этот у <@{smile["user_id"]}>')).to_dict()
                ),
                home_form['blocks'].append(ActionsBlock(elements=[ButtonElement(text='Обновить смайл', action_id=f'update_smile_{smile["id"]}')]).to_dict()) if smile["user_id"] == event_data['event']['user'] else None,
                home_form['blocks'].append(DividerBlock().to_dict())
            ]
            for smile in list_smiles
        ]
    bot.views_publish(user_id=event_data['event']['user'], view=home_form)
