# Search through HN data
import collections
import json
import textwrap
import time

import grequests

from hackernews import HackerNews


def show_search(hn, term, print_comments=False):
    found = hn.search(term)

    if not found:
        print("\n*** No matches for " + term)
        return

    comment_wrapper = textwrap.TextWrapper(width=100, initial_indent="  ", subsequent_indent="  ").fill

    decorated = []
    for idx, (story_id, comment_ids) in enumerate(found.items()):
        story = hn[story_id]
        decorated.append((story["score"], idx, story, comment_ids))

    print("\n*** Search results for " + term)
    for _, _, story, comment_ids in reversed(sorted(decorated)):
        print("Story {id} [{score}]: {title}".format(**story))
        if "url" in story:
            print("      {url}".format(**story))
        for line in []:  # story.get("text", "").splitlines():
            print(comment_wrapper(line))
        if print_comments:
            for comment_id in comment_ids:
                comment = hn[comment_id]
                print("- Comment {id}".format(**comment))
                for line in comment["text"].splitlines():
                    print(comment_wrapper(line))
        else:
            print("  with {} matching comments.".format(len(comment_ids)))


def load_files_into_mongo():
    exit(1)
    hn = HackerNews()
    hn.database.drop_collection("full")
    hn.database.drop_collection("search")
    del hn
    hn = HackerNews()
    import glob
    names = glob.glob("/Users/ark3/datawire/hn_data/*.json")
    for idx, name in enumerate(names):
        if not (idx + 1) % 1000:
            print(name, idx + 1)
        data = open(name).read()
        item = json.loads(data)
        if item:
            hn.add_item(item)
        else:
            print(name, repr(data))


def add_many_items(item_ids):
    hn = HackerNews()
    reqs = (grequests.get("https://hacker-news.firebaseio.com/v0/item/" + str(item_id) + ".json")
            for item_id in item_ids)
    result = []
    for resp in grequests.imap(reqs, size=50):
        item = resp.json()
        if not item:
            continue
        result.append(hn.update_item(item))
    return result


def grab_last_n_days(num_days):
    start_time = time.time()
    cutoff_time = start_time - (num_days * 24 * 60 * 60)
    hn = HackerNews()
    max_id = item_id = hn.get_max_item_id()
    stats = collections.Counter()
    step = 100
    try:
        while True:
            item_ids = range(item_id, item_id - step, -1)
            stats.update(add_many_items(item_ids))
            item = hn[item_id - step + 1]
            if item and item.get("time", start_time) < cutoff_time:
                break
            item_id -= step
            print(max_id - item_id, item_id, time.ctime(item.get("time", start_time)))
    finally:
        count = sum(stats.values())
        spent = time.time() - start_time
        bleh = dict(count=count, spent=spent, stats=stats)
        print("Fetched {count} items in {spent:.2f} seconds ".format(**bleh) +
              "({count / spent:.1f} items per second)".format(**bleh))
        print(" {stats['new']} new items, {stats['updated']} updates, {stats['same']} same as before".format(**bleh))


def main():
    hn = HackerNews()
    show_search(hn, "devop")
    show_search(hn, "kube")
    show_search(hn, "abc_not_present_xyz")
    show_search(hn, "asdf")


if __name__ == "__main__":
    #main()
    grab_last_n_days(7)
