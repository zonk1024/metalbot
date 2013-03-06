function populateArtists()
{
    $.get("/api/artists", "", function(data, status) {
        var artistTree = [];

        $.each(data, function() {
            var artist = { label: this["artist"], children: []};

            $.each(this["albums"], function() {
                artist["children"].push({label: this["album"] });
            });

            artistTree.push(artist);
        });

        $(".albums").tree({
            data: artistTree,
            onCanSelectNode: function(node) {
                if (node.children.length > 0)
                    return false;
                return true;
            }
        });

    });
}

function createBindings()
{
    $(".albums").bind("tree.select", function(event) {
        var node = event.node;
        artist = node.parent.name;
        album = node.name;
        $.get("/api/songs/" + artist + "/" + album, "", function(data, status) {
            var songlist = [];

            $.each(data, function() {
                songlist.push({label: "[" + this["id"] + "] " + this["title"]});
            });
            $(".songs").tree({
                data: songlist
            });
            $("#queuesong").css("display", "");
            $("#queuealbum").css("display", "");
            $("#queuealbum").data("currentalbum", artist + "/" + album);
        });
    });

    $(".songs").bind ("tree.select", function(event) {
        var node = event.node;

        var regex = /\[(\d+)\]/;
        id = regex.exec(node.name);
        if (id[1])
            $("#queuesong").data("currentsong", id[1]);
    });

    $("#queuesong").click(function(e) {
        id = $(this).data("currentsong");
        if (id)
        {
            $.get("/api/queue/" + id, "", function(data, status){
                getQueue();
            });
        }
    });

    $("#queuealbum").click(function(e) {
        if (!confirm("Confirm the whole damn album? That's a lot of " + artist + "..."))
            return;

        id = $(this).data("currentalbum");
        if (id)
        {
            $.get("/api/queue/" + id, "", function(data, status){
                getQueue();
            });
        }
    });
}

function getQueue()
{
    $.get("/api/queue", "", function(data, status) {
        $("#queue").html("");
        $.each(data, function() {
            $("#queue").append("<li>[" + this["sid"] + "] <b>" + this["artist"] + "</b> - <i>" + this["title"] + "</i></li>");
        });
    });
    setTimeout(getQueue, 30000);
}

function getSongs()
{
    $.get("/api/upcoming/10", "", function(data, status) {
        $("#upcoming").html("");
        $.each(data, function() {
            $("#upcoming").append("<li>[" + this["sid"] + "] <b>" + this["artist"] + "</b> - <i>" + this["title"] + "</i></li>");
        });
    });
    $.get("/api/currentsong", "", function(data, status) {
        $("#covercontainer").css("display:none");
        $("#currentsong").html("[" + data["sid"] + "] <b>" + data["artist"] + "</b> - <i>" + data["title"] + "</i>");
        $("#currentalbum").html("From the \"" + data["album"] + "\" album");
        if (data["coverpath"] != null)
        {
            $(".cover").attr("src", data["coverpath"]);
            $("#covercontainer").css("display", "");a
        }
    });
    setTimeout(getSongs, 30000);
}

