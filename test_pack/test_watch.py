from znatoks import authorize
import requests
from gspread import CellNotFound


class TestWatch:
    sheet = authorize().open('Кандидаты(версия 2)').worksheet('watched_tasks')
    link_id = 'https://znanija.com/task/45116478'
    channel_id = 'C6VN5UUTD'
    ts = '12453453.433524'

    def test_start_watch(self, ):
        errors = []
        self.sheet.clear()
        response = requests.post('http://localhost:8000/znatok_helper_api/watch',
                                 json=dict(link_id=self.link_id,
                                           channel_id=self.channel_id,
                                           ts=self.ts,
                                           activity='start'))
        if not (response.status_code == 200 and response.json()['ok']):
            errors.append(response.json()['error'])
        try:
            cell = self.sheet.find(self.link_id, in_column=1)
            if not (cell.row == 1 and cell.col == 1 and cell.value == self.link_id):
                errors.append('incorrect position')
        except CellNotFound:
            errors.append('cell not found')
        assert not errors, 'errors occurred:\n{}'.format('\n'.join(errors))

    def test_end_watch(self):
        errors = []
        response = requests.post('http://localhost:8000/znatok_helper_api/watch',
                                 json=dict(link_id=self.link_id, activity='end'))
        if not (response.status_code == 200 and response.json()['ok'] and response.json()['deleted_rows'] == 1):
            errors.append(response.json()['error'])
        try:
            self.sheet.find(self.link_id, in_column=1)
            errors.append('link remains')
        except CellNotFound:
            pass
        assert not errors, 'errors occurred:\n{}'.format('\n'.join(errors))

    def test_end_watch_noexist_task(self):
        response = requests.post('http://localhost:8000/znatok_helper_api/watch',
                                 json=dict(link_id=self.link_id, activity='end'))
        assert response.status_code == 200 and response.json()['ok'] and response.json()['deleted_rows'] == 0

    def test_incorrect_type(self):
        response = requests.post('http://localhost:8000/znatok_helper_api/watch',
                                 json=dict(link_id=self.link_id, activity='endd'))
        assert (response.status_code == 200
                and not response.json()['ok']
                and response.json()['error'] == 'no such activity')

    def test_start_watch_exist_task(self):
        self.sheet.clear()
        requests.post('http://localhost:8000/znatok_helper_api/watch',
                      json=dict(link_id=self.link_id,
                                channel_id=self.channel_id,
                                ts=self.ts,
                                activity='start'))
        requests.post('http://localhost:8000/znatok_helper_api/watch',
                      json=dict(link_id=self.link_id,
                                channel_id=self.channel_id,
                                ts=self.ts,
                                activity='start'))
        cells_tasks = self.sheet.findall(self.link_id, in_column=1)
        assert (len(cells_tasks) > 0
                and cells_tasks[0].row == 1 and cells_tasks[1].row == 2
                and cells_tasks[1].col == 1 and cells_tasks[1].col == 1
                and cells_tasks[0].value == self.link_id and cells_tasks[1].value == self.link_id)

    def test_end_watch_duplicated_task(self):
        requests.post('http://localhost:8000/znatok_helper_api/watch',
                      json=dict(link_id='https://znanija.com/task/451164',
                                channel_id=self.channel_id,
                                ts=self.ts,
                                activity='start'))
        response = requests.post('http://localhost:8000/znatok_helper_api/watch',
                                 json=dict(link_id=self.link_id,
                                           channel_id=self.channel_id,
                                           ts=self.ts,
                                           activity='end'))
        cells_tasks = self.sheet.findall(self.link_id, in_column=1)
        assert len(cells_tasks) == 0 and response.json()['deleted_rows'] == 2