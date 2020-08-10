import json

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


def find_user_spreadsheet(url):
    tables_list = ['кандидаты', 'команда знатоков']
    return [find_in_table(table, url) for table in tables_list]


def find_in_table(table, url):
    try:
        worksheet = spreadsheet.worksheet(table)
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