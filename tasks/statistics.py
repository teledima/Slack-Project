from flask import Blueprint, request, make_response
from slack_sdk.web.client import WebClient
from znatoks import authorize
from slack_core import constants
from brainly_core import SubjectRating, BlockedError
import cfscrape
import sqlite3

# replace in App Engine to r'/usr/sbin/tor'
# TOR_CMD = r'C:\Users\Dmitry\Desktop\Tor Browser\Browser\TorBrowser\Tor\tor.exe'
WEEK = 3
task_statistics_blueprint = Blueprint('task_statistics', __name__)


@task_statistics_blueprint.route('/tasks/statistics')
def get_statistics():
    if 'X-Appengine-Cron' not in request.headers or request.headers['X-Appengine-Cron'] is False:
        return make_response('', 403)
    bot_client = WebClient(token=constants.SLACK_OAUTH_TOKEN_BOT)
    worksheet = authorize().open('Кандидаты(версия 2)').worksheet('statistics')
    worksheet.clear()
    worksheet.append_row(["Предмет", "Ник", "Статусы", "Количество ответов",
                          "Дата регистрации", "Количество ответов по предметам"])
    session = cfscrape.Session()
    with sqlite3.connect('files/subjects.db') as db:
        for subject_id, subject_name in db.execute('select id, name '
                                                   'from subjects_mapping '
                                                   'where channel_name != (select channel_name '
                                                   '                       from subjects_mapping where name is null)'):
            values = []
            try:
                places = SubjectRating.get_rating(subject_id, WEEK, session).places
            except BlockedError as error:
                bot_client.chat_postMessage(channel='G0182K2AFRQ',
                                            text=f'Произошла ошибка при загрузке рейтинга по предмету {subject_name}.'
                                                 f'Через 10 минут запуститься повторное выполнение задания')
                raise error
            for place in places:
                user = place.user
                if len(user.special_ranks) > 0:
                    continue
                statuses_pretty = '; '.join(user.special_ranks + [user.rank] if user.rank is not None else [])
                values.append([subject_name, user.link, statuses_pretty, user.answers_count, user.created,
                               *[f'{subject["subject_name"]}: {subject["count"]}'
                                 for subject in user.answers_count_by_subjects
                                 if subject['count'] > 0.1 * user.answers_count and user.answers_count >= 100]])
            worksheet.append_rows(values=values)
    bot_client.chat_postMessage(channel='G0182K2AFRQ', text='Загрузка статистики завершена')
    return make_response('', 200)
