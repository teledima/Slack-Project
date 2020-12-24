from bs4 import BeautifulSoup
import cfscrape
import sqlite3


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
        answered_users = []
        for answer in beautiful_soup.find('div', attrs={'data-test': 'answer-box-list'}).findChildren('div', recursive=False):
            user = answer.find('div', attrs={"class": "brn-qpage-next-answer-box-author__description"}).findChild('span').get_text(strip=True)
            text = answer.find('div', attrs={"data-test": "answer-box-text"}, recursive=True)
            if not text.findChildren('p'):
                text = text.get_text(strip=True)
                answered_users.append(dict(user=user, text=text))
                continue
            for i in range(len(text)):
                latex_formulas = text[i].findChildren('img')
                if latex_formulas:
                    for latex_formula in latex_formulas:
                        latex_formula.replace_with(latex_formula['alt'])
            answered_users.append(dict(user=user, text='\n'.join([text_piece.text for text_piece in text])))
        question = beautiful_soup.find('h1', attrs={'data-test': 'question-box-text'}).get_text(separator='\n', strip=True)

        subject = dict()
        subject["name"] = beautiful_soup.find('a', attrs={'data-test': 'question-box-subject'}).get_text(strip=True)
        with sqlite3.connect('files/subjects.db') as db:
            subject['channel_name'] = db.execute('select channel_name '
                                                 'from subjects_mapping '
                                                 'where name = :name or name is null',
                                                 {"name": subject["name"]}).fetchone()[0]
        return dict(ok=True,
                    link=link,
                    question=question,
                    subject=subject,
                    answered_users=answered_users)
    else:
        return dict(ok=False, link=link, error_code=request.status_code)
