from flask import Blueprint, request, make_response
from slack_sdk.web import WebClient
import slack_sdk.errors as slack_errors
from slack_sdk.models.blocks import *
from slack_sdk.models.views import PlainTextObject
from slack_sdk.models.attachments import Attachment
from datetime import datetime
from firebase_admin import firestore
import pytz
import json
import re

from slack_core import constants
from slack_core.tasks import async_task
from brainly_core import BrainlyTask, RequestError, BlockedError
from znatoks import authorize


views_endpoint_blueprint = Blueprint('views_endpoint', __name__)
authed_users_collection = firestore.client().collection('authed_users')


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
                    view['private_metadata'] = doc.to_dict()['user']['access_token']
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
            link = payload['actions'][0]['value']
            if re.search(r'https:/{2,}znanija\.com/+task/+\d+', link):
                # получить информацию о задаче
                task_info = BrainlyTask.get_info(link)
                view = construct_view(task_info)
                view['private_metadata'] = json.dumps(dict(token=payload['view']['private_metadata'],
                                                           subject=task_info.subject.name))
                # обновить форму
                client.views_update(view=view, view_id=payload['view']['id'])
        return make_response('', 200)
    elif payload['type'] == 'view_submission':
        if payload['view']['callback_id'] == 'send_check_form':
            message_payload = get_message_payload(payload)
            client = WebClient(token=message_payload['token'])
            client.chat_postMessage(channel=message_payload['channel_name'],
                                    text=message_payload['verdict'],
                                    as_user=True,
                                    attachments=[Attachment(text=message_payload['question'],
                                                            title=message_payload['title'],
                                                            title_link=message_payload['link'],
                                                            fallback=message_payload['title']).to_dict()])
            form_check_submit(message_payload['user'], message_payload['link'])
        return make_response('', 200)
    return make_response('', 404)


@async_task
def form_check_submit(user, link):
    spreadsheet_client = authorize()
    sheet = spreadsheet_client.open('Кандидаты(версия 2)').worksheet('test_list')
    sheet.append_row([datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S'), 'проверка',
                      user, link])


def construct_view(task_info: BrainlyTask):
    # получить исходную форму
    view = get_view('files/check_form_initial.json')
    view['submit'] = PlainTextObject(text='Отправить проверку').to_dict()
    view['blocks'].append(SectionBlock(text=task_info.question, block_id='question_id').to_dict())
    view['blocks'].append(DividerBlock().to_dict())
    # вставить ответы в форму
    for i in range(0, len(task_info.answered_users)):
        view['blocks'].append(SectionBlock(text=f'_*Ответ {task_info.answered_users[i].username}*_').to_dict())
        view['blocks'].append(SectionBlock(text=PlainTextObject(text=task_info.answered_users[i].content),
                                           block_id=f'answer_{i}_id',
                                           type='plain_text').to_dict())

    verdict_element = InputInteractiveElement(type='plain_text_input',
                                              action_id='verdict_id',
                                              placeholder=PlainTextObject(text='Полное верное решение, '
                                                                               'копия или есть ошибки?'),
                                              multiline=True)
    view['blocks'].append(InputBlock(label=PlainTextObject(text='Введите ваш вердикт'),
                                     element=verdict_element,
                                     optional=True,
                                     block_id='verdict_input_id').to_dict())
    view['blocks'].append(SectionBlock(text='Проверка отправится в',
                                       block_id='channel_block_id',
                                       accessory=ChannelSelectElement(initial_channel=task_info.subject.channel_name,
                                                                      placeholder='Выберите канал',
                                                                      action_id='channel_selected_id')).to_dict())
    return view


def get_message_payload(payload):
    user = payload['user']['username']
    link = payload['view']['state']['values']['link_id']['input_link_action_id']['value']
    verdict = payload['view']['state']['values']['verdict_input_id']['verdict_id']['value']
    question = list(filter(lambda block: block['block_id'] == 'question_id',
                           payload['view']['blocks']))[0]['text']['text']
    channel_name = payload['view']['state']['values']['channel_block_id']['channel_selected_id']['selected_channel']
    private_metadata = json.loads(payload['view']['private_metadata'])

    cute_link = re.sub(r"http.*://", '', link)
    title = f':star: {cute_link}, {private_metadata["subject"]}'
    return dict(token=private_metadata['token'], channel_name=channel_name,
                user=user, verdict=verdict, link=link, title=title, question=question)


def get_view(filename):
    with open(filename, 'r', encoding='utf-8') as form_file:
        return json.load(form_file)
