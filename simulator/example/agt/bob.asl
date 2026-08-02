!start.

+!start: true <-
    .wait(10000);
    updateFeed(false).

+feed_order([Ids]): true <-
    .wait(message(M4, alice, ContentM4, OriginalM4, TimestampM4));
    repost(M4).
