import pytz

from slack_core.tasks import async_task
from flask import Blueprint, request, make_response
from slack_sdk.web import WebClient
import slack_sdk.errors as slack_errors
from slack_core import constants
from slack_sdk.models.blocks import SectionBlock, InputBlock, InputInteractiveElement, DividerBlock
from slack_sdk.models.views import PlainTextObject
from slack_sdk.models.attachments import Attachment
from datetime import datetime
import json
import re
from brainly_pack import get_task_info
from znatoks import authorize


views_endpoint_blueprint = Blueprint('views_endpoint', __name__)


@views_endpoint_blueprint.route('/views-endpoint', methods=["POST"])
def entry_point():
    payload = json.loads(request.form['payload'])
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    if payload['type'] == 'shortcut':
        try:
            if payload['callback_id'] == 'send_check_form':
                client.views_open(trigger_id=payload['trigger_id'], view=get_view('files/check_form_initial.json'))
            elif payload['callback_id'] == 'add_form_id':
                client.views_open(trigger_id=payload['trigger_id'], view=get_view('files/validate_form.json'))
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
            if re.search(r'https://znanija\.com/task/[0-9/]+$', link):
                # получить информацию о задаче
                task_info = get_task_info(link)
                print(task_info)
                # проверить, получилось ли запросить информацию о задаче
                if task_info['ok']:
                    # получить исходную форму
                    view = get_view('files/check_form_initial.json')
                    view['blocks'].append(SectionBlock(text=task_info['question'], block_id='question_id').to_dict())
                    view['blocks'].append(DividerBlock().to_dict())
                    # вставить ответы в форму
                    for i in range(0, len(task_info['answered_users'])):
                        view['blocks'].append(SectionBlock(text=task_info['answered_users'][i]['text'],
                                                           block_id=f'answer_{i}_id',
                                                           type='plain_text').to_dict())
                    view['blocks'].append(InputBlock(label=PlainTextObject(text='Введите ваш вердикт'),
                                                     element=InputInteractiveElement(type='plain_text_input',
                                                                                     action_id='verdict_id',
                                                                                     placeholder=PlainTextObject(text='Полное верное решение, копия или есть ошибки?'),
                                                                                     multiline=True),
                                                     optional=True,
                                                     block_id='verdict_input_id').to_dict())
                    view['private_metadata'] = json.dumps(task_info['subject'])
                    # обновить форму
                    client.views_update(view=view, view_id=payload['view']['id'])
        return make_response('', 200)
    elif payload['type'] == 'view_submission':
        json.dump(payload, open('views_slack/example_payload/submit_form.json', 'w'), indent=4)
        if payload['view']['callback_id'] == 'expert_form':
            form_expert_submit(client, payload)
        elif payload['view']['callback_id'] == 'candidate_form':
            form_candidate_submit(client, payload)
        elif payload['view']['callback_id'] == 'send_check_form':
            user = payload['user']['username']
            link = payload['view']['state']['values']['link_id']['input_link_action_id']['value']
            verdict = payload['view']['state']['values']['verdict_input_id']['verdict_id']['value']
            question = list(filter(lambda block: block['block_id'] == 'question_id', payload['view']['blocks']))[0]['text']['text']
            subject = json.loads(payload['view']['private_metadata'])

            cute_link = re.sub(r"http.*://", '', link)
            title = f':star: {cute_link}, {subject["name"]}'
            client = WebClient(token=constants.SLACK_OAUTH_TOKEN_USER)
            client.chat_postMessage(channel=subject["channel_name"],
                                    text=verdict,
                                    as_user=True,
                                    attachments=[Attachment(text=question, title=title, title_link=link, fallback=title).to_dict()])
            form_check_submit(user, link)
        return make_response('', 200)
    return make_response('', 404)


@async_task
def form_candidate_submit(client, payload):
    user_info = {'profile': None, 'nick': None, 'name': None,
                 'statuses': None, 'tutor': None, 'subject': None, 'happy_birthday': None, 'is_auto_check': False}
    pass


@async_task
def form_expert_submit(client, payload):
    pass


@async_task
def form_check_submit(user, link):
    spreadsheet_client = authorize()
    sheet = spreadsheet_client.open('Кандидаты(версия 2)').worksheet('test_list')
    sheet.append_row([datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S'), 'проверка', user, link])


def get_view(filename):
    with open(filename, 'r', encoding='utf-8') as form_file:
        return json.load(form_file)