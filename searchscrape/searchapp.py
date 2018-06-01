import time

from flask import Flask, jsonify, request, render_template

from hackernews import HackerNews

app = Flask("searchscrape")
hn = HackerNews()


@app.route("/v0/item/<int:item_id>")
def item(item_id):
    try:
        result = hn[item_id]
    except KeyError:
        result = None
    return jsonify(result)


@app.route("/v0/search/<string:term>")
def search(term):
    return jsonify(hn.search(term))


@app.route("/", methods=["GET"])
def index():
    term = request.args.get("q", "")
    if term:
        found = hn.search(term)
    else:
        found = {}

    decorated = []
    for idx, (story_id, comment_ids) in enumerate(found.items()):
        story = dict(hn[story_id])
        decorated.append((story["score"], len(comment_ids), idx, story))

    results = []
    for score, matching_comments, idx, story in reversed(sorted(decorated)):
        story["matching_comments"] = matching_comments
        story["discussion"] = "https://news.ycombinator.com/item?id=" + str(story["id"])
        story["pretty_time"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(story["time"]))
        results.append(story)

    return render_template("index.html", term=term, results=results)
