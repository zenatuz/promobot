if __package__ is None or __package__ == '':
    from config import Config
else:
    from promobot.config import Config

import notify2
import re
import time
import urllib.request
from bs4 import BeautifulSoup
from config import Config
from datetime import datetime
from dbus import exceptions
from http.client import IncompleteRead
from json import dumps


class Promobot(Config):
    config = {}
    data = {}
    hdr = {}

    def __init__(self):
        self.config.update(
            Config().data
        )

        for kw in self.config.get('keywords', []):
            if not self.data.get(kw):
                self.data.update({
                    kw.lower(): []
                })

        self.hdr.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/35.0.1916.47 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,'
                      'application/xml;q=0.9,*/*;q=0.8'
        })

    def alert(self, level='', msg=''):
        if type(msg) == dict:
            if (self.config['telegram']['token'] and
               self.config['telegram']['chat_id']):
                try:
                    text = urllib.parse.urlencode({
                        'chat_id': self.config['telegram']['chat_id'],
                        'parse_mode': 'Markdown',
                        'text': 'Keyword: [{}]({})'.format(
                            level,
                            msg['url']
                        ),
                    }).encode()

                    urllib.request.urlopen(
                        self.config['telegram']['url'],
                        text,
                        timeout=60,
                    )
                except (urllib.error.HTTPError, IncompleteRead, OSError) as e:
                    self.alert(
                        'ERROR',
                        'Error on publishing data on telegram: {}'.format(
                            e
                        )
                    )
                    self.__init__()

            level = msg['title']
            msg = '{}\n---\n{}'.format(
                msg['desc'],
                msg['url'],
            )
        else:
            print(
                '{} - {} - {}'.format(
                    datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
                    level,
                    msg,
                )
            )

        if level == 'ERROR':
            time.sleep(10)
        elif level != 'INFO' and level != 'DEBUG':
            try:
                notify2.init('alert')
                n = notify2.Notification(
                    level,
                    msg,
                )
                n.show()
            except (exceptions.DBusException) as e:
                self.alert(
                    'ERROR',
                    'Error on alert: {}'.format(
                        e
                    )
                )

    def add_thread(self, kw, add, title, desc, url):
        if title:
            title = re.sub(r'\n|\t', '', title)

        if desc:
            desc = re.sub(r'\n|\t', '', desc)

        if re.match(
                r'.*{}.*'.format(kw),
                url
           ):
            for p in list(self.data.values()):
                for v in p:
                    if url == v['url']:
                        add = False
                        break

            if add:
                self.data[kw].append({
                    'title': title,
                    'desc': desc,
                    'url': url,
                    'datetime': datetime.now().strftime('%d-%m-%Y %H:%M')
                })

                self.alert(
                    kw,
                    self.data[kw][-1],
                )

    def pelando(self, each, t_title):
        d = {}
        d['title'] = t_title.find(text=True)
        d['desc'] = each.find(
            'div',
            {
                'class': 'cept-description-container overflow--wrap-break '
                         'width--all-12  size--all-s size--fromW3-m'
            }
        )
        d['url'] = t_title.get('href').lower()
        return d

    def hardmob(self, each, t_title, url):
        d = {}
        d['title'] = t_title.find(text=True)
        d['desc'] = each.get('title')
        d['url'] = '{}/{}'.format(
            re.search(
                r'.*://[^/]+',
                url,
            ).group(),
            t_title.get('href').lower(),
        )
        return d

    def get_topic(self, src):
        content = ''
        topic = []

        while len(topic) == 0:
            try:
                req = urllib.request.Request(
                    url=src['url'],
                    headers=self.hdr
                )

                content = urllib.request.urlopen(
                    req,
                    timeout=60,
                ).read()
            except (urllib.error.HTTPError, IncompleteRead, OSError) as e:
                self.alert(
                    'ERROR',
                    'Error on getting data: {}'.format(
                        e,
                    )
                )

            if content:
                soup = BeautifulSoup(content, 'html.parser')

                if src['topic'].get('class'):
                    topic = soup.findAll(
                        src['topic']['tag'],
                        {'class': src['topic']['class']}
                    )
                else:
                    topic = soup.findAll(
                        src['topic']['tag']
                    )

                if len(topic) == 0:
                    self.alert(
                        'ERROR', 'Error on searching topics'
                    )
            else:
                self.__init__()

        return topic

    def find_thread(self, src):
        topic = self.get_topic(src)

        for kw in self.data.keys():
            add = True

            for each in topic:
                if src['thread'].get('class'):
                    t_title = each.find(
                        src['thread']['tag'],
                        {'class': src['thread']['class']}
                    )
                else:
                    t_title = each.find(
                        src['thread']['tag']
                    )

                if t_title:
                    t = {}

                    if 'hardmob' in src['url']:
                        t = self.hardmob(each, t_title, src['url'])
                    elif 'pelando' in src['url']:
                        t = self.pelando(each, t_title)

                    self.add_thread(kw, add, t['title'], t['desc'], t['url'])

    def main(self):
        for i in self.config['src']:
            self.find_thread(i)

        self.alert(
            'DEBUG',
            'Data\n{}\n(Response at {})'.format(
                dumps(self.data, indent=2, ensure_ascii=False),
                datetime.now().strftime('%H:%M:%S'),
            )
        )
