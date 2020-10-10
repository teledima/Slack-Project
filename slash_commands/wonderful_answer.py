import re
from concurrent.futures.thread import ThreadPoolExecutor

import slack.errors as slack_errors
from slack import WebClient
from flask import Blueprint, request, make_response

import znatoks
import constants
from functions_slack import check_empty, reply, ephemeral_message, is_admin
from tasks import async_task

wonderful_answer_blueprint = Blueprint('wonderful_answer', __name__)


@wonderful_answer_blueprint.route('/wonderful_answer', methods=['POST', 'GET'])
def wonderful_answer():
    req = request.form
    client = WebClient(token=constants.SLACK_OAUTH_TOKEN)
    if check_empty(req):
        return make_response('', 200)
    wonderful_answer_background(client, req)
    return reply('Привет! Подождите секунду, бот заносит ссылку/ссылки в таблицу')


@async_task
def wonderful_answer_background(client, req):
    urls = set([url.strip('<>') for url in re.findall(r'https:\/\/znanija\.com\/task\/\w+', req['text'])])
    *_, last_word = req['text'].split()
    reg_ex_slack_nickname = re.search(r'(^<@\w+\|\w+>$|^\w+$)', last_word)
    who_add_ans = None if reg_ex_slack_nickname is None else reg_ex_slack_nickname.group()

    try:
        user_ex_com_info = client.users_info(user=req['user_id'])
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
                user_add_ans_info = client.users_info(user=reg_ex_user_id.search(who_add_ans).group().split('|')[0])
                username_add_ans = user_add_ans_info['user']['profile']['display_name'].lower().strip()
                user_add_ans_full_name = user_add_ans_info['user']['profile']['real_name'].lower().strip()
            except slack_errors.SlackApiError:
                pass

    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(work_with_url,
                     [client]*len(urls),
                     urls,
                     [user_ex_com_info]*len(urls),
                     [username_add_ans]*len(urls),
                     [user_add_ans_full_name]*len(urls),
                     [req['response_url']]*len(urls))


def work_with_url(client, url, user_ex_com_info, user_add_ans_display_name, user_add_ans_full_name, response_url):
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
        # get cell with user that added this answer
        user_ex_cell = wonderful_answer_table.cell(user.row, user.col + 3)
        # convert cell value to list
        list_user = user_ex_cell.value.split(',')

        if user_ex_com_name not in list_user or is_admin(client, user_ex_com_info['user']['id']):
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