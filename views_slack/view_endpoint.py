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

from slack_core import constants, get_view, is_admin, get_username
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
        elif payload['actions'][0]['action_id'].endswith('delete_action'):
            smile_id = payload['actions'][0]['value']
            delete_smile(smile_id)
            delete_smile_from_modal(payload['view'], smile_id)
        elif payload['actions'][0]['action_id'] == 'user_select_action':
            user_id = payload['actions'][0]['selected_user']
            update_view4update_smile(payload['view'], find_smile_info(user_id)['smile'])
        elif payload['actions'][0]['action_id'] == 'open_all_smiles_action':
            open_all_smiles(payload['trigger_id'], is_admin(payload['user']['id']))
        elif payload['actions'][0]['action_id'] == 'open_update_smile_view_action':
            open_update_smile_view(payload['trigger_id'], payload['user']['id'], is_admin(payload['user']['id']),)

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
        elif payload['view']['callback_id'] == 'update_smile_callback':
            smile_raw = payload['view']['state']['values']['input_smile_block']['input_smile_action']['value']

            if is_admin(payload['user']['id']):
                user_id = payload['view']['state']['values']['user_select_block']['user_select_action']['selected_user']
            else:
                user_id = None

            user_id = user_id or payload['user']['id']

            error_response = change_smile(smile_raw=smile_raw, username=get_username(user_id), user_id=user_id)

            if error_response['errors']:
                return jsonify(error_response), 200
            else:
                return jsonify(response_action='clear'), 200
    return make_response('', 200)


def change_smile(smile_raw, username, user_id):
    error_response = dict(response_action='errors', errors=dict())
    try:
        smile_id = list(filter(lambda item: item != '', smile_raw.split(':'))).pop()
        if re.search(r'[^a-z0-9-_]', smile_id):
            error_response['errors']['input_smile_block'] = 'Название должно состоять из латинских строчных букв, цифр и не могут содержать пробелы, точки и большинство знаков препинания'
            return error_response
    except IndexError:
        error_response['errors']['input_smile_block'] = 'Смайлик введён в некорректном формате'
        return error_response
    # get document by entered smiled_id
    doc_ref = smiles_collection.document(smile_id)

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
    elif doc_ref.get().get('user_id') != user_id:
        error_response['errors']['input_smile_block'] = f'{doc_ref.get().get("expert_name")} уже занял этот смайлик'

    return error_response


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
        return {'type': 'info', 'smile': {'id': None, 'user_id': user_id}}


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
def open_all_smiles(trigger_id, admin):
    bot = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    all_smiles_view = get_view('files/all_smiles_modal.json')
    list_smiles = [dict(id=doc.id, user_id=doc.get('user_id')) for doc in smiles_collection.limit(90).get()]
    _ = [
            all_smiles_view['blocks'].append(
                SectionBlock(
                    block_id=f'{smile["id"]}_block',
                    text=MarkdownTextObject(text=f':{smile["id"]}: этот у <@{smile["user_id"]}>'),
                    accessory=ButtonElement(
                        action_id=f'{smile["id"]}_delete_action',
                        text='Удалить смайлик',
                        value=smile["id"],
                        confirm=ConfirmObject(title='Удаление смайлика',
                                              text=MarkdownTextObject(text=f'Вы действительно хотите удалить смайлик <@{smile["user_id"]}>?'),
                                              confirm='Да', deny='Отмена')
                    ) if admin else None
                ).to_dict()
            )
            for smile in list_smiles
        ]
    bot.views_open(trigger_id=trigger_id, view=all_smiles_view)


@async_task
def delete_smile_from_modal(view, smile_id):
    bot = WebClient(constants.SLACK_OAUTH_TOKEN_BOT)
    all_smiles_view = get_view('files/all_smiles_modal.json')
    for i, block in enumerate(view['blocks']):
        view['blocks'].remove(block) if block['block_id'] == f'{smile_id}_block' else None
    all_smiles_view['blocks'] = view['blocks']
    bot.views_update(view=all_smiles_view, view_id=view['id'], hash=view['hash'])


@async_task
def open_update_smile_view(trigger_id, current_user_id, admin):
    bot = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    update_smile_view = get_view('files/update_smile_modal.json')

    search_result = smiles_collection.where('user_id', '==', current_user_id).get()
    current_smile = {'id': search_result[0].id, 'user_id': search_result[0].get('user_id')} if search_result else None

    if admin:
        update_smile_view['blocks'].append(
            ActionsBlock(
                block_id='user_select_block',
                elements=[UserSelectElement(placeholder='Выберите пользователя',action_id='user_select_action')]
            ).to_dict()
        )

    if not current_smile:
        description_text = 'У вас ещё нет смайлика. Добавьте его, чтобы отмечать свои ответы.'
        button_text = 'Добавить смайлик'
    elif current_smile:
        description_text = f'Ваш смайлик :{current_smile["id"]}:'
        button_text = 'Обновить смайлик'

    update_smile_view['submit']['text'] = button_text
    update_smile_view['blocks'].append(
        SectionBlock(block_id='description_block', text=MarkdownTextObject(text=description_text)).to_dict())

    update_smile_view['blocks'].append(
        InputBlock(
            block_id='input_smile_block',
            element=PlainTextInputElement(action_id='input_smile_action', placeholder='Введите смайлик'),
            label='Смайлик'
        ).to_dict()
    )
    bot.views_open(trigger_id=trigger_id, view=update_smile_view)


@async_task
def update_view4update_smile(view, smile_info):
    bot = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    update_smile_view = get_view('files/update_smile_modal.json')

    update_smile_view['submit']['text'] = 'Обновить' if smile_info['id'] else 'Добавить'
    for i, block in enumerate(view['blocks']):
        if block['block_id'] == 'description_block':
            if smile_info["id"]:
                block['text']['text'] = f'Смайлик <@{smile_info["user_id"]}> :{smile_info["id"]}:'
            else:
                block['text']['text'] = 'Смайлик не выбран'

    update_smile_view['blocks'] = view['blocks']
    bot.views_update(view=update_smile_view, view_id=view['id'], hash=view['hash'])
