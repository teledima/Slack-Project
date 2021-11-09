from bs4 import BeautifulSoup
from typing import List
import sqlite3
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


class BrainlyTask:
    def __init__(self, link: str,
                 question: str = None,
                 subject: Subject = None,
                 answered_users: List[UserAnswer] = None):
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
    def get_info(link, session):
        request = session.get(f'https://znanija.com/api/14/api_tasks/main_view/{re.search(r"[0-9]+$", link).group(0)}')
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
