import cfscrape
import sqlite3
import pytz
import json
import re
import slack_sdk.errors as slack_errors
from slack_sdk.web import WebClient
from slack_sdk.models.blocks import *
from slack_sdk.models.attachments import Attachment
from datetime import datetime
from flask import request
from firebase_admin import firestore

from slack_core import constants, utils
from slack_core.sheets import authorize
from slack_core.tasks import async_task
from brainly_core import BrainlyTask, BlockedError, RequestError


authed_users_collection = firestore.client().collection('authed_users')


def open_check_form(payload):
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    try:
        if payload['callback_id'] == 'check_form_callback':
            doc = authed_users_collection.document(payload['user']['id']).get()
            if doc.exists:
                view = utils.get_view('files/check_form_initial.json')
                view['private_metadata'] = json.dumps(dict(token=doc.to_dict()['user']['access_token']))
                client.views_open(trigger_id=payload['trigger_id'], view=view)
            else:
                client.chat_postMessage(text=f'Вы не авторизовались в приложении, пройдите по ссылке '
                                             f'{request.url_root}auth, '
                                             f'чтобы авторизоваться, и попробуйте снова',
                                        channel=payload['user']['id'],
                                        unfurl_links=False)
    except slack_errors.SlackApiError:
        pass


def input_link(payload):
    @async_task
    def update_view():
        conn = sqlite3.connect(database='files/subjects.db')
        cur = conn.cursor()

        list_options = [
            Option(text=TextObject(text=subject_name, type='plain_text'), value=str(subject_id))
            for subject_id, subject_name
            in cur.execute('select id, name from subjects_mapping where name is not null').fetchall()
        ]

        initial_option = Option(
            text=TextObject(type='plain_text', text=task_info.subject.name),
            value=str(task_info.subject.subject_id)
        ) if task_info and task_info.subject else None

        initial_channel = (
            task_info.subject.channel_name
            if task_info and task_info.subject
            else cur.execute('select channel_name from subjects_mapping where name is null').fetchone()[0]
        )

        # получить исходную форму
        view = utils.get_view('files/check_form_initial.json')
        view['submit'] = PlainTextObject(text='Отправить проверку').to_dict()
        if task_info.question is not None:
            view['blocks'].append(SectionBlock(text=task_info.question, block_id='question_block').to_dict())
            view['blocks'].append(DividerBlock().to_dict())
        if task_info.answered_users:
            # вставить ответы в форму
            for i in range(0, len(task_info.answered_users)):
                view['blocks'].append(SectionBlock(text=f'_*Ответ {task_info.answered_users[i].username}*_').to_dict())
                view['blocks'].append(SectionBlock(text=PlainTextObject(text=task_info.answered_users[i].content),
                                                   block_id=f'answer_{i}_block').to_dict())

        # блок для вердикта
        view['blocks'].append(
            InputBlock(
                label=PlainTextObject(text='Введите ваш вердикт'),
                element=PlainTextInputElement(
                    action_id='verdict_input_action',
                    placeholder=PlainTextObject(text='Полное верное решение, копия или есть ошибки?'),
                    multiline=True
                ),
                optional=True,
                block_id='verdict_input_block'
            ).to_dict()
        )

        # выбор канала, в который отправится проверка
        view['blocks'].append(
            SectionBlock(
                text='Проверка отправится в',
                block_id='channel_select_block',
                accessory=ChannelSelectElement(placeholder='Выберите канал',
                                               action_id='channel_select_action',
                                               initial_channel=initial_channel)
            ).to_dict()
        )

        # выбор предмета
        view['blocks'].append(
            SectionBlock(
                block_id='subject_select_block',
                accessory=StaticSelectElement(
                    action_id='subject_select_action',
                    placeholder=PlainTextObject(text='Выберите предмет'),
                    options=list_options,
                    initial_option=initial_option
                ),
                text='Выберите предмет'
            ).to_dict()
        )

        view['private_metadata'] = json.dumps(
            dict(token=json.loads(payload['view']['private_metadata'])['token'])
        )

        client.views_update(view=view, view_id=payload['view']['id'])

    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    link_raw = payload['actions'][0]['value']
    link = None
    if link_raw:
        link = re.match(r'https?:/{2,}znanija\.com/+task/+\d+', link_raw).group()
    if link:
        # получить информацию о задаче
        try:
            task_info = BrainlyTask.get_info(link, cfscrape.create_scraper())
        except (BlockedError, RequestError):
            # установить по умолчанию
            task_info = BrainlyTask(link=link)

        update_view()


def submit_check_form(payload, result):
    def get_message_payload():
        user_info = client.users_info(user=payload['user']['id'])
        user = str()
        if user_info['user']['profile']['display_name']:
            user = user_info['user']['profile']['display_name']
        elif user_info['user']['profile']['real_name']:
            user = user_info['user']['profile']['real_name']
        link = payload['view']['state']['values']['input_link_block']['input_link_action']['value']
        verdict = payload['view']['state']['values']['verdict_input_block']['verdict_input_action']['value']
        question = [block for block in payload['view']['blocks'] if block['block_id'] == 'question_block']
        if question:
            question = question[0]['text']['text']
        else:
            question = None
        channel_name = payload['view']['state']['values']['channel_select_block']['channel_select_action'][
            'selected_channel']
        private_metadata = json.loads(payload['view']['private_metadata'])

        cute_link = re.sub(r"http.*://", '', link)
        subject = payload['view']['state']['values']['subject_select_block']['subject_select_action'][
            'selected_option']
        if subject:
            subject = subject['text']['text']
            title = f':four_leaf_clover: {cute_link}, {subject}'
        else:
            title = f':four_leaf_clover: {cute_link}'
        return dict(token=private_metadata['token'], channel_name=channel_name,
                    user=user, verdict=verdict, link=link, title=title, question=question)

    @async_task
    def submit(user, link):
        spreadsheet_client = authorize()
        spreadsheet = spreadsheet_client.open('Кандидаты(версия 2)')
        # insert new check
        spreadsheet.worksheet('test_list').append_row(
            [datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S'), 'проверка', user, link]
        )

    client = WebClient(constants.SLACK_OAUTH_TOKEN_BOT)
    message_payload = get_message_payload()
    client = WebClient(token=message_payload['token'])
    client.chat_postMessage(
        channel=message_payload['channel_name'],
        text=message_payload['verdict'],
        as_user=True,
        attachments=[Attachment(text=message_payload['question'],
                                title=message_payload['title'],
                                title_link=message_payload['link'],
                                fallback=message_payload['title']
                                ).to_dict()]
    )
    submit(message_payload['user'], message_payload['link'])
    result['response_action'] = 'clear'
