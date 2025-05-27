from bs4 import BeautifulSoup
import urllib
from urllib.parse import urlparse

class BaseParser:
    '''解析器的基类'''
    def __init__(self)->None:
        self.html_content = None
        self.url = None
        self.soup = None
        self.disallowed_urls = self.load_robots()

    def parse(self)->None:
        """子类应该实现这个方法，用于处理html内容"""
        raise NotImplementedError("子类必须实现 parse 方法")
    def setURL(self, url):
        self.url = url
    def setHTML(self, html_content):
        self.html_content = html_content
        self.soup = BeautifulSoup(html_content, 'html.parser')
    def load_robots(self):
        return None
    def url_allowed(self, url: str) -> bool:
        """判断某个 URL 是否被 CNN 的 robots.txt 禁止"""
        if len(self.disallowed_urls)==0:
            return True
        parsed = urlparse(url)
        path = parsed.path
        for disallowed in self.disallowed_urls:
            if path.startswith(disallowed):
                return False
        return True
class CNNParser(BaseParser):
    '''专门针对CNN新闻的解析器'''
    def parse(self):
        
        data_page_type = self.soup.find('body').get('data-page-type')
        if (data_page_type==None):#无法处理类似于这种情况https://edition.cnn.com/interactive/2024/04/politics/trump-campaign-promises-dg/，因此将status设置为failed
            return {
                'url': self.url,
                'status': "failed"
           }
        elif (data_page_type=='article'):
            time = self.soup.find('div',class_=["timestamp", "vossi-timestamp"]).get_text(strip=True).replace("Published","").replace("Updated","").strip()
            title_tag = self.soup.find('h1', class_=["headline__text", "inline-placeholder", "vossi-headline-text"])
            content_div = self.soup.find('div', class_='article__content')
            title = title_tag.get_text(strip=True) if title_tag else ''
            content = ''
            if content_div:
                for child in content_div.children:
                    if child.name == 'p':
                        content += child.get_text(strip=True).replace("::before","") + "\n"
                    if child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        content += "**"+child.get_text(strip=True)+"**"
            return {
                'url': self.url,
                'status': "success",
                'title': title,
                'time': time,
                'content': content
            }
        elif (data_page_type=='live-story'): #特殊的格式：live-news
            time = self.soup.find('div',class_=["timestamp", "vossi-timestamp"]).get_text(strip=True).replace("Published","").replace("Updated","").strip()
            title = self.soup.find('h1', class_=["headline_live-story__text", "inline-placeholder", "vossi-headline-text"]).get_text(strip=True)
            content = self.soup.find('article',class_=["live-story-post_pinned", "liveStoryPost"]).get_text(strip=True).replace("::before","")
            posts = {
                'url': self.url,
                'status': "success",
                'title': title,
                'time': time,
                'content': content
            }
            posts_list = []
            posts_tag = self.soup.find("div",class_="live-story__items-container")
            posts_html = posts_tag.find_all("div",class_="live-story-post__wrapper")
            for post_html in posts_html:
                time = post_html.find("time").get_text()
                title= post_html.find("h2",class_=["live-story-post__headline", "inline-placeholder"]).get_text(strip=True)
                post_content_div = post_html.find("div",class_="live-story-post__content")
                post_content=""
                for child in post_content_div.children:
                    if child.name == 'p':
                        post_content += child.get_text(strip=True).replace("::before","")+ "\n"
                    if child.name in ['h3', 'h4', 'h5', 'h6']:
                        post_content += "**"+child.get_text(strip=True)+"**"
                post={
                    "title": title,
                    'status': "success",
                    "time": time,
                    "content": post_content
                }
                posts_list.append(post)
            posts["posts"]=posts_list
            return posts
        elif (data_page_type=="gallery"):
            title = self.soup.find("h1",class_=["headline__text", "inline-placeholder", "vossi-headline-text"]).get_text(strip=True)
            time = self.soup.find("div",class_=["timestamp", "vossi-timestamp"]).get_text(strip=True).replace("Published","").replace("Updated","").strip()
            content =self.soup.find("div",class_="gallery-inline__main").get_text(strip=True)
            return {
                'url': self.url,
                'status': "success",
                'title': title,
                'time': time,
                'content': content
            }
        else: #可能存在其他未考虑到的情况
            return {
                'url': self.url,
                'status': "failed"
            }
    def load_robots(self):
        disallowed_paths = []
        try:
            with urllib.request.urlopen("https://edition.cnn.com/robots.txt", timeout=10) as response:
                lines = response.read().decode("utf-8").splitlines()
                for line in lines:
                    line = line.strip()
                    if line.startswith("Disallow:"):
                        path = line[len("Disallow:"):].strip()
                        if path:
                            disallowed_paths.append(path)
        except Exception as e:
            print(f"⚠️ 下载 robots.txt 失败: {e}")
        return disallowed_paths
        
if __name__ == "__main__":
    pass
