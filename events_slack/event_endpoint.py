import json

from flask import Blueprint

from slack_sdk.web import WebClient
from slack_sdk.models.blocks import *
from slack_core import constants, get_view, is_admin
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
                                        latest=str(float(ts)+1),
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
    admin = is_admin(event_data['event']['user'])

    bot = WebClient(constants.SLACK_OAUTH_TOKEN_BOT)
    home_form = get_view('files/app_home_initial.json')

    list_smiles = [dict(id=doc.id, user_id=doc.get().get('user_id')) for doc in smiles_collection.list_documents()]
    current_user_smail = list(filter(lambda smile: smile['user_id'] == event_data['event']['user'], list_smiles))

    if admin:
        home_form['blocks'].append(
            SectionBlock(block_id='user_select_block',
                         text='Выберите пользователя',
                         accessory=UserSelectElement(placeholder='Пользователь...',
                                                     action_id='user_select_action')).to_dict()
        )

    if not current_user_smail:
        description_text = 'У вас ещё нет смайла. Добавьте его, чтобы отмечать свои ответы.'
        button_text = 'Добавить смайл'
    elif current_user_smail:
        description_text = f'Ваш смайл :{current_user_smail[0]["id"]}:'
        button_text = 'Обновить смайл'

    home_form['blocks'].append(SectionBlock(block_id='description_block', text=MarkdownTextObject(text=description_text)).to_dict())

    home_form['blocks'].append(
        InputBlock(
            block_id='input_smile_block',
            element=PlainTextInputElement(action_id='input_smile_action', placeholder='Введите смайлик'),
            label='Смайлик'
        ).to_dict()
    )

    home_form['blocks'].append(ActionsBlock(block_id='actions_block',
                                            elements=[ButtonElement(action_id='change_smile_action',
                                                                    text=button_text,
                                                                    style=None if current_user_smail else 'primary')]).to_dict())

    home_form['blocks'].append(HeaderBlock(block_id='smile_list_header_block', text='Список смайликов').to_dict())
    home_form['blocks'].append(DividerBlock(block_id='divide_header_list_block').to_dict())

    _ = [
            [
                home_form['blocks'].append(
                    SectionBlock(
                        block_id=f'{smile["user_id"]}_block',
                        text=MarkdownTextObject(text=f':{smile["id"]}: этот у <@{smile["user_id"]}>'),
                        accessory=ButtonElement(
                            action_id=f'{smile["id"]}_delete_action',
                            text='Удалить смайл',
                            value=smile["id"],
                            confirm=ConfirmObject(title='Удаление смайлика',
                                                  text=MarkdownTextObject(text=f'Вы действительно хотите удалить смайл <@{smile["user_id"]}>?'),
                                                  confirm='Да', deny='Отмена')
                        ) if admin else None
                    ).to_dict()
                )
            ]
            for smile in list_smiles
        ]
    bot.views_publish(user_id=event_data['event']['user'], view=home_form)
