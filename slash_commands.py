import constants
import requests
import json
import znatoks
import re
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, make_response, jsonify
from slack.web.classes import blocks
from slack.web.client import WebClient
import slack.errors as slack_errors
from tasks import async_task

app = Flask(__name__)


def ephemeral_message(response_url, text=None, blocks=None):
    requests.post(response_url, data=json.dumps({'content_type': 'ephemeral', 'text': text, 'blocks': blocks}))


def reply(text: str):
    return jsonify(
        content_type='ephemeral',
        text=text
    )


def is_admin(client, req):
    user_info_resp = client.users_info(user=req['user_id'])
    if user_info_resp['user']['is_admin'] or user_info_resp['user']['id'] in constants.WHITE_LIST:
        return True
    else:
        return False


def check_empty(req):
    if not req['text']:
        ephemeral_message(req['response_url'], "Запрос пустой")
        return True
    return False


@app.route('/')
def hello():
    return "Hello, Slack App!"


@app.route('/get_info', methods=['POST'])
def get_info():
    req = request.form
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN)
    if not is_admin(client, req):
        return reply("You don't have permission")
    check_empty(req)
    get_info_background(request.form)
    return reply('Got it!')


@async_task
def get_info_background(req):
    info = znatoks.find_user_spreadsheet(req['text'])
    if all(i is None for i in info):
        ephemeral_message(req['response_url'], 'User is not found')
        return
    sections = []
    for row in info:
        if row is not None:
            for key in row.keys():
                sections.append(
                    blocks.SectionBlock(text=blocks.TextObject(f'_*{key}*_: {row[key]}', 'mrkdwn')).to_dict())
            sections.append(blocks.DividerBlock().to_dict())
    ephemeral_message(req['response_url'], blocks=sections)


@app.route('/wonderful_answer', methods=['POST', 'GET'])
def wonderful_answer():
    req = request.form
    if check_empty(req):
        return make_response('', 200)
    wonderful_answer_background(req)
    return reply('Привет! Подождите секунду, бот заносит ссылку/ссылки в таблицу')


@async_task
def wonderful_answer_background(req):
    urls = set([url.strip('<>') for url in re.findall(r'https:\/\/znanija\.com\/task\/\w+', req['text'])])
    *_, last_word = req['text'].split()
    reg_ex_slack_nickname = re.search(r'(^<@\w+\|\w+>$|^\w+$)', last_word)
    who_add_ans = None if reg_ex_slack_nickname is None else reg_ex_slack_nickname.group()

    try:
        user_ex_com_info = get_info_user(req['user_id'])
        if not user_ex_com_info['user']['profile']['display_name']:
            ephemeral_message(req['response_url'], f'В вашем профиле не установлен display name.\n'
                                                   f'Чтобы его установить вам надо <https://prnt.sc/u2t1a6|в этом поле> '
                                                   f'указать свой ник в znanija.com\n'
                                                   f'Более подробно о том, как установить display name, вы можете узнать в этой '
                                                   f'статье: <https://slack.com/intl/en-ru/help/articles/216360827-Change-your-display-name|Change your display name>')
            return
    except slack_errors.SlackApiError as e:
        ephemeral_message(req['response_url'], f'Ошибка при запросе к Slack API: {e.response}')
        return

    username_add_ans = None
    user_add_ans_full_name = None
    if who_add_ans:
        # find user name added answer
        reg_ex_user_id = re.compile(r'\w+\|\w+')
        if reg_ex_user_id.search(who_add_ans) is None:
            # param just nickname
            username_add_ans = who_add_ans.lower().strip()
        else:
            # param is slack nickname (@nickname)
            try:
                user_add_ans_info = get_info_user(
                    reg_ex_user_id.search(who_add_ans).group().split('|')[0]
                )
                username_add_ans = user_add_ans_info['user']['profile']['display_name'].lower().strip()
                user_add_ans_full_name = user_add_ans_info['user']['profile']['real_name'].lower().strip()
            except slack_errors.SlackApiError:
                pass

    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(work_with_url,
                     urls,
                     [user_ex_com_info]*len(urls),
                     [username_add_ans]*len(urls),
                     [user_add_ans_full_name]*len(urls),
                     [req['response_url']]*len(urls))


def work_with_url(url, user_ex_com_info, user_add_ans_display_name, user_add_ans_full_name, response_url):
    user_ex_com_name = user_ex_com_info['user']['profile']['display_name'].lower().strip()
    result = znatoks.is_correct_request(url, user_ex_com_name, user_add_ans_display_name, user_add_ans_full_name)
    if not result['ok']:
        if result['cause'] == 'same_user':
            ephemeral_message(response_url, f'{url} - Вы не можете отправлять свои ответы')
            return
        elif result['cause'] == 'blocked_error':
            ephemeral_message(response_url, f'{url} - Извините, произошла ошибка при проверке ответа. Попробуйте позже')
            return
        elif result['cause'] == 'answer_user_not_found':
            ephemeral_message(response_url, f'{url} - Ответ пользователя {user_add_ans_display_name} не найден')
            return
    wonderful_answer_table = znatoks.authorize().open('wonderful_answer_test').worksheet('wonderful_answer')

    # find users answered on a question and filter
    user_filter_cells = list(filter(lambda x: x.value == result['user'],
                                    [wonderful_answer_table.cell(cell.row, cell.col + 1)
                                     for cell in wonderful_answer_table.findall(url, in_column=1)]))
    # update 'count' column
    for user in user_filter_cells:
        # get 'count' cell
        count_cell = wonderful_answer_table.cell(user.row, user.col + 2)
        # get cell with user that added this answer
        user_ex_cell = wonderful_answer_table.cell(user.row, user.col + 3)
        # convert cell value to list
        list_user = user_ex_cell.value.split(',')

        if user_ex_com_name not in list_user or\
                user_ex_com_info['user']['is_admin'] or user_ex_com_info['user']['id'] in constants.WHITE_LIST:
            wonderful_answer_table.update_cell(count_cell.row, count_cell.col, int(count_cell.value) + 1)
            if user_ex_com_name not in list_user:
                list_user.append(user_ex_com_name)
                wonderful_answer_table.update_cell(user_ex_cell.row, user_ex_cell.col, ','.join(list_user))
        else:
            ephemeral_message(response_url, f'{url} - Вы не можете два раза добавить один и тот же ответ.')
            return

    # url with user doesn't exist in the table yet
    if not user_filter_cells:
        # столбцы таблицы: ссылка, кто дал ответ, предмет, сколько раз ответ выбрали, кто выбрал
        wonderful_answer_table.append_row([url, result['user'], result['subject'], 1, user_ex_com_name])
    ephemeral_message(response_url, f'{url} - Ответ пользователя {result["user"]} добавлен!')


@app.route('/entry_point', methods=["POST"])
def entry_point():
    payload = json.loads(request.form['payload'])
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN)
    if payload['type'] == 'shortcut':
        try:
            client.views_open(trigger_id=payload['trigger_id'], view=get_view('files/validate_form.json'))
            return make_response('', 200)
        except slack_errors.SlackApiError as e:
            code = e.response["error"]
            return make_response(f"Failed to open a modal due to {code}", 200)
    elif payload['type'] == 'block_actions':
        if payload['view']['callback_id'] == 'valid_form':
            value = payload['actions'][0]['selected_option']['value']
            client.views_update(view=get_view(f'files/form_add_{value}.json'), view_id=payload['view']['id'])
    elif payload['type'] == 'view_submission':
        if payload['view']['callback_id'] == 'expert_form':
            form_expert_submit(client, payload)
        elif payload['view']['callback_id'] == 'candidate_form':
            form_candidate_submit(client, payload)
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


def get_view(filename):
    with open(filename, 'r', encoding='utf-8') as form_file:
        return json.load(form_file)


def get_info_user(user_id):
    try:
        info = WebClient(token=constants.SLACK_OAUTH_TOKEN).users_info(user=user_id).data
        if info['ok']:
            return info
    except slack_errors.SlackApiError as e:
        raise e
