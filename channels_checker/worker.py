import json
import re
import cfscrape
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_core import constants
from flask import Blueprint

channels = ['C6Z5Y47CG', 'C73P36V32', 'C7L8QNY5T', 'C7K2SLQ7M', 'C7D6KFY1X', 'C6W3RKNF9', 'C6V5A1CF2', 'C7L8QSA3F',
            'C7K55693L', 'C9RLE568J', 'C8C51TY0M', 'C6VN5UUTD', 'C6VN48WBD', 'C7K98JW13']
slack_bot = WebClient(token=constants.CHECKER_SLACK_BOT_TOKEN)
scraper = cfscrape.create_scraper()
channels_checker_blueprint = Blueprint('channels_checker_blueprint', __name__)


def get_messages():
    stack = []
    for channel in channels:
        cursor = None
        while True:
            conversation = slack_bot.conversations_history(channel=channel, limit=100, cursor=cursor)

            for message in conversation['messages']:
                try:
                    text = message['attachments'][0]['title'] if 'bot_profile' in message else message['text']
                    link = re.search(r'znanija\.com/task/\d+', text)
                    if link is None: continue

                    stack.append({
                        'ts': message['ts'],
                        'channel': channel,
                        'taskId': int(link.group().split('/').pop()),
                        'reactions': [reaction['name'] for reaction in
                                      message['reactions']] if 'reactions' in message else [],
                        'has_threads': 'reply_count' in message
                    })
                except:
                    continue

            cursor = conversation['response_metadata']['next_cursor'] if conversation['has_more'] else None
            if cursor is None:
                break
    return stack


def get_brainly_data(msgs):
    query = ''
    for msg in msgs:
        q = f"task{msg['taskId']}: questionById(id: {int(msg['taskId'])}) " + "{ canBeAnswered databaseId answers { hasVerified nodes {id isConfirmed} } } "
        query += q

    brainly_data = scraper.post(
        url='https://znanija.com/graphql/ru',
        data=json.dumps({'query': '{ ' + query + '}'}),
        headers={'content-type': 'application/json; charset=utf-8'}
    )
    if brainly_data.status_code == 403:
        print('Blocked! 403 forbidden')
        return {'data': None}

    return brainly_data.json()


@channels_checker_blueprint.route('/check-slack-channels', methods=['GET'])
def main():
    slack_messages = get_messages()
    if len(slack_messages) < 1: return

    brainly_data = get_brainly_data(slack_messages)['data']
    if brainly_data is None: return 'Brainly error! 403 Forbidden'

    for k in brainly_data.keys():
        task = brainly_data[k]
        if task is None: continue

        slack_message = None
        for slack_msg in slack_messages:
            if slack_msg['taskId'] == task['databaseId']: slack_message = slack_msg
        if slack_message is None: continue

        # contains verified answers -> delete
        if task['answers']['hasVerified']:
            verified_answers = []
            for answer in task['answers']['nodes']:
                if answer['isConfirmed']: verified_answers.append(answer)

            if len(task['answers']['nodes']) == len(verified_answers):
                print(f"Contains verified -> https://znanija.com/task/{task['databaseId']}")

                if slack_message['has_threads']:
                    replies = slack_bot.conversations_replies(channel=slack_message['channel'],
                                                              ts=slack_message['ts'])
                    for reply in replies['messages']:
                        if 'parent_user_id' not in reply: continue
                        slack_bot.chat_delete(channel=slack_message['channel'], ts=reply['ts'],
                                              token=constants.CHECKER_SLACK_ADMIN_TOKEN)

                try:
                    slack_bot.chat_delete(
                        channel=slack_message['channel'],
                        ts=slack_message['ts'],
                        token=constants.CHECKER_SLACK_ADMIN_TOKEN
                    )
                except SlackApiError:
                    continue

        # answer has been deleted
        if len(task['answers']['nodes']) == 0:
            print(f"No answers -> https://znanija.com/task/{task['databaseId']}")

            try:
                slack_bot.reactions_add(
                    channel=slack_message['channel'],
                    timestamp=slack_message['ts'],
                    name='lower_left_ballpoint_pen'
                )
            except SlackApiError:
                continue
        # if there is a pen and there are answers then delete pen smile
        else:
            if 'lower_left_ballpoint_pen' in slack_message['reactions']:
                print(f"Remove smile -> https://znanija.com/task/{task['databaseId']}")
                try:
                    slack_bot.reactions_remove(
                        name='lower_left_ballpoint_pen',
                        channel=slack_message['channel'],
                        timestamp=slack_message['ts']
                    )
                except SlackApiError:
                    continue

    return 'Executed'
