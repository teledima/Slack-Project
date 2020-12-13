from bs4 import BeautifulSoup
import cfscrape


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
    request = scraper.get(link)
    if request.ok:
        beautiful_soup = BeautifulSoup(request.content, 'lxml')
        return [answer.get_text(separator='\n').strip() for answer in beautiful_soup.find_all(name='div', attrs={"data-test": "answer-box-text"})]
    else:
        return ["Не удалось загрузить ответы"]