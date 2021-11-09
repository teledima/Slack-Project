import gspread
from gspread import Cell
from gspread.utils import absolute_range_name, fill_gaps
from oauth2client.service_account import ServiceAccountCredentials


def authorize():
    return gspread.authorize(ServiceAccountCredentials.
                             from_json_keyfile_name('files/slash-commands-archive-6bd3a93cc8eb.json',
                                                    ['https://spreadsheets.google.com/feeds',
                                                     'https://www.googleapis.com/auth/drive']
                                                    )
                             )


def find_rows(sheet, row_values):
    temp_row_values = []
    data = sheet.spreadsheet.values_get(absolute_range_name(sheet.title))

    try:
        values = fill_gaps(data['values'])
        temp_row_values = fill_gaps([row_values], cols=max(len(row) for row in values)).pop()
    except KeyError:
        values = []

    array_cells = get_array_cells(values)

    return [
     row for _, row in enumerate(array_cells)
     if all([
             True if cell.value == temp_row_values[j] or temp_row_values[j] == '' else False
             for j, cell in enumerate(row)
            ])
     ]


def get_array_cells(values):
    return [[Cell(row=i+1, col=j+1, value=cell_value) for j, cell_value in enumerate(row)] for i, row in enumerate(values)]
