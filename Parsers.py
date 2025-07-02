from bs4 import BeautifulSoup
import urllib
from urllib.parse import urlparse

class BaseParser:
    '''解析器的基类'''
    def __init__(self, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")->None:
        self.html_content = None
        self.url = None
        self.user_agent = user_agent
        self.robots_rules = self.load_robots()

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
    def url_allowed(self, url: str)->bool:
        parsed = urlparse(url)
        path = parsed.path
        allowed = True  # 默认允许
        for directive, rule_path in self.robots_rules:
            if rule_path == "":
                continue
            if path.startswith(rule_path):
                if directive == "Disallow":
                    allowed = False
                elif directive == "Allow":
                    allowed = True
        return allowed
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
                        content += child.get_text().replace("::before","") + "\n"
                    if child.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        content += "**"+child.get_text()+"**"
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
            content = self.soup.find('article',class_=["live-story-post_pinned", "liveStoryPost"]).get_text().replace("::before","")
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
                        post_content += child.get_text().replace("::before","")+ "\n"
                    if child.name in ['h3', 'h4', 'h5', 'h6']:
                        post_content += "**"+child.get_text()+"**"
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
            content =self.soup.find("div",class_="gallery-inline__main").get_text()
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
        """按 user-agent 加载 robots.txt 中对应的 Allow/Disallow 规则"""
        try:
            with urllib.request.urlopen("https://edition.cnn.com/robots.txt", timeout=10) as response:
                lines = response.read().decode("utf-8").splitlines()
        except Exception as e:
            print(f"⚠️ 下载 robots.txt 失败: {e}")
            return []
        rules = {}
        current_agents = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.lower().startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                current_agents = [agent]
                if agent not in rules:
                    rules[agent] = []
            elif line.lower().startswith(("disallow:", "allow:")):
                directive, value = line.split(":", 1)
                directive = directive.strip().capitalize()
                path = value.strip()
                for agent in current_agents:
                    rules.setdefault(agent, []).append((directive, path))
        return rules.get(self.user_agent, rules.get("*", []))
if __name__ == "__main__":
    pass
