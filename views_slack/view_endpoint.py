import pytz

from slack_core.tasks import async_task
from flask import Blueprint, request, make_response
from slack_sdk.web import WebClient
import slack_sdk.errors as slack_errors
from slack_core import constants
from slack_sdk.models.blocks import SectionBlock, InputBlock, InputInteractiveElement
from slack_sdk.models.views import PlainTextObject
from datetime import datetime
import json
import re
from brainly_pack import get_task_info
from znatoks import authorize


views_endpoint_blueprint = Blueprint('views_endpoint', __name__)


@views_endpoint_blueprint.route('/views-endpoint', methods=["POST"])
def entry_point():
    payload = json.loads(request.form['payload'])
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN)
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
                # получить ответы
                answers = get_task_info(link)
                # проверить, даны ли ответы
                if answers:
                    # получить исходную форму
                    view = get_view('files/check_form_initial.json')
                    # вставить ответы в форму
                    for i in range(0, len(answers)):
                        view['blocks'].append(SectionBlock(text=answers[i], block_id=f'answer_{i}_id', type='plain_text').to_dict())
                    view['blocks'].append(InputBlock(label=PlainTextObject(text='Введите ваш вердикт'),
                                                     element=InputInteractiveElement(type='plain_text_input',
                                                                                     action_id='verdict_id',
                                                                                     placeholder=PlainTextObject(text='Полное верное решение, копия или есть ошибки'),
                                                                                     multiline=True),
                                                     optional=True,
                                                     block_id='verdict_input_id').to_dict())
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
            form_check_submit(payload)
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
def form_check_submit(payload):
    user = payload['user']['username']
    link = payload['view']['state']['values']['link_id']['input_link_action_id']['value']
    print(user, link)
    client_spreadsheet = authorize()
    sheet = client_spreadsheet.open('Кандидаты(версия 2)').worksheet('test_list')
    sheet.append_row([datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S'), 'проверка', user, link])


def get_view(filename):
    with open(filename, 'r', encoding='utf-8') as form_file:
        return json.load(form_file)
