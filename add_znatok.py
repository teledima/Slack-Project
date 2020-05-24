import argparse
import requests
from bs4 import BeautifulSoup

import gspread
from oauth2client.service_account import ServiceAccountCredentials

parser = argparse.ArgumentParser(usage='Добавить нового знатока')
# добавляем аргументы командной строки
parser.add_argument('--link', dest='link', help='Ссылка на профиль', required=True)
parser.add_argument('--nick', dest='nick', help='Ник пользователя', required=False, default=None)
parser.add_argument('--name', dest='name', help='Имя знатока', required=False, default=None)

# получаем аргументы
args = parser.parse_args()

headers = {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                         'Chrome/81.0.4044.138 Safari/537.36'}
req_text = requests.get(url=args.link, headers=headers).text
soup = BeautifulSoup(req_text, 'lxml')

# получаем все статусы
statuses = []
for status_raw in soup.find(attrs={'class': 'rank'}).find('h3').find_all('span'):
    statuses.append(status_raw.text.replace('\n', '').rstrip(' ').lower())

# получаем ник
nick = args.nick
if nick is None:
    nick = args.link.replace('https://znanija.com/profil/', '').split('-')[0]

# получаем имя пользователя
name = args.name
if name is None:
    extra_info = soup.find('ul', attrs={'class': 'extra-info'}).find_all('li')
    if len(extra_info) == 3:
        name = extra_info[0].text.replace('Имя: ', '')


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


# лист в который будем добавлять
sheet_add = definition_sheet(statuses)


def next_available_row(worksheet):
    str_list = list(filter(None, worksheet.col_values(1)))
    return len(str_list) + 1


scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('My Project 65610-89eb7ad75f48.json', scope)
client = gspread.authorize(creds)  # авторизация сервиса

spreadsheet = client.open('Кандидаты')  # получаем доступ к таблице
sheet = spreadsheet.worksheet(sheet_add)  # открываем лист
try:
    sheet.insert_row([args.link, nick, name, ','.join(statuses)], next_available_row(sheet))  # вставляем нового пользователя
    print('Success')
except RuntimeError:
    print('Error during insert')
