from znatoks import authorize
import requests


class TestGetList:
    base_url = 'http://localhost:8000/znatok_helper_api/get_list'
    sheet = authorize().open('Кандидаты(версия 2)').worksheet('watched_tasks')
    sheet.clear()
    sheet.insert_rows([[row, 'C6VN5UUTD', '12453453.433527'] for row in range(1, 70)])

    def test_get_default(self):
        response = requests.get(self.base_url)
        assert (response.status_code == 200
                and response.json()['ok']
                and len(response.json()['tasks']) == 50
                and response.json()['tasks'][0][0] == '1'
                and response.json()['tasks'][-1][0] == '50'
                and response.json()['next'] == self.base_url + '?start=51&limit=50')

    def test_count_tasks_1(self):
        response = requests.get(self.base_url+'?start=10&limit=5')
        assert (response.status_code == 200
                and response.json()['ok']
                and len(response.json()['tasks']) == 5
                and response.json()['tasks'][0][0] == '10'
                and response.json()['tasks'][-1][0] == '14'
                and response.json()['next'] == self.base_url + '?start=15&limit=5')

    def test_count_tasks_2(self):
        response = requests.get(self.base_url+'?start=10&limit=100')
        assert (response.status_code == 200
                and response.json()['ok']
                and len(response.json()['tasks']) == 60
                and response.json()['tasks'][0][0] == '10'
                and response.json()['tasks'][-1][0] == '69'
                and response.json()['next'] is None)

    def test_correct_start_test(self):
        response = requests.get(self.base_url+'?start=10&limit=0')
        assert (response.status_code == 200
                and not response.json()['ok']
                and response.json()['error'] == 'incorrect parameters. "start" and "limit" must be greater than 0')

    def test_next(self):
        errors = []
        response = requests.get(self.base_url+'?start=1&limit=30')
        if not (response.status_code == 200
                and response.json()['ok']
                and len(response.json()['tasks']) == 30
                and response.json()['tasks'][0][0] == '1'
                and response.json()['tasks'][-1][0] == '30'
                and response.json()['next'] == self.base_url+'?start=31&limit=30'):
            errors.append('error in first request: count_tasks={} task0={}; task1={}; next={}'.format(len(response.json()['tasks']),
                                                                                                      response.json()['tasks'][0][0],
                                                                                                      response.json()['tasks'][-1][0],
                                                                                                      response.json()['next']))

        response = requests.get(response.json()['next'])
        if not (response.status_code == 200
                and response.json()['ok']
                and len(response.json()['tasks']) == 30
                and response.json()['tasks'][0][0] == '31'
                and response.json()['tasks'][-1][0] == '60'
                and response.json()['next'] == self.base_url+'?start=61&limit=30'):
            errors.append('error in second request: count_tasks={} task0={}; task1={}; next={}'.format(len(response.json()['tasks']),
                                                                                                      response.json()['tasks'][0][0],
                                                                                                      response.json()['tasks'][-1][0],
                                                                                                      response.json()['next']))

        response = requests.get(response.json()['next'])
        if not (response.status_code == 200
                and response.json()['ok']
                and len(response.json()['tasks']) == 9
                and response.json()['tasks'][0][0] == '61'
                and response.json()['tasks'][-1][0] == '69'
                and response.json()['next'] is None):
            errors.append('error in third request: count_tasks={} task0={}; task1={}; next={}'.format(len(response.json()['tasks']),
                                                                                                      response.json()['tasks'][0][0],
                                                                                                      response.json()['tasks'][-1][0],
                                                                                                      response.json()['next']))

        assert not errors, 'errors occurred:\n{}'.format('\n'.join(errors))
