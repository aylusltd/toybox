var firebase = require("firebase");

firebase.initializeApp({
    databaseURL: "https://hacker-news.firebaseio.com/"
});

var fireDb = firebase.database();

var mongoDb = null;


function addItem(item) {
    var idDict = { _id: item.id };
    item._id = item.id;
    return mongoDb.collection("full").replaceOne(idDict, item, { upsert: true }).then(function (result) {
        var searchable = { _id: item.id, id: item.id, content: (item.text || "") + " " + (item.title || "") };
        return mongoDb.collection("search").replaceOne(idDict, searchable, { upsert: true });
    });
}

function downloadItem(item_id) {
    //console.log("Trying to download " + item_id);
    var path = "/v0/item/" + String(item_id);
    return fireDb.ref(path).once("value").then(function (snapshot) {
        var item = snapshot.val();
        //console.log("Downloaded item: " + (item && item.id || item));
        if (item) {
            return addItem(item).then(function (result) {
                return Promise.resolve(item);
            });
        } else {
            return Promise.resolve(null);
        }
    });
}

function getItem(item_id) {
    return mongoDb.collection("full").findOne({ _id: item_id }).then(function (item) {
        //console.log("getItem findOne got: " + item);
        if (!item) {
            item = downloadItem(item_id);
            //console.log("getItem download got: " + item);
        }
        return item;
    });
}

function getMany(ids) {
    return Promise.all(ids.map(function (id) {
        return getItem(id);
    })).then(function (items) {
        var idx;
        for (idx = items.length; idx >= 0; idx -= 1) {
            if (items[idx]) {
                return items[idx];
            }
        }
        return Promise.resolve(null);
    });
}

function getMaxId() {
    return fireDb.ref("/v0/maxitem").once("value").then(function (snapshot) {
        console.log("Max ID: " + snapshot.val());
        return snapshot.val();
    });
}

//getMaxId().then(function (maxId) { console.log("Max ID is " + maxId); });

function getSome(upper, count) {
    var idx;
    var ids = [];
    for (idx = 0; idx < count; idx += 1) {
        ids.push(upper - idx);
    }
    return getMany(ids);
}

function getRecent(seconds) {
    var nowSeconds = Date.now() / 1000;
    var oldestSeconds = nowSeconds - seconds;

    function maybeMore(item) {
        if (item.time >= oldestSeconds) {
            console.log("maybemore Launching getsome " + item.id + " " + new Date(item.time * 1000));
            return getSome(item.id - 1, 1000).then(maybeMore);
        } else {
            console.log("maybemore doing nothing");
            return item;
        }
    }

    return getMaxId().then(function (maxId) {
        console.log("Got max id, launching getitem of that ID");
        return getItem(maxId).then(function (item) {
            console.log("Got max ID item, launching maybemore of that item");
            console.log("Got: " + item);
            return maybeMore(item);
        });
    });
}

var MongoClient = require("mongodb").MongoClient;
MongoClient.connect("mongodb://localhost:27017/HackerNews", function (err, database) {
    mongoDb = database;
    getRecent(60 * 60 * 24 * 30).then(function () {
        mongoDb.collection("full").count().then(function (count) {
            console.log("Full database has " + count + " items.");
            mongoDb.collection("full").find().sort({ _id: 1 }).nextObject(function (err, item) {
                console.log("  Low ID is " + item.id);
                mongoDb.collection("full").find().sort({ _id: -1 }).nextObject(function (err, item) {
                    console.log("  High ID is " + item.id);
                });
            });
        });
    });
});


