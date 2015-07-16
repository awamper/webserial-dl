# coding: utf-8
"""
    Copyright 2015 Ivan awamper@gmail.com

    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License as
    published by the Free Software Foundation; either version 2 of
    the License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

import os
import subprocess
import click
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup

http_adapter = HTTPAdapter(max_retries=5)
session = requests.Session()
session.mount('http://', http_adapter)
session.mount('https://', http_adapter)

def parse_chapter(html_markup):
    content = ''
    html = BeautifulSoup(html_markup, 'lxml')

    text_title = html.find(class_='entry-title').text
    text_title = text_title.encode('utf-8')
    title = '<h1 class="chapter">{0}</h1>'.format(text_title)
    
    paragraphs = html.find(class_='entry-content').find_all('p')
    for paragraph in paragraphs:
        links = paragraph.find_all('a')
        for link in links: link.extract()
        paragraph = paragraph.text.strip()
        paragraph = paragraph.encode('utf-8')
        if paragraph: content += '<p>%s</p>\n\n' % paragraph

    next_url = html.find('link', rel='next')
    if next_url: next_url = next_url['href']

    return {
        'title': title,
        'text_title': text_title,
        'content': content,
        'next_url': next_url
    }


def get_statistics(chapters):
    total_chapters = len(chapters)
    total_length = 0
    total_words = 0

    for chapter in chapters:
        total_length += len(chapter['content'])
        total_words += len(chapter['content'].split(' '))

    return {
        'chapters': total_chapters,
        'length': total_length,
        'words': total_words
    }


def convert_book(path, out_format):
    out_path = '%s.%s' % (
        os.path.splitext(path)[0],
        out_format
    )

    with open(os.devnull, 'w') as f:
        subprocess.call(['ebook-convert', path, out_path], stdout=f)


def show_current_item(path):
    if path:
        return os.path.basename(path)


@click.command()
@click.option(
    '-n',
    '--name',
    help='Name of the book.',
    required=True,
    prompt=True
)
@click.option(
    '-p',
    '--part-length',
    default=130000,
    help='Size of a part of the book',
    show_default=True
)
@click.option(
    '--split/--no-split',
    default=True,
    help='Should split book to smaller parts',
    show_default=True
)
@click.option(
    '-d',
    '--directory',
    help='Directory in which book should be saved',
    type=click.Path(exists=True, resolve_path=True),
    default='.'
)
@click.option(
    '-c',
    '--convert-to',
    help='Convert book to this format (uses ebook-convert)',
    type=str,
    default=''
)
@click.option(
    '-m',
    '--max-chapters',
    help='Max chapters to download (0 - all chapters)',
    type=int,
    default=0,
    show_default=True
)
@click.version_option()
@click.argument(
    'chapter_url',
    type=str,
    nargs=1
)
def main(name, part_length, split, directory, convert_to, max_chapters, chapter_url):
    """ Download WordPress based webserials """

    paths = []
    chapters = []
    next_url = chapter_url

    click.echo(click.style('Downloading "%s"...' % name, bg='blue'))

    while next_url:
        if max_chapters and len(chapters) >= max_chapters: break

        response = session.get(next_url)

        if response.status_code != requests.codes.ok:
            click.echo(click.style(
                'Error code %s, reason "%s"' % (
                    response.status_code,
                    response.reason
                ),
                bg='red'
            ))
            chapters = []
            next_url = None
            break

        chapter = parse_chapter(response.text)
        chapters.append(chapter)
        next_url = chapter['next_url']

        click.echo(click.style(
            '\tChapter "%s" done.' % chapter['text_title'],
            bg='blue'
        ))

    statistics = get_statistics(chapters)
    click.echo(click.style(
        'Done! Statistics:\n\tChapters:%s\n\tWords:%s\n\tLength:%s' % (
            statistics['chapters'],
            statistics['words'],
            statistics['length']
        ),
        bg='blue'
    ))

    if split:
        part = 1
        content = ''

        for index, chapter in enumerate(chapters):
            content += '%s\n%s' % (
                chapter['title'],
                chapter['content']
            )

            if (
                (len(content) >= part_length) or
                (index == len(chapters) - 1)
            ):
                part_n = str(part).zfill(len(str(len(chapters))))
                numbered_name = '%s %s.html' % (part_n, name)
                path = os.path.join(directory, numbered_name)
                paths.append(path)

                fp = open(path, 'w')
                fp.write(content)
                fp.close()

                content = ''
                part += 1
    else:
        name = name + '.html'
        path = os.path.join(directory, name)
        paths = [path]

        fp = open(path, 'w')
        for chapter in chapters:
            chapter_content = '%s\n%s' % (
                chapter['title'],
                chapter['content']
            )
            fp.write(chapter_content)
        fp.close()

    if convert_to:
        with click.progressbar(
            paths,
            item_show_func=show_current_item,
            label='Converting',
            fill_char=click.style('#', fg='green')
        ) as bar:
            for path in bar:
                convert_book(path, convert_to)
                os.remove(path)
