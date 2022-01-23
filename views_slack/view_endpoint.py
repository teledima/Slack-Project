from flask import Blueprint, request, make_response, jsonify

import slack_sdk.errors as slack_errors
from slack_sdk.web import WebClient
from slack_sdk.models.blocks import *
from slack_sdk.models.attachments import Attachment

from datetime import datetime
from firebase_admin import firestore

import cfscrape
import sqlite3
import pytz
import json
import re

from slack_core import constants, get_view, is_admin
from slack_core.sheets import authorize
from slack_core.tasks import async_task
from brainly_core import BrainlyTask, BlockedError, RequestError
from znatok_helper_api.watch import start_watch

views_endpoint_blueprint = Blueprint('views_endpoint', __name__)
authed_users_collection = firestore.client().collection('authed_users')
smiles_collection = firestore.client().collection('smiles')


@views_endpoint_blueprint.route('/views-endpoint', methods=["POST"])
def entry_point():
    payload = json.loads(request.form['payload'])
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    if payload['type'] == 'shortcut':
        try:
            if payload['callback_id'] == 'send_check_form':
                doc = authed_users_collection.document(payload['user']['id']).get()
                if doc.exists:
                    view = get_view('files/check_form_initial.json')
                    view['private_metadata'] = json.dumps(dict(token=doc.to_dict()['user']['access_token']))
                    client.views_open(trigger_id=payload['trigger_id'], view=view)
                else:
                    client.chat_postMessage(text=f'Вы не авторизовались в приложении, пройдите по ссылке '
                                                 f'{request.url_root}auth, '
                                                 f'чтобы авторизоваться, и попробуйте снова',
                                            channel=payload['user']['id'],
                                            unfurl_links=False)
            return make_response('', 200)
        except slack_errors.SlackApiError as e:
            code = e.response["error"]
            return make_response(f"Failed to open a modal due to {code}", 200)
    elif payload['type'] == 'block_actions':
        if payload['view']['callback_id'] == 'valid_form':
            value = payload['actions'][0]['selected_option']['value']
            client.views_update(view=get_view(f'files/form_add_{value}.json'), view_id=payload['view']['id'])
        elif payload['view']['callback_id'] == 'send_check_form':
            # проверить введёную ссылку
            link = [action['value'] for action in payload['actions']
                    if action['block_id'] == 'link_id' and action['action_id'] == 'input_link_action_id']
            cleared_link = None
            if link:
                cleared_link = re.match(r'https?:/{2,}znanija\.com/+task/+\d+', link[0]).group()
            if cleared_link:
                # получить информацию о задаче
                try:
                    task_info = BrainlyTask.get_info(cleared_link, cfscrape.create_scraper())
                except (BlockedError, RequestError):
                    # установить по умолчанию
                    task_info = BrainlyTask(link=cleared_link)

                view = construct_view(task_info)
                view['private_metadata'] = json.dumps(
                    dict(token=json.loads(payload['view']['private_metadata'])['token'])
                )
                # обновить форму
                client.views_update(view=view, view_id=payload['view']['id'])
        elif payload['actions'][0]['action_id'] == 'change_smile_action':
            smile_raw = payload['view']['state']['values']['input_smile_block']['input_smile_action']['value'] or ''

            result = change_smile(smile_raw=smile_raw, username=payload['user']['username'], user_id=payload['user']['id'])
            reconstruct_home(payload['view']['blocks'], payload['user']['id'], result, payload['view']['hash'])
        elif payload['actions'][0]['action_id'].endswith('delete_action'):
            smile_id = payload['actions'][0]['value']
            result = delete_smile(smile_id)
            reconstruct_home(payload['view']['blocks'], payload['user']['id'], result, payload['view']['hash'])
        elif payload['actions'][0]['action_id'] == 'user_select_action':
            user_id = payload['actions'][0]['selected_user']
            result = find_smile_info(user_id)
            reconstruct_home(payload['view']['blocks'], payload['user']['id'], result, payload['view']['hash'])

    elif payload['type'] == 'view_submission':
        if payload['view']['callback_id'] == 'send_check_form':
            message_payload = get_message_payload(client, payload)
            client = WebClient(token=message_payload['token'])
            response = client.chat_postMessage(
                channel=message_payload['channel_name'],
                text=message_payload['verdict'],
                as_user=True,
                attachments=[Attachment(text=message_payload['question'],
                                        title=message_payload['title'],
                                        title_link=message_payload['link'],
                                        fallback=message_payload['title']
                                        ).to_dict()]
            )
            form_check_submit(message_payload['user'], message_payload['link'], response['channel'], response['ts'])
    return make_response('', 200)


def change_smile(smile_raw, username, user_id):
    try:
        smile_id = list(filter(lambda item: item != '', smile_raw.split(':'))).pop()
    except IndexError:
        return {'type': 'error', 'text': ':warning: Смайл не введён или введён в некорректном формате'}

    if re.search(r'[^a-z0-9-_]', smile_id):
        return {'type': 'error', 'text': ':warning: Название должны состоять из латинских строчных букв, цифр и не могут содержать пробелы, точки и большинство знаков препинания.'}

    # get document by entered smiled_id
    doc_ref = smiles_collection.document(smile_raw)

    # check that smile is available
    if not doc_ref.get().exists:
        # find old smile for user
        old_smile = smiles_collection.where('user_id', '==', user_id).get()
        if old_smile:
            # delete document by old smile
            old_smile[0].reference.delete()

        data = {'expert_name': username, 'user_id': user_id}

        # create new document
        doc_ref.set(data)
        return {'type': 'update' if old_smile else 'add', 'smile': {'id': smile_raw, 'user_id': user_id}}
    elif doc_ref.get().get('user_id') != user_id:
        return {'type': 'error', 'text': f':warning: <@{doc_ref.get().get("user_id")}> уже занял этот смайл'}
    else:
        return {}


def delete_smile(smile_id):
    doc_ref = smiles_collection.document(smile_id)
    user_id = doc_ref.get().get('user_id')
    doc_ref.delete()
    return {'type': 'delete', 'smile': {'id': smile_id, 'user_id': user_id}}


def find_smile_info(user_id):
    search_result = smiles_collection.where('user_id', '==', user_id).get()
    if search_result:
        smile_info = search_result[0]
        return {'type': 'info', 'smile': {'id': smile_info.id, 'user_id': user_id}}
    else:
        return {'type': 'info', 'smile': None}


@async_task
def form_check_submit(user, link, channel, ts):
    spreadsheet_client = authorize()
    spreadsheet = spreadsheet_client.open('Кандидаты(версия 2)')
    # insert new check
    spreadsheet.worksheet('test_list').append_row(
        [datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S'), 'проверка', user, link]
    )
    # start watch
    start_watch(link, channel, ts)


def construct_view(task_info: BrainlyTask):
    conn = sqlite3.connect(database='files/subjects.db')
    cur = conn.cursor()
    list_options = [Option(text=TextObject(text=subject_name, type='plain_text'), value=str(subject_id))
                    for subject_id, subject_name
                    in cur.execute('select id, name from subjects_mapping where name is not null').fetchall()]
    initial_option = Option(text=TextObject(type='plain_text', text=task_info.subject.name),
                            value=str(task_info.subject.subject_id)) if task_info and task_info.subject else None

    initial_channel = (task_info.subject.channel_name
                       if task_info and task_info.subject
                       else cur.execute('select channel_name from subjects_mapping where name is null').fetchone()[0])

    # получить исходную форму
    view = get_view('files/check_form_initial.json')
    view['submit'] = PlainTextObject(text='Отправить проверку').to_dict()
    if task_info.question is not None:
        view['blocks'].append(SectionBlock(text=task_info.question, block_id='question_id').to_dict())
        view['blocks'].append(DividerBlock().to_dict())
    if task_info.answered_users:
        # вставить ответы в форму
        for i in range(0, len(task_info.answered_users)):
            view['blocks'].append(SectionBlock(text=f'_*Ответ {task_info.answered_users[i].username}*_').to_dict())
            view['blocks'].append(SectionBlock(text=PlainTextObject(text=task_info.answered_users[i].content),
                                               block_id=f'answer_{i}_id').to_dict())

    # блок для вердикта
    verdict_element = PlainTextInputElement(action_id='verdict_id',
                                            placeholder=PlainTextObject(text='Полное верное решение, '
                                                                             'копия или есть ошибки?'),
                                            multiline=True)
    view['blocks'].append(InputBlock(label=PlainTextObject(text='Введите ваш вердикт'),
                                     element=verdict_element,
                                     optional=True,
                                     block_id='verdict_input_id').to_dict())

    # выбор канала, в который отправится проверка
    view['blocks'].append(SectionBlock(text='Проверка отправится в',
                                       block_id='channel_block_id',
                                       accessory=ChannelSelectElement(
                                           placeholder='Выберите канал',
                                           action_id='channel_selected_id',
                                           initial_channel=initial_channel)).to_dict())

    # выбор предмета
    select_subject_block = StaticSelectElement(action_id='select_subject_action_id',
                                               placeholder=PlainTextObject(text='Выберите предмет'),
                                               options=list_options,
                                               initial_option=initial_option)

    view['blocks'].append(SectionBlock(block_id='select_subject_block_id',
                                       accessory=select_subject_block,
                                       text='Выберите предмет').to_dict())

    return view


def get_message_payload(client: WebClient, payload):
    user_info = client.users_info(user=payload['user']['id'])
    user = str()
    if user_info['user']['profile']['display_name']:
        user = user_info['user']['profile']['display_name']
    elif user_info['user']['profile']['real_name']:
        user = user_info['user']['profile']['real_name']
    link = payload['view']['state']['values']['link_id']['input_link_action_id']['value']
    verdict = payload['view']['state']['values']['verdict_input_id']['verdict_id']['value']
    question = [block for block in payload['view']['blocks'] if block['block_id'] == 'question_id']
    if question:
        question = question[0]['text']['text']
    else:
        question = None
    channel_name = payload['view']['state']['values']['channel_block_id']['channel_selected_id']['selected_channel']
    private_metadata = json.loads(payload['view']['private_metadata'])

    cute_link = re.sub(r"http.*://", '', link)
    subject = payload['view']['state']['values']['select_subject_block_id']['select_subject_action_id']['selected_option']
    if subject:
        subject = subject['text']['text']
        title = f':four_leaf_clover: {cute_link}, {subject}'
    else:
        title = f':four_leaf_clover: {cute_link}'
    return dict(token=private_metadata['token'], channel_name=channel_name,
                user=user, verdict=verdict, link=link, title=title, question=question)


@async_task
def reconstruct_home(view_blocks, user_id, result, hash):
    bot = WebClient(constants.SLACK_OAUTH_TOKEN_BOT)
    initial_view = get_view('files/app_home_initial.json')
    for i, block in enumerate(view_blocks):
        if block['block_id'] == 'input_smile_block' and result.get('type') == 'error':
            view_blocks.insert(i+1, SectionBlock(block_id='error_block',
                                                 text=PlainTextObject(text=result['text'])).to_dict())
        elif result.get('type') in ('update', 'delete'):
            if block['block_id'] == f'{result["smile"]["user_id"]}_block':
                if result['type'] == 'update':
                    block['text']['text'] = f':{result["smile"]["id"]}: этот у <@{result["smile"]["user_id"]}>'
                elif result['type'] == 'delete':
                    view_blocks.remove(block)

        if result.get('type') == 'info':
            if block['block_id'] == 'description_block':
                if result["smile"]:
                    block['text']['text'] = f'Смайл <@{result["smile"]["user_id"]}> :{result["smile"]["id"]}:'
                else:
                    block['text']['text'] = 'Смайл не выбран'
            elif block['block_id'] == 'actions_block':
                if result["smile"]:
                    block['elements'][0].pop('style')
                    block['elements'][0]['text']['text'] = 'Обновить смайл'
                else:
                    block['elements'][0]['style'] = 'primary'
                    block['elements'][0]['text']['text'] = 'Добавить смайл'

    if result.get('type') == 'add':
        view_blocks.append(SectionBlock(
            block_id=f'{result["smile"]["user_id"]}_block',
            text=MarkdownTextObject(text=f':{result["smile"]["id"]}: этот у <@{result["smile"]["user_id"]}>'),
            accessory=ButtonElement(
                action_id=f'{result["smile"]["id"]}_delete_action',
                text='Удалить смайл',
                value=result["smile"]["id"],
                confirm=ConfirmObject(title='Удаление смайлика',
                                      text=MarkdownTextObject(text=f'Вы действительно хотите удалить смайл <@{result["smile"]["user_id"]}>?'),
                                      confirm='Да', deny='Отмена')
            ) if is_admin(result["smile"]["user_id"]) else None
        ).to_dict())

    initial_view['blocks'] = view_blocks

    bot.views_publish(user_id=user_id, view=initial_view, hash=hash)
