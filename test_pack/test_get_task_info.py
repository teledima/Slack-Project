from brainly_pack import get_task_info


class TestGetTaskInfo:
    def test_without_answers(self):
        link = 'https://znanija.com/task/27919768'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and task_info['subject'] == 'Обществознание'
                and task_info['answered_users'] == [])

    def test_one_answer(self):
        link = 'https://znanija.com/task/33180775'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and task_info['subject'] == 'Математика'
                and len(task_info['answered_users']) == 1
                and task_info['answered_users'][0]['user'] == 'shushkasmol'
                and isinstance(task_info['answered_users'][0]['text'], str))

    def test_two_answers(self):
        link = 'https://znanija.com/task/30955562'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and task_info['subject'] == 'Математика'
                and len(task_info['answered_users']) == 2
                and set([answer['user'] for answer in task_info['answered_users']]).issubset(['maymr', 'Участник Знаний'])
                and isinstance(task_info['answered_users'][0]['text'], str)
                and isinstance(task_info['answered_users'][1]['text'], str))

    def test_one_accepted_answer(self):
        link = 'https://znanija.com/task/9998689'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and task_info['subject'] == 'Геометрия'
                and len(task_info['answered_users']) == 1
                and task_info['answered_users'][0]['user'] == 'teledima00'
                and isinstance(task_info['answered_users'][0]['text'], str))

    def test_two_accepted_answers(self):
        link = 'https://znanija.com/task/1092020'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and task_info['subject'] == 'Алгебра'
                and len(task_info['answered_users']) == 2
                and set([answer['user'] for answer in task_info['answered_users']]).issubset(['axatar', 'rumanezzo'])
                and isinstance(task_info['answered_users'][0]['text'], str)
                and isinstance(task_info['answered_users'][1]['text'], str))

    def test_deleted_task(self):
        link = 'https://znanija.com/task/6644554'
        task_info = get_task_info(link)
        assert (task_info['ok'] is False
                and task_info['link'] == link)