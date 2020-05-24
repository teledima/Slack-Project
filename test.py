import requests
data = {'username': 'teledima00', 'password': "${mXh$8Q", 'type_client': 5}
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 ' \
             'Safari/537.36 '

s = requests.Session()

s.get('https://znanija.com/', headers={'user_agent': user_agent})
log_in = s.post('https://znanija.com/api/28/api_account/authorize',
                      data=data,
                      headers={'user_agent': user_agent, 'referer': 'https://znanija.com/login?entry=2'})

# moderators_list = requests.get('https://znanija.com/moderators/mod_list',
#                                cookies=log_in.cookies)
main_page = s.get('https://znanija.com/moderators/mod_list',
                  headers={'user_agent': user_agent})
print(log_in.text)
