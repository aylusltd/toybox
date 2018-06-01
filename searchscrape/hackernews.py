import pymongo
import requests


class HackerNews(object):

    def __init__(self):
        self.database = pymongo.MongoClient()["HackerNews"]
        self.database.search.create_index([("content", pymongo.TEXT)])
        self.session = requests.Session()

    def __getitem__(self, item_id):
        return self.database.full.find_one(dict(_id=item_id)) or self.download_item(item_id)

    def download_item(self, item_id):
        resp = self.session.get("https://hacker-news.firebaseio.com/v0/item/" + str(item_id) + ".json")
        item = resp.json()
        if not item:
            raise KeyError((item_id, resp.text))
        self.add_item(item)
        return item

    def add_item(self, item):
        id_dict = dict(_id=item["id"])
        item["_id"] = item["id"]  # Mutate item in-place!
        self.database.full.replace_one(id_dict, item, upsert=True)
        searchable = dict(_id=item["id"], id=item["id"], content=item.get("text", "") + " " + item.get("title", ""))
        self.database.search.replace_one(id_dict, searchable, upsert=True)

    def update_item(self, item):
        original = self.database.full.find_one(dict(_id=item["id"])) or None
        self.add_item(item)
        if item == original:
            return "same"
        if not original:
            return "new"
        return "updated"

    def get_max_item_id(self):
        resp = self.session.get("https://hacker-news.firebaseio.com/v0/maxitem.json")
        return resp.json()

    def find_story(self, item):
        item_type = item["type"]
        if item_type == "story":
            return item
        if item_type == "comment":
            return self.find_story(self[item["parent"]])
        print("***** find_story returning non-story item {id} with type {type}".format(**item))
        return item

    def search(self, term):
        stories = {}  # story id -> [ comment id, ... ]
        term = term.lower()
        for searchable in self.database.search.find({"$text": {"$search": term, "$language": "en"}}):
            item_id = searchable["_id"]
            item = self[item_id]
            if item.get("dead") or item.get("deleted"):
                continue
            if item["type"] == "story":
                stories.setdefault(item_id, [])
            elif item["type"] == "comment":
                story = self.find_story(item)
                if story.get("dead") or story.get("deleted"):
                    continue
                story_id = story["id"]
                stories.setdefault(story_id, [])
                stories[story_id].append(item_id)
            else:
                print("***** Skipping item {id} with type {type}".format(**item))
        return stories
