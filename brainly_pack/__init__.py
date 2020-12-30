from bs4 import BeautifulSoup
import cfscrape
import sqlite3
import re


def get_answered_users(link):
    scraper = cfscrape.create_scraper()
    request = scraper.get(link)
    if request.status_code == 200:
        beautiful_soup = BeautifulSoup(request.content, 'lxml')
        return dict(ok=True,
                    users=[div_el.span.text.replace('\n', '').lower()
                           for div_el
                           in beautiful_soup.find_all('div',
                                                      {'class': "brn-qpage-next-answer-box-author__description"})])
    else:
        return dict(ok=False, users=[], error_code=request.status_code)


def get_task_info(link):
    scraper = cfscrape.create_scraper()
    request = scraper.get(f'https://znanija.com/api/14/api_tasks/main_view/{re.search(r"[0-9]+$",link).group(0)}')
    if request.ok:
        request_data = request.json()
        if request_data['success']:
            question = BeautifulSoup(request_data['data']['task']['content'], 'lxml').get_text(strip=True,
                                                                                               separator='\n')
            answered_users = [dict(user=next(user['nick']
                                             for user
                                             in request_data['data']['presence']['solved']
                                             if user['id'] == answer['user_id']),
                                   text=BeautifulSoup(answer['content'], 'lxml').get_text(strip=True, separator='\n'))
                              for answer in request_data['data']['responses']]
            subject_id = request_data['data']['task']['subject_id']
            assert isinstance(subject_id, int)
            with sqlite3.connect('files/subjects.db') as db:
                subject_name, channel_name = db.execute('select name, channel_name '
                                                        'from subjects_mapping '
                                                        'where id = :id', {"id": subject_id}).fetchone()
            return dict(ok=True,
                        link=link,
                        question=question,
                        subject=dict(name=subject_name, channel_name=channel_name),
                        answered_users=answered_users)
        else:
            return dict(ok=False, link=link, message=request_data['message'], error_code=request_data['code'])
    else:
        return dict(ok=False, link=link, message=request.reason, error_code=request.status_code)
