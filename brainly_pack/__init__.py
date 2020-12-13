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
        answered_users = [dict(user=answer.find('div', attrs={"class": "brn-qpage-next-answer-box-author__description"})
                                          .findChild('span')
                                          .get_text(strip=True),
                               text=answer.find(name='div', attrs={"data-test": "answer-box-text"})
                                          .get_text(separator='\n', strip=True))
                          for answer
                          in beautiful_soup.find('div', attrs={'data-test': 'answer-box-list'})
                                           .findChildren('div', recursive=False)]
        return dict(ok=True,
                    link=link,
                    subject=beautiful_soup.find('a', attrs={'data-test': 'question-box-subject'}).get_text(strip=True),
                    answered_users=answered_users)
    else:
        return dict(ok=False, link=link, error_code=request.status_code)