!start.

+!start: true <-
    searchAuthor(alice, false);
    !esperarFeed.

+!esperarFeed: feed_order([M4, M1]) <-
    repost(M4).

+!esperarFeed: not feed_order([_,_]) <-
    .wait(1000);
    searchAuthor(alice, false);
    !esperarFeed.