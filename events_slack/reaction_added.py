import pytz
import cfscrape
from datetime import datetime
from slack_sdk import WebClient

from slack_core import utils, constants, authorize, smiles_collection, settings_collection
from brainly_core import BrainlyTask, BlockedError, RequestError
from .errors import SmileExistsButUserHasNotAnswer, ExpertNameNotFound


def reaction_added(event_data):
    emoji = event_data["event"]["reaction"]
    doc = smiles_collection.document(emoji).get()
    current_timestamp = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M:%S')
    if doc.exists:
        expert_name = doc.to_dict()['expert_name']
        link = utils.extract_link_from_message(event_data['event']['item']['channel'], event_data['event']['item']['ts'])

        client = authorize()
        # open 'popular' sheet
        if event_data['event']['item']['channel'] == 'C5X27V19S':
            worksheet = client.open('Кандидаты(версия 2)').worksheet('test_list_popular')
        # open sheet for archive
        else:
            worksheet = client.open('Кандидаты(версия 2)').worksheet('test_list')
        try:
            answered_users = [answer.username.lower()
                              for answer in BrainlyTask.get_info(link, cfscrape.create_scraper(headers={'User-Agent': 'RuArchiveSlackBot'})).answered_users]
            if expert_name.lower() in answered_users:
                worksheet.append_row([current_timestamp, 'решение', expert_name, link])
            else:
                raise SmileExistsButUserHasNotAnswer(f'Смайл "{emoji}" существует но пользователь, который к нему привязан не отвечал на данный вопрос. Пользователь, к которому привязан смайл: {expert_name}. Пользователи, ответившие на вопрос "{link}": {answered_users}')
        except (RequestError, BlockedError):
            worksheet.append_row([current_timestamp, 'решение', expert_name, link, '?'])
    else:
        if emoji == 'lower_left_ballpoint_pen':
            bot = WebClient(constants.SLACK_OAUTH_TOKEN_BOT)

            link = utils.extract_link_from_message(event_data['event']['item']['channel'], event_data['event']['item']['ts'])
            response = bot.reactions_get(channel=event_data['event']['item']['channel'], full=True, timestamp=event_data["event"]["item"]["ts"])
            list_smiles = response[response['type']]['reactions']
            # if there are two or more emotions lower_left_ballpoint_pen in the message, then the notification will not be sent
            if not [1 for smile in list_smiles if smile['name'] == 'lower_left_ballpoint_pen' and smile['count'] == 1]:
                return
            # get the user whose message has a smiley attached to it
            user_id = event_data['event']['item_user']
            # check if the user needs to send a notification
            user_settings = settings_collection.document(user_id).get()

            send_notification = user_settings.get('send_notification') if user_settings.exists else False

            if send_notification:
                bot.chat_postMessage(
                    channel=user_id,
                    text=f'В вопросе {link} освободились поля для ответов!\n'
                         f'Ссылка на проверку: <https://znanija-archive.slack.com/archives/{event_data["event"]["item"]["channel"]}/{event_data["event"]["item"]["ts"].replace(".", "")}>'
                )
        else:
            raise ExpertNameNotFound(f'Ник пользователя со смайлом {emoji} отсутствует в базе данных')
