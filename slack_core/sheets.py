import gspread
from oauth2client.service_account import ServiceAccountCredentials


def authorize():
    return gspread.authorize(
        ServiceAccountCredentials.from_json_keyfile_name(
            'files/slash-commands-archive-6bd3a93cc8eb.json',
            ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        )
    )
