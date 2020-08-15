import requests
import json
import re
import gspread
import gspread.exceptions as errors_sheet
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup
from slack import WebClient
import slack.errors as slack_errors

import constants


class SameUserError(Exception):
    pass


class BlockedError(Exception):
    pass


def authorize():
    return gspread.authorize(ServiceAccountCredentials.
                             from_json_keyfile_name('files/slash-commands-archive-a7072e2bbb96.json',
                                                    ['https://spreadsheets.google.com/feeds',
                                                     'https://www.googleapis.com/auth/drive']
                                                    )
                             )


def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))
    return len(str_list) + 1


def find_user_spreadsheet(url):
    client = authorize()
    spreadsheet = client.open('Copy of Кандидаты')
    tables_list = ['кандидаты', 'команда знатоков']
    return [find_in_table(spreadsheet.worksheet(table), url) for table in tables_list]


def find_in_table(worksheet, url):
    try:
        headers_table = []
        for header in worksheet.row_values(1):
            if not header:
                break
            headers_table.append(header.lower())
        values = worksheet.row_values(worksheet.find(url).row)
        values = values + [''] * (len(headers_table) - len(values))
        return dict(zip(headers_table + ['таблица'], values + [worksheet.title]))
    except errors_sheet.CellNotFound:
        pass


def get_display_name(user_id):
    try:
        info = WebClient(token=constants.SLACK_OAUTH_TOKEN).users_info(user=user_id).data
        if info['ok']:
            return info['user']['profile']['display_name']
    except slack_errors.SlackApiError as e:
        raise e


def is_expert(nick_name):
    # TODO necessary to split the table 'магистры/архивариусы' on 3 table: 'архивариусы', 'магистры', 'модераторы'
    return True


def check_answer(list_authors, user_add_ans_name, user_ex_com_name):
    for nick_name in list_authors:
        # /wonderful_answer url @nick
        if user_add_ans_name is not None:
            if nick_name == user_add_ans_name:
                return {'ok': True}
        else:  # should check user in expert team and user is not I
            if len(list_authors) == 1:
                if nick_name == user_ex_com_name:
                    return {'ok': False, 'cause': 'same_user'}
                elif is_expert(nick_name):
                    return {'ok': True}
    return {'ok': False, 'cause': 'answer_user_not_found'}


def is_correct_request(url, user_ex_com_id, who_add_ans=None):
    # get info about user executed the command
    try:
        user_ex_com_name = get_display_name(user_ex_com_id).lower().strip()
    except slack_errors.SlackApiError as e:
        return {'ok': False, 'cause': 'slack_api_error', 'description': e.response['error']}

    if who_add_ans is None:
        user_add_ans_name = None
    else:
        # find user name added answer
        reg_ex = re.compile(r'\w+\|\w+')
        if reg_ex.search(who_add_ans) is None:
            # param just nickname
            user_add_ans_name = who_add_ans
        else:
            # param is slack nickname (@nickname)
            try:
                user_add_ans_name = get_display_name(reg_ex.search(who_add_ans).group().split('|')[0]).lower().strip()
            except slack_errors.SlackApiError:
                user_add_ans_name = None

    soup = BeautifulSoup(requests.get(url=url, headers=json.load(open('files/headers.json', 'r'))).text, 'lxml')
    if soup.find('title').text != 'You have been blocked':
        try:
            # Here possible AttributeError exception
            list_authors = [author_description_tag.find('div').find('span').text.lower().strip()
                            for author_description_tag
                            in soup.find_all('div', attrs={'class': 'brn-qpage-next-answer-box-author__description'})]
            return check_answer(list_authors, user_add_ans_name, user_ex_com_name)
        except AttributeError:
            list_authors = [author_description_tag.find_all('div')[1].text
                            for author_description_tag
                            in soup.find_all('div', attrs={'class': 'brn-kodiak-answer__user'})]
            return check_answer(list_authors, user_add_ans_name, user_ex_com_name)
    else:
        return {'ok': False, 'cause': 'blocked_error'}
