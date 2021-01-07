class AuthedUser:
    def __init__(self, app_id: str, id: str, access_token: str, token_type: str, scope: str, team_id: str, team_name: str):
        self.app_id = app_id
        self.user = dict(id=id, scope=scope, access_token=access_token, token_type=token_type)
        self.team = dict(team_id=team_id, team_name=team_name)

    @staticmethod
    def from_dict(source):
        return dict(app_id=source['app_id'],
                    user=dict(id=source['authed_user']['id'],
                              scope=source['authed_user']['scope'],
                              access_token=source['authed_user']['access_token'],
                              token_type=source['authed_user']['token_type']),
                    team=dict(id=source['team']['id'],
                              name=source['team']['username']))

    def to_dict(self):
        return dict(app_id=self.app_id, user=self.user, team=self.team)
