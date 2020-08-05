import json
import requests
from bs4 import BeautifulSoup
from scrapy.selector import Selector

import gspread
import gspread.exceptions as errors_sheet
from oauth2client.service_account import ServiceAccountCredentials

client = gspread.authorize(ServiceAccountCredentials.
                           from_json_keyfile_name('files/slash-commands-archive-a7072e2bbb96.json',
                                                  ['https://spreadsheets.google.com/feeds',
                                                   'https://www.googleapis.com/auth/drive']
                                                  )
                           )
spreadsheet = client.open('Copy of Кандидаты')

cookie = json.load(open('files/cookies.json'))
headers = json.load(open('files/headers_after_login.json'))


def definition_sheet(statuses_arg):
    if statuses_arg:
        if statuses_arg & {'модератор', 'старший модератор', 'ведущий модератор'}:
            if statuses_arg & {'знаток'}:
                return 'Модераторы'
            else:
                return None
        elif statuses_arg & {'архивариус', 'старший архивариус', 'главный архивариус-знаток'}:
            return 'Архивариусы'
        elif statuses_arg & {'знаток', 'старший знаток', 'премьер-знаток'}:
            return 'Знатоки'
        else:
            return None
    else:
        return None


def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))
    return len(str_list) + 1


class User:
    def __init__(self, url, **kwargs):
        # default initialize
        self.sheet = None
        self.parameters = {'nick': None, 'url': url, 'name': None, 'tutor': None,
                           'statuses': None, 'happy_birthday_date': None}
        for key in kwargs.keys():
            self.parameters[key] = kwargs[key]

        get_user_page = requests.get(url=url, cookies=cookie, headers=headers) if None in self.parameters.values() else None
        # if we can get the user page then we can extract info about user
        if get_user_page is not None and get_user_page.status_code == 200:
            selector = Selector(text=get_user_page.text)
            if self.parameters['nick'] is None:
                self.parameters['nick'] = selector.xpath('//span[@class="ranking"]/h2/a/text()').get()

            if self.parameters['name'] is None:
                extra_info = selector.xpath('//ul[@class="extra-info"]/li/text()').getall()
                if len(extra_info) == 3:
                    self.parameters['name'] = extra_info[0]

            if self.parameters['statuses'] is None:
                # find statuses
                statuses = {status_raw.replace('\n', '').rstrip(' ').lower() for status_raw in
                            selector.xpath('//span[@style]/text()').getall()}
                if statuses is not None:
                    self.parameters['statuses'] = ','.join(statuses)
                else:
                    self.parameters['statuses'] = None

                # if user have status define sheet
                if statuses is not None:
                    try:
                        self.sheet = spreadsheet.worksheet(definition_sheet(statuses))
                    except errors_sheet.WorksheetNotFound:
                        pass

            if self.parameters['tutor'] is None:
                self.parameters['tutor'] = selector.xpath('//div[@id="profile-mod-panel"]/ul/a/text()').get()

    def add_user_into_team(self):
        try:
            self.sheet.find(self.parameters['url'], in_column=0)
            return False
        except errors_sheet.CellNotFound:
            # add new user
            self.sheet.insert_row(list(self.parameters.values()), next_available_row(self.sheet))
            return True
        except AttributeError:
            return False

    def delete_user_from_team(self):
        try:
            self.sheet.delete_row(index=self.sheet.find(self.parameters['url'], in_column=0).row)
            print('Пользователь успешно удалён')
        except errors_sheet.CellNotFound:
            print('Пользователь не найден')
        except AttributeError:
            pass

    def update_info_about_member_of_team(self, **kwargs):
        row = self.sheet.find(self.parameters['url'], in_column=0).row
        values = self.sheet.get_all_records()[row - 2]
        values.update(kwargs)
        range_update = self.sheet.range(row, 1, row, self.sheet.col_count)
        for cell in range_update:
            cell.value = list(values.values())[cell.col - 1]
        self.sheet.update_cells(cell_list=range_update)
        if values['statuses'] != self.parameters['statuses']:
            User.move_to(self, definition_sheet(set(values['statuses'].split(','))), row)
        self.parameters = values
        print('Информация обновлена')

    def move_to(self, new_sheet, row):
        values = self.sheet.get_all_values()[row - 1]
        self.sheet.delete_row(row)
        self.sheet = spreadsheet.worksheet(new_sheet)
        self.sheet.insert_row(values, next_available_row(self.sheet))


def find_user_slack(nick):
    with open('files/data_search.json', 'r') as search_file:
        data = json.load(search_file)
        data['data[User][nick]'] = nick
        req = requests.post('https://znanija.com/users/search',
                            data=data,
                            cookies=cookie,
                            headers=headers)

        if req.status_code == 200:
            soap = BeautifulSoup(req.text, 'lxml')
            try:
                path = soap.find('a', attrs={'class': 'nick'}).attrs['href']
                return User('https://znanija.com' + path)
            except AttributeError:
                return None
        else:
            return False


def find_user_spreadsheet(url):
    tables_list = ['кандидаты', 'команда знатоков']
    return [find_in_table(table, url) for table in tables_list]


def find_in_table(table, url):
    try:
        worksheet = spreadsheet.worksheet(table)
        headers_table = [header.lower() for header in worksheet.row_values(1)]
        values = worksheet.row_values(worksheet.find(url).row)
        values = values + [''] * (len(headers_table) - len(values))
        return dict(zip(headers_table + ['таблица'], values + [worksheet.title]))
    except errors_sheet.CellNotFound:
        pass