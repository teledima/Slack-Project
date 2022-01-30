from flask import Blueprint, request

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

from slack_core import constants, get_view, is_admin, get_username, generate_random_id, SlackInteractionsAdapter
from slack_core.sheets import authorize
from slack_core.tasks import async_task
from brainly_core import BrainlyTask, BlockedError, RequestError
from znatok_helper_api.watch import start_watch

views_endpoint_blueprint = Blueprint('views_endpoint', __name__)
interactions_adapter = SlackInteractionsAdapter(router=views_endpoint_blueprint, rule='/views-endpoint')

firestore_client = firestore.client()
authed_users_collection = firestore_client.collection('authed_users')
smiles_collection = firestore_client.collection('smiles')
settings_collection = firestore_client.collection('users_settings')


@interactions_adapter.on('shortcut.check_form_callback')
def open_check_form(payload):
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    try:
        if payload['callback_id'] == 'check_form_callback':
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
    except slack_errors.SlackApiError as e:
        pass


@interactions_adapter.on('block_actions.input_link_action')
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
        view = get_view('files/check_form_initial.json')
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


@interactions_adapter.on('block_actions.open_all_smiles_action')
def open_all_smiles(payload):
    open_list_smiles_view(start=0, end=constants.ALL_SMILES_PAGE_SIZE, admin=is_admin(payload['user']['id']),
                          add_info={'trigger_id': payload['trigger_id']})


@interactions_adapter.on('block_actions.all_smiles_next_page_action')
def all_smiles_next_page(payload):
    metadata = json.loads(payload['view']['private_metadata'])
    open_list_smiles_view(start=metadata['end_at'], end=metadata['end_at'] + constants.ALL_SMILES_PAGE_SIZE,
                          admin=is_admin(payload['user']['id']),
                          update_info={'view_id': payload['view']['id'], 'hash': payload['view']['hash']})


@interactions_adapter.on('block_actions.all_smiles_prev_page_action')
def all_smiles_prev_page(payload):
    metadata = json.loads(payload['view']['private_metadata'])
    open_list_smiles_view(start=metadata['start_at'] - constants.ALL_SMILES_PAGE_SIZE, end=metadata['start_at'],
                          admin=is_admin(payload['user']['id']),
                          update_info={'view_id': payload['view']['id'], 'hash': payload['view']['hash']})


@interactions_adapter.on('block_actions.delete_smile_action')
def delete_smile(payload):
    smile_id = payload['actions'][0]['value']

    smiles_collection.document(smile_id).delete()

    metadata = json.loads(payload['view']['private_metadata'])
    open_list_smiles_view(start=metadata['start_at'], end=metadata['start_at'] + constants.ALL_SMILES_PAGE_SIZE,
                          admin=is_admin(payload['user']['id']),
                          update_info={'view_id': payload['view']['id'], 'hash': payload['view']['hash']})


@interactions_adapter.on('block_actions.open_update_smile_view_action')
def open_update_smile_view(payload):
    current_user_id = payload['user']['id']

    bot = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    update_smile_view = get_view('files/app_home/update_smile_modal.json')
    current_user_settings = settings_collection.document(current_user_id).get()

    search_result = smiles_collection.where('user_id', '==', current_user_id).get()
    current_smile = {'id': search_result[0].id, 'user_id': search_result[0].get('user_id')} if search_result else None

    if is_admin(payload['user']['id']):
        update_smile_view['blocks'].append(
            ActionsBlock(
                block_id='user_select_block',
                elements=[UserSelectElement(placeholder='Выберите пользователя', action_id='user_select_action')]
            ).to_dict()
        )

    if not current_smile:
        description_text = 'У вас ещё нет смайлика. Добавьте его, чтобы отмечать свои ответы.'
    elif current_smile:
        description_text = f'Ваш смайлик :{current_smile["id"]}:'

    update_smile_view['blocks'].append(
        SectionBlock(block_id='description_block', text=MarkdownTextObject(text=description_text)).to_dict()
    )

    update_smile_view['blocks'].append(
        InputBlock(
            block_id='input_smile_block',
            element=PlainTextInputElement(action_id='input_smile_action', placeholder='Введите смайлик'),
            label='Смайлик',
            optional=True,
        ).to_dict()
    )
    send_notification_option = Option(
        value='send_notification',
        label='Отправлять уведомления',
        description='Когда под проверкой поставят :lower_left_ballpoint_pen: тогда <@U0184CFEU56> отправит сообщение об освободившемся поле для ответа'
    )
    update_smile_view['blocks'].append(
        ActionsBlock(
            elements=[
                CheckboxesElement(
                    action_id='settings_action',
                    options=[send_notification_option],
                    initial_options=[send_notification_option if current_user_settings.exists and current_user_settings.get('send_notification') else None]
                )
            ]
        ).to_dict()
    )

    bot.views_open(trigger_id=payload['trigger_id'], view=update_smile_view)


@interactions_adapter.on('block_actions.user_select_action')
def update_smile_user_select(payload):
    def get_info(user_id):
        info = dict(type='info', smile=dict(), settings=dict())
        search_result = smiles_collection.where('user_id', '==', user_id).get()
        user_settings = settings_collection.document(user_id).get()
        if search_result:
            smile_info = search_result[0]
            info['smile'] = {'id': smile_info.id, 'user_id': user_id}
        else:
            info['smile'] = {'id': None, 'user_id': user_id}
        if user_settings.exists:
            info['settings']['send_notification'] = user_settings.get('send_notification')
        else:
            info['settings']['send_notification'] = False
        return info
    user_info = get_info(payload['actions'][0]['selected_user'])
    view = payload['view']

    bot = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    update_smile_view = get_view('files/app_home/update_smile_modal.json')

    send_notification_option = Option(
        value='send_notification',
        label='Отправлять уведомления',
        description='Когда под проверкой поставят :lower_left_ballpoint_pen: тогда <@U0184CFEU56> отправит уведомление об освободившемся поле для ответа'
    ).to_dict()

    update_smile_view['submit']['text'] = 'Обновить настройки'
    for i, block in enumerate(view['blocks']):
        if block['block_id'] == 'description_block':
            if user_info['smile']["id"]:
                block['text']['text'] = f'Смайлик <@{user_info["smile"]["user_id"]}> :{user_info["smile"]["id"]}:'
            else:
                block['text']['text'] = 'Смайлик не выбран'
        elif 'elements' in block and 'settings_action' in block['elements'][0]['action_id']:
            # to update the checkbox on the page, you need to regenerate the id
            block['block_id'] = generate_random_id()
            if user_info['settings']['send_notification']:
                block['elements'][0]['initial_options'] = [send_notification_option]
            elif block['elements'][0].get('initial_options'):
                block['elements'][0].pop('initial_options')

    update_smile_view['blocks'] = view['blocks']

    bot.views_update(view=update_smile_view, view_id=view['id'], hash=view['hash'])


@interactions_adapter.on('view_submission.check_form_callback')
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
    def submit(user, link, channel, ts):
        spreadsheet_client = authorize()
        spreadsheet = spreadsheet_client.open('Кандидаты(версия 2)')
        # insert new check
        spreadsheet.worksheet('test_list').append_row(
            [datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S'), 'проверка', user, link]
        )
        # start watch
        start_watch(link, channel, ts)

    client = WebClient(constants.SLACK_OAUTH_TOKEN_BOT)
    message_payload = get_message_payload()
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
    submit(message_payload['user'], message_payload['link'], response['channel'], response['ts'])
    result['response_action'] = 'clear'


@interactions_adapter.on('view_submission.update_smile_callback')
def submit_update_smile(payload, result):
    def update_smile():
        try:
            smile_id = list(filter(lambda item: item != '', smile_raw.split(':'))).pop()
            if re.search(r'[^a-z0-9-_]', smile_id):
                return dict(
                    input_smile_block='Название должно состоять из латинских строчных букв, цифр и не могут содержать пробелы, точки и большинство знаков препинания')
        except IndexError:
            return dict(input_smile_block='Смайлик введён в некорректном формате')
        # remove the ability to use this smile
        if smile_id == 'lower_left_ballpoint_pen':
            return dict(input_smile_block='Вы не можете выбрать этот смайлик')

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
            return dict(input_smile_block=f'{doc_ref.get().get("expert_name")} уже занял этот смайлик')
    state_values = payload['view']['state']['values']
    smile_raw = state_values['input_smile_block']['input_smile_action']['value']
    selected_options = [state_values[block]['settings_action']['selected_options']
                        for block in state_values if 'settings_action' in state_values[block]][0]

    send_notification = len(selected_options) > 0 and len(
        list(filter(lambda item: item['value'] == 'send_notification', selected_options))
    ) > 0

    if is_admin(payload['user']['id']):
        user_id = payload['view']['state']['values']['user_select_block']['user_select_action']['selected_user']
    else:
        user_id = None

    user_id = user_id or payload['user']['id']

    if smile_raw:
        username = get_username(user_id)
        change_errors = update_smile()
        if change_errors:
            result['response_action'] = 'errors'
            result['errors'] = change_errors

    if not result.get('errors'):
        settings_collection.document(user_id).set({'send_notification': send_notification}, merge=True)
        result['response_action'] = 'clear'


@async_task
def open_list_smiles_view(start, end, admin, add_info=None, update_info=None):
    assert add_info or update_info

    bot = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    all_smiles_view = get_view('files/app_home/all_smiles_modal.json')
    # querying the database for the number of elements 1 more than the page size
    smiles_page_one_extra = [doc for doc in smiles_collection.order_by(field_path='expert_name').offset(start).limit(end - start + 1).get()]

    # check if the requested number is equal to the length of the array, then 1 additional element is discarded
    if len(smiles_page_one_extra) == end - start + 1:
        smiles_page = smiles_page_one_extra[:-1]
    # otherwise there are no more elements in the database and you need to display everything
    else:
        smiles_page = smiles_page_one_extra

    list_smiles = [dict(id=doc.reference.id, user_id=doc.get('user_id')) for doc in smiles_page]
    _ = [
        all_smiles_view['blocks'].append(
            SectionBlock(
                block_id=f'{smile["id"]}_block',
                text=MarkdownTextObject(text=f':{smile["id"]}: этот у <@{smile["user_id"]}>'),
                accessory=ButtonElement(
                    action_id='delete_smile_action',
                    text='Удалить смайлик',
                    value=smile["id"],
                    confirm=ConfirmObject(title='Удаление смайлика',
                                          text=MarkdownTextObject(
                                              text=f'Вы действительно хотите удалить смайлик <@{smile["user_id"]}>?'),
                                          confirm='Да', deny='Отмена')
                ) if admin else None
            ).to_dict()
        )
        for smile in list_smiles
    ]

    navigation_block = ActionsBlock(block_id='navigation_block', elements=[])
    metadata = dict(start_at=start)

    if start != 0:
        navigation_block.elements.append(ButtonElement(action_id='all_smiles_prev_page_action', text='Предыдущая страница'))

    if len(smiles_page_one_extra) == end - start + 1:
        metadata['end_at'] = end
        navigation_block.elements.append(ButtonElement(action_id='all_smiles_next_page_action', text='Следующая страница'))

    if navigation_block.elements:
        all_smiles_view['blocks'].append(navigation_block.to_dict())
        all_smiles_view['private_metadata'] = json.dumps(metadata)

    if add_info:
        bot.views_open(trigger_id=add_info['trigger_id'], view=all_smiles_view)
    else:
        bot.views_update(view=all_smiles_view, view_id=update_info['view_id'], hash=update_info['hash'])
