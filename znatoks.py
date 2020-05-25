import requests
import requests.exceptions as http_errors
from bs4 import BeautifulSoup

import gspread
import gspread.exceptions as errors_sheet
from oauth2client.service_account import ServiceAccountCredentials

def definition_sheet(statuses_arg):
    if len(statuses_arg) == 0:
        return None
    else:
        if 'модератор' in statuses_arg or 'старший модератор' in statuses_arg or 'ведущий модератор' in statuses_arg:
            return 'Модераторы'
        elif 'архивариус' in statuses_arg or 'старший архивариус' in statuses_arg:
            return 'Архивариусы'
        else:
            return 'Знатоки'

def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))
    return len(str_list) + 1

class Znatok:
    headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/81.0.4044.138 Safari/537.36'}

    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name('My Project 65610-89eb7ad75f48.json',
                                                             ['https://spreadsheets.google.com/feeds',
                                                              'https://www.googleapis.com/auth/drive']))
    spreadsheet = client.open('Кандидаты')

    def __init__(self, url, nick=None, name=None):
        self.url = url
        try:
            self.soup = BeautifulSoup(requests.get(url=self.url, headers=self.headers).text, 'lxml')
        except http_errors.ConnectionError:
            print("Invalid URL")
        self.nick = nick if nick is not None else url.replace('https://znanija.com/profil/', '').split('-')[0]
        if name is None:
            extra_info = self.soup.find('ul', attrs={'class': 'extra-info'}).find_all('li')
            if len(extra_info) == 3:
                self.name = extra_info[0].text.replace('Имя: ', '')
        self.statuses = [status_raw.text.replace('\n', '').rstrip(' ').lower() for status_raw in
                         self.soup.find(attrs={'class': 'rank'}).find('h3').find_all('span')]
        self.sheet = Znatok.spreadsheet.worksheet(definition_sheet(self.statuses))

    def add_znatok(self):
        self.sheet.insert_row([self.url, self.nick, self.name, ','.join(self.statuses)],
                              next_available_row(self.sheet))  # вставляем нового пользователя

    def delete_znatok(self):
        try:
            self.sheet.delete_row(index=self.sheet.find(self.url, in_column=0).row)
            print('Success')
        except errors_sheet.CellNotFound:
            print('User is not found')

