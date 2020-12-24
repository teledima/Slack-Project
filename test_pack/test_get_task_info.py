from brainly_pack import get_task_info


class TestGetTaskInfo:
    def test_one_answer(self):
        link = 'https://znanija.com/task/33180775'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and isinstance(task_info['question'], str)
                and isinstance(task_info['subject'], dict)
                and task_info['subject']['name'] == 'Математика'
                and task_info['subject']['channel_name'] == 'C6V5A1CF2'
                and len(task_info['answered_users']) == 1
                and task_info['answered_users'][0]['user'] == 'shushkasmol'
                and isinstance(task_info['answered_users'][0]['text'], str))

    def test_two_answers(self):
        link = 'https://znanija.com/task/30955562'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and isinstance(task_info['question'], str)
                and isinstance(task_info['subject'], dict)
                and task_info['subject']['name'] == 'Математика'
                and task_info['subject']['channel_name'] == 'C6V5A1CF2'
                and len(task_info['answered_users']) == 1
                and task_info['answered_users'][0]['user'] == 'maymr'
                and isinstance(task_info['answered_users'][0]['text'], str))

    def test_one_accepted_answer(self):
        link = 'https://znanija.com/task/9998689'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and isinstance(task_info['question'], str)
                and isinstance(task_info['subject'], dict)
                and task_info['subject']['name'] == 'Геометрия'
                and task_info['subject']['channel_name'] == 'C6V5A1CF2'
                and len(task_info['answered_users']) == 1
                and task_info['answered_users'][0]['user'] == 'teledima00'
                and isinstance(task_info['answered_users'][0]['text'], str))

    def test_two_accepted_answers(self):
        link = 'https://znanija.com/task/1092020'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and isinstance(task_info['question'], str)
                and isinstance(task_info['subject'], dict)
                and task_info['subject']['name'] == 'Алгебра'
                and task_info['subject']['channel_name'] == 'C6V5A1CF2'
                and len(task_info['answered_users']) == 2
                and set([answer['user'] for answer in task_info['answered_users']]).issubset(['axatar', 'rumanezzo'])
                and isinstance(task_info['answered_users'][0]['text'], str)
                and isinstance(task_info['answered_users'][1]['text'], str))

    def test_subject_physic(self):
        link = 'https://znanija.com/task/8817161'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and isinstance(task_info['question'], str)
                and isinstance(task_info['subject'], dict)
                and task_info['subject']['name'] == 'Физика'
                and task_info['subject']['channel_name'] == 'C6VN5UUTD'
                and len(task_info['answered_users']) == 1
                and task_info['answered_users'][0]['user'] == 'DedStar'
                and isinstance(task_info['answered_users'][0]['text'], str))

    def test_subject_ukraine(self):
        link = 'https://znanija.com/task/41121320'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and isinstance(task_info['question'], str)
                and isinstance(task_info['subject'], dict)
                and task_info['subject']['name'] == 'Українська мова'
                and task_info['subject']['channel_name'] == 'C8C51TY0M'
                and len(task_info['answered_users']) == 2
                and set([answer['user'] for answer in task_info['answered_users']]).issubset(['polusoidp1l3a7', 'pavlechko82ozvquy'])
                and isinstance(task_info['answered_users'][0]['text'], str)
                and isinstance(task_info['answered_users'][1]['text'], str))

    def test_subject_kazakh(self):
        link = 'https://znanija.com/task/41072818'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and isinstance(task_info['question'], str)
                and isinstance(task_info['subject'], dict)
                and task_info['subject']['name'] == 'Қазақ тiлi'
                and task_info['subject']['channel_name'] == 'C7D6KFY1X'
                and len(task_info['answered_users']) == 1
                and task_info['answered_users'][0]['user'] == 'damettie'
                and isinstance(task_info['answered_users'][0]['text'], str))

    def test_subject_other_subject(self):
        link = 'https://znanija.com/task/23105760'
        task_info = get_task_info(link)
        assert (task_info['ok'] is True
                and task_info['link'] == link
                and isinstance(task_info['question'], str)
                and isinstance(task_info['subject'], dict)
                and task_info['subject']['name'] == 'Музыка'
                and task_info['subject']['channel_name'] == 'C2ACTAVQ8'
                and len(task_info['answered_users']) == 1
                and task_info['answered_users'][0]['user'] == 'MrsVaderr'
                and isinstance(task_info['answered_users'][0]['text'], str))

    def test_deleted_task(self):
        link = 'https://znanija.com/task/6644554'
        task_info = get_task_info(link)
        assert (task_info['ok'] is False
                and task_info['link'] == link)
