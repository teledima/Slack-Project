import requests
import json
import gspread
import gspread.exceptions as errors_sheet
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup


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


def get_text(url_page):
    return requests.get(url=url_page, headers=json.load(open('files/headers.json', 'r'))).text


def is_expert(nick_name):
    # TODO necessary to split the table 'магистры/архивариусы' on 3 table: 'архивариусы', 'магистры', 'модераторы'
    return True


def check_answer(list_authors, user_ex_com_name, user_add_ans_name, user_add_ans_full_name):
    for nick_name in list_authors:
        # /wonderful_answer url @nick
        if user_add_ans_name is not None or user_add_ans_full_name is not None:
            # check equals whether display name (or nickname without @) or full name with the nickname in znanija.com
            if user_add_ans_name == user_ex_com_name or user_add_ans_full_name == user_ex_com_name:
                return {'ok': False, 'cause': 'same_user'}
            if nick_name == user_add_ans_name or nick_name == user_add_ans_full_name:
                if is_expert(nick_name):
                    return {'ok': True, 'user': nick_name}
        if len(list_authors) == 1:
            if nick_name == user_ex_com_name:
                return {'ok': False, 'cause': 'same_user'}
            if user_add_ans_name is None and user_add_ans_full_name is None and is_expert(nick_name):
                return {'ok': True, 'user': nick_name}
    return {'ok': False, 'cause': 'answer_user_not_found'}


def is_correct_request(url, user_ex_com_name, user_add_ans_name=None, user_add_ans_full_name=None):
    with open('files/headers.json', 'r') as headers_file:
        text = requests.get(url=url, headers=json.load(headers_file)).text
        soup = BeautifulSoup(text, 'lxml')
    if soup.find('title').text != 'You have been blocked':
        list_authors = [author_description_tag.find('div').find('span').text.lower().strip()
                        for author_description_tag
                        in soup.find_all('div', attrs={'class': 'brn-qpage-next-answer-box-author__description'})]
        if not list_authors:
            list_authors = [author_description_tag.find_all('div')[1].text.lower().strip()
                            for author_description_tag
                            in soup.find_all('div', attrs={'class': 'brn-kodiak-answer__user'})]
        print(list_authors, user_ex_com_name, user_add_ans_name, user_add_ans_full_name)
        res = check_answer(list_authors, user_ex_com_name, user_add_ans_name, user_add_ans_full_name)
        if res['ok']:
            res['subject'] = soup.find('div', attrs={'class': 'brn-qpage-next-question-box-header__description'}).\
                find('ul').find('a').text.lower().strip()
        print(res)
        return res
    else:
        return {'ok': False, 'cause': 'blocked_error'}

