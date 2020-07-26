import json
import requests
import re
from flask import Flask, jsonify, request

SLACK_VERIFICATION_TOKEN = 'AWpTOQH0TOYjUwU1eLDapn7U'
SLACK_OAUTH_TOKEN = 'xoxb-1113661707335-1192105294019-d1Ivwdcf6oGab7UJCDIzhE3T'
SLACK_TEAM_ID = 'T013BKFLT9V'
app = Flask(__name__)


@app.route('/add-znatok', methods=['POST'])
def add_znatok():
    text = request.form['text']
    if not text:
        return jsonify(
            response_type='ephemeral',
            text='query is empty'
        )
    
    username_id = re.search(r'@\w+', text.split()[0]).string

    with open('command_requests.json', 'w+') as file:
        file.write(json.dumps(request.form, indent=4))

    response = requests.get('https://slack.com/api/users.info',
                            params={'token': SLACK_OAUTH_TOKEN,
                                    'user': 'U013SJ0HZ7D'})

    if not response.json()['ok']:
        return jsonify(
            response_type='ephemeral',
            text='This user does not exist'
        )

    return jsonify(
        response_type='ephemeral',
        text='Hi, This response from ngrok \n with file logs (version=8.2)',
    )


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
