from brainly_core import BrainlyTask, Subject, RequestError
import cfscrape


class TestGetTaskInfo:
    def test_one_answer(self):
        link = 'https://znanija.com/task/33180775'
        task_info = BrainlyTask.get_info(link, cfscrape.create_scraper())
        assert (task_info is not None
                and task_info.link == link
                and isinstance(task_info.question, str)
                and task_info.subject is not None
                and task_info.subject == Subject(subject_id=29, name='Математика', channel_name='C6V5A1CF2')
                and len(task_info.answered_users) == 1
                and task_info.answered_users[0].name == 'shushkasmol'
                and isinstance(task_info.answered_users[0].content, str))

    def test_one_accepted_answer_english(self):
        link = 'https://znanija.com/task/12092457'
        task_info = BrainlyTask.get_info(link, cfscrape.create_scraper())
        assert (task_info is not None
                and task_info.link == link
                and isinstance(task_info.question, str)
                and task_info.subject is not None
                and task_info.subject == Subject(subject_id=33, name='Английский язык', channel_name='C6Z5Y47CG')
                and len(task_info.answered_users) == 1
                and task_info.answered_users[0].name == 'Decoration'
                and isinstance(task_info.answered_users[0].content, str))

    def test_one_accepted_answer(self):
        link = 'https://znanija.com/task/9998689'
        task_info = BrainlyTask.get_info(link, cfscrape.create_scraper())
        assert (task_info is not None
                and task_info.link == link
                and isinstance(task_info.question, str)
                and task_info.subject is not None
                and task_info.subject == Subject(subject_id=31, name='Геометрия', channel_name='C6V5A1CF2')
                and task_info.subject.name == 'Геометрия'
                and task_info.subject.channel_name == 'C6V5A1CF2'
                and len(task_info.answered_users) == 1
                and task_info.answered_users[0].name == 'teledima00'
                and isinstance(task_info.answered_users[0].content, str))

    def test_two_accepted_answers(self):
        link = 'https://znanija.com/task/1092020'
        task_info = BrainlyTask.get_info(link, cfscrape.create_scraper())
        assert (task_info is not None
                and task_info.link == link
                and isinstance(task_info.question, str)
                and task_info.subject is not None
                and task_info.subject == Subject(subject_id=30, name='Алгебра', channel_name='C6V5A1CF2')
                and len(task_info.answered_users) == 2
                and set([answer.name for answer in task_info.answered_users]).issubset(['axatar', 'rumanezzo'])
                and isinstance(task_info.answered_users[0].content, str)
                and isinstance(task_info.answered_users[1].content, str))

    def test_subject_physic(self):
        link = 'https://znanija.com/task/8817161'
        task_info = BrainlyTask.get_info(link, cfscrape.create_scraper())
        assert (task_info is not None
                and task_info.link == link
                and isinstance(task_info.question, str)
                and task_info.subject == Subject(subject_id=9, name='Физика', channel_name='C6VN5UUTD')
                and len(task_info.answered_users) == 1
                and task_info.answered_users[0].name == 'DedStar'
                and isinstance(task_info.answered_users[0].content, str))

    def test_subject_ukraine(self):
        link = 'https://znanija.com/task/41121320'
        task_info = BrainlyTask.get_info(link, cfscrape.create_scraper())
        assert (task_info is not None
                and task_info.link == link
                and isinstance(task_info.question, str)
                and task_info.subject is not None
                and task_info.subject == Subject(subject_id=37, name='Українська мова', channel_name='C8C51TY0M')
                and len(task_info.answered_users) == 2
                and set([answer.name
                         for answer in task_info.answered_users]).issubset(['polusoidp1l3a7', 'pavlechko82ozvquy'])
                and isinstance(task_info.answered_users[0].content, str)
                and isinstance(task_info.answered_users[1].content, str))

    def test_subject_kazakh(self):
        link = 'https://znanija.com/task/41072818'
        task_info = BrainlyTask.get_info(link, cfscrape.create_scraper())
        assert (task_info is not None
                and task_info.link == link
                and isinstance(task_info.question, str)
                and task_info.subject is not None
                and task_info.subject == Subject(subject_id=44, name='Қазақ тiлi', channel_name='C7D6KFY1X')
                and len(task_info.answered_users) == 1
                and task_info.answered_users[0].name == 'damettie'
                and isinstance(task_info.answered_users[0].content, str))

    def test_subject_other_subject(self):
        link = 'https://znanija.com/task/23105760'
        task_info = BrainlyTask.get_info(link, cfscrape.create_scraper())
        assert (task_info is not None
                and task_info.link == link
                and isinstance(task_info.question, str)
                and task_info.subject is not None
                and task_info.subject == Subject(subject_id=48, name='Музыка', channel_name='C2ACTAVQ8')
                and len(task_info.answered_users) == 1
                and task_info.answered_users[0].name == 'MrsVaderr'
                and isinstance(task_info.answered_users[0].content, str))

    def test_deleted_task(self):
        link = 'https://znanija.com/task/6644554'
        try:
            BrainlyTask.get_info(link, cfscrape.create_scraper())
        except RequestError as e:
            assert (e.code == 10)
