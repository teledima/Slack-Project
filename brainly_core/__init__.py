from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime
import cfscrape
import sqlite3
import json
import re


class RequestError(Exception):
    """Error while executing request"""
    def __init__(self, link: str, message: str, error_code: int):
        self.code = error_code
        super().__init__(f'Server responds with: {message} and code: {error_code} for link: {link}')


class BlockedError(Exception):
    """The request was blocked"""
    def __init__(self, link: str, message: str, error_code: int):
        self.code = error_code
        super().__init__(f'Request was blocked, message: {message}, error_code: {error_code}, link: {link}')


class Subject:
    def __init__(self, subject_id: str, name: str, channel_name: str):
        self.subject_id = subject_id
        self.name = name
        self.channel_name = channel_name

    def __eq__(self, other):
        return (isinstance(other, Subject)
                and self.subject_id == other.subject_id
                and self.name == other.name
                and self.channel_name == other.channel_name)


class UserAnswer:
    def __init__(self, username: str, content: str):
        self.username = username
        self.content = content

    def __eq__(self, other):
        return isinstance(other, UserAnswer) and self.username == other.username and self.content == other.content


class UserInfo:
    def __init__(self, user_id: int, session: cfscrape.Session, nick: Optional[str] = None):
        self.user_id = user_id
        self.nick = nick
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        with sqlite3.connect('files/subjects.db') as db:
            cursor = db.execute('select id '
                                'from subjects_mapping '
                                'where channel_name != (select channel_name '
                                '                       from subjects_mapping where name is null)')
            ids = [row[0] for row in cursor.fetchall()]
        data = [dict(operationName="ProfilePage",
                     query="query ProfilePage($userId: Int!, $subjectsIds: [ID!]) {"
                           "  userById(id: $userId) {"
                           "    databaseId"
                           "    nick"
                           "    avatar {"
                           "      thumbnailUrl"
                           "    }"
                           "    rank {"
                           "      name"
                           "    }"
                           "    specialRanks {"
                           "      name"
                           "    }"
                           "    created"
                           "    answerCountBySubject(ids: $subjectsIds) {"
                           "      subject {"
                           "        name"
                           "      }"
                           "      count"
                           "    }"
                           "    answers {"
                           "      count"
                           "    }"
                           "  }"
                           "}",
                     variables=dict(subjectsIds=ids, userId=self.user_id))]
        url = 'https://znanija.com/graphql/ru'
        response = session.post(url=url, data=json.dumps(data), headers=headers)
        if response.ok:
            user_info = response.json()[0]['data']['userById']
            self.nick = user_info['nick'] if self.nick is None else self.nick
            self.rank = None if user_info['rank'] is None else user_info['rank']['name']
            self.created = datetime.fromisoformat(user_info['created']).strftime('%Y-%m-%d')
            self.answers_count = user_info['answers']['count']
            self.answers_count_by_subjects = [dict(subject_name=subject['subject']['name'], count=subject['count'])
                                              for subject in user_info['answerCountBySubject']]
            self.special_ranks = [rank['name'] for rank in user_info['specialRanks']]
        else:
            raise BlockedError(link=url, message=response.reason, error_code=response.status_code)

    @property
    def link(self):
        return f'https://znanija.com/profil/{self.nick}-{self.user_id}'

    def __str__(self):
        statuses_pretty = '; '.join(self.special_ranks + [self.rank] if self.rank is not None else [])
        if self.answers_count < 100:
            answer_count_by_subject_pretty = str()
        else:
            answer_count_by_subject_pretty = f'\tКоличество ответов по предметам:\n'
            answer_count_by_subject_pretty += '\n'.join([f'\t\t{subject["subject_name"]}: {subject["count"]}'
                                                        for subject in self.answers_count_by_subjects
                                                        if subject['count'] > 0.1 * self.answers_count])
            answer_count_by_subject_pretty += '\n'
        return (f'Пользователь:\n'
                f'\tНик: https://znanija.com/profil/{self.nick}-{self.user_id}\n'
                f'\tСтатусы: {statuses_pretty}\n'
                f'\tКоличество ответов: {self.answers_count}\n'
                f'{answer_count_by_subject_pretty}'
                f'\tЗарегистрирован: {self.created}\n')


class BrainlyTask:
    def __init__(self, link: str,
                 question: str,
                 subject: Subject,
                 answered_users: List[UserAnswer]):
        self.link = link
        self.question = question
        self.subject = subject
        self.answered_users = answered_users

    def __eq__(self, other):
        return (isinstance(other, BrainlyTask)
                and self.link == other.link
                and self.question == other.question
                and self.subject == other.subject
                and self.answered_users == other.answered_user)

    @staticmethod
    def get_info(link):
        scraper = cfscrape.create_scraper()
        request = scraper.get(f'https://znanija.com/api/14/api_tasks/main_view/{re.search(r"[0-9]+$", link).group(0)}')
        if request.ok:
            request_data = request.json()
            if request_data['success']:
                question = BeautifulSoup(request_data['data']['task']['content'], 'lxml').get_text(strip=True,
                                                                                                   separator='\n')
                answered_users = [UserAnswer(username=next(user['nick']
                                                           for user
                                                           in request_data['data']['presence']['solved']
                                                           if user['id'] == answer['user_id']),
                                             content=BeautifulSoup(answer['content'], 'lxml').get_text(strip=True, separator='\n'))
                                  for answer in request_data['data']['responses']]
                subject_id = request_data['data']['task']['subject_id']
                with sqlite3.connect('files/subjects.db') as db:
                    subject_name, channel_name = db.execute('select name, channel_name '
                                                            'from subjects_mapping '
                                                            'where id = :id', {"id": subject_id}).fetchone()

                return BrainlyTask(link=link,
                                   question=question,
                                   subject=Subject(subject_id, subject_name, channel_name),
                                   answered_users=answered_users)
            else:
                raise RequestError(link=link, message=request_data['message'], error_code=request_data['code'])
        else:
            raise BlockedError(link=link, message=request.reason, error_code=request.status_code)


class Place:
    def __init__(self, place: int, user: UserInfo, value: str):
        self.place = place
        self.user = user
        self.value = value

    def __str__(self):
        return (f'Место: {self.place}\n'
                f'{str(self.user)}')


class SubjectRating:
    def __init__(self, places: List[Place]):
        self.places = places

    @staticmethod
    def get_rating(subject_id: int, type_ratings: int, session: cfscrape.Session):
        link = f'https://znanija.com/api/28/api_global_rankings/view/{subject_id}/{type_ratings}'
        request = session.get(url=link)
        if request.ok:
            request_data = request.json()
            if request_data['success']:
                return SubjectRating(places=[Place(place=one_place['place'],
                                                   user=UserInfo(user_id=one_place['user_id'], session=session),
                                                   value=one_place['value'])
                                             for one_place in request_data['data']])
            else:
                raise RequestError(link=link, message=request_data['message'], error_code=request_data['code'])
        else:
            raise BlockedError(link=link, message=request.reason, error_code=request.status_code)
