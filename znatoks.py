import json
from scrapy.selector import Selector
import requests
import requests.exceptions as http_errors
from bs4 import BeautifulSoup

import gspread
import gspread.exceptions as errors_sheet
from oauth2client.service_account import ServiceAccountCredentials

client = gspread.authorize(ServiceAccountCredentials.
                           from_json_keyfile_name('slash-command-archive-cdd8145bac45.json',
                                                  ['https://spreadsheets.google.com/feeds',
                                                   'https://www.googleapis.com/auth/drive']
                                                  )
                           )
spreadsheet = client.open('Кандидаты')

cookie = json.load(open('cookies.json'))


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
        self.values = {'url': url, 'nick': None, 'name': None, 'statuses': None, 'tutor': None}
        for key in kwargs.keys():
            self.values[key] = kwargs['key']

        text_page = requests.get(url=url, cookies=cookie).text
        selector = Selector(text=text_page)
        if self.values['nick'] is None:
            self.values['nick'] = selector.xpath('//span[@class="ranking"]/h2/a/text()').get()

        if self.values['name'] is None:
            extra_info = selector.xpath('//ul[@class="extra-info"]/li/text()').getall()
            if len(extra_info) == 3:
                self.values['name'] = extra_info[0].text.replace(': ', '')

        # find statuses
        statuses = {status_raw.replace('\n', '').rstrip(' ').lower() for status_raw in
                    selector.xpath('//span[@style]/text()').getall()}
        self.values['statuses'] = ','.join(statuses)
        # if user have status define sheet
        if statuses is not None:
            try:
                self.sheet = spreadsheet.worksheet(definition_sheet(statuses))
            except errors_sheet.WorksheetNotFound:
                pass
        self.values['tutor'] = selector.xpath('//div[@id="profile-mod-panel"]/ul/a/text()').get()

    def add_user_into_team(self):
        try:
            self.sheet.find(self.values['url'], in_column=0)
            print('Такой пользователь уже существует ({})'.format(self.values['nick']))
        except errors_sheet.CellNotFound:
            # вставляем нового пользователя
            self.sheet.insert_row(list(self.values.values()), next_available_row(self.sheet))
            print('Пользователь {} добавлен'.format(self.values['nick']))
        except AttributeError:
            pass

    def delete_user_from_team(self):
        try:
            self.sheet.delete_row(index=self.sheet.find(self.values['url'], in_column=0).row)
            print('Пользователь успешно удалён')
        except errors_sheet.CellNotFound:
            print('Пользователь не найден')
        except AttributeError:
            pass

    def update_info_about_member_of_team(self, **kwargs):
        row = self.sheet.find(self.values['url'], in_column=0).row
        values = self.sheet.get_all_records()[row - 2]
        values.update(kwargs)
        range_update = self.sheet.range(row, 1, row, self.sheet.col_count)
        for cell in range_update:
            cell.value = list(values.values())[cell.col - 1]
        self.sheet.update_cells(cell_list=range_update)
        if values['statuses'] != self.values['statuses']:
            User.move_to(self, definition_sheet(set(values['statuses'].split(','))), row)
        self.values = values
        print('Информация обновлена')

    def move_to(self, new_sheet, row):
        values = self.sheet.get_all_values()[row - 1]
        self.sheet.delete_row(row)
        self.sheet = spreadsheet.worksheet(new_sheet)
        self.sheet.insert_row(values, next_available_row(self.sheet))


def init_spreadsheet():
    url = 'https://znanija.com/moderators/mod_list/page:{}'
    for moderator_url in walk_page(url.format(4)):
        User(moderator_url).add_user_into_team()


def walk_page(url):
    soup = BeautifulSoup(requests.get(url, cookies=cookie).text, 'lxml')
    table = soup.find('table', attrs={'class': 'usersTable'})
    list_mod_on_page = []
    for row in table.find_all('tr'):
        for cell in row.find_all('td'):
            list_mod_on_page.append('https://znanija.com'+cell.find('a').attrs['href'])
    return list_mod_on_page