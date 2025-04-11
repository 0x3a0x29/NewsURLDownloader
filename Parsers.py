from bs4 import BeautifulSoup

class BaseParser:
    '''解析器的基类'''
    def __init__(self)->None:
        self.html_content = None
        self.url = None
        self.soup = None

    def parse(self)->None:
        """子类应该实现这个方法，用于处理html内容"""
        raise NotImplementedError("子类必须实现 parse 方法")
    def setURL(self, url):
        self.url = url
    def setHTML(self, html_content):
        self.html_content = html_content
        self.soup = BeautifulSoup(html_content, 'html.parser')
class CNNParser(BaseParser):
    '''专门针对CNN新闻的解析器'''
    def parse(self):
        time = self.soup.find('div',class_="timestamp vossi-timestamp").get_text(strip=True).replace("Published","").strip()
        if (self.soup.find('body').get('data-page-type')=='article'):
            title_tag = self.soup.find('h1', class_='headline__text inline-placeholder vossi-headline-text')
            content_div = self.soup.find('div', class_='article__content')
            title = title_tag.get_text(strip=True) if title_tag else ''
            content = ''
            if content_div:
                for child in content_div.children:
                    if child.name == 'p':
                        content += child.get_text(strip=True).replace("::before","")
                    if child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        content += "**"+child.get_text(strip=True)+"**"
            return {
                'url': self.url,
                'title': title,
                'time': time,
                'content': content
            }
        elif (self.soup.find('body').get('data-page-type')=='live-story'):
            title_tag = self.soup.find('h1', class_='headline_live-story__text inline-placeholder vossi-headline-text')
            title = title_tag.get_text(strip=True) if title_tag else ''
            text_tag = self.soup.find('ul',class_="list_live-story__items list_live-story__items--ul")
            text=""
            for li in text_tag.children:
                if li.name == 'li':
                    text += li.get_text(strip=True).replace("::before","")
            posts = {
                'url': self.url,
                'title': title,
                'text': text
            }
            posts_list = []
            posts_tag = self.soup.find("div",class_="live-story__items-container")
            posts_html = posts_tag.find_all("div",class_="live-story-post__wrapper")
            for post_html in posts_html:
                time = post_html.find("time").get_text()
                title= post_html.find("h2",class_="live-story-post__headline inline-placeholder").get_text(strip=True)
                post_content_div = post_html.find("div",class_="live-story-post__content")
                post_content=""
                for child in post_content_div.children:
                    if child.name == 'p':
                        post_content += child.get_text(strip=True).replace("::before","")
                    if child.name in ['h3', 'h4', 'h5', 'h6']:
                        post_content += "**"+child.get_text(strip=True)+"**"
                post={
                    "title": title,
                    "time": time,
                    "content": post_content
                }
                posts_list.append(post)
            posts["posts"]=posts_list
            return posts
        
if __name__ == "__main__":
    pass
