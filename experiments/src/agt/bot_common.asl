/* Initial beliefs and rules */
random_miliseconds(X) :-
    .random(R) &
    M = R * 10000 &
    X = math.floor(M).

/* Plans */
+!intervene : random_miliseconds(X) <-
    .wait(X);
    updateFeed;
    .wait(feed_order(FeedList));
    !collect_messages(FeedList, "", Conversation);
    ia.generateIntervention(Conversation, Response);
    FeedList = [Last | _];
    comment(Last, [], [], Response);
    !intervene.

+!collect_messages([] , Conversation, Conversation) : true <- true.

+!collect_messages([ID|Tail], Conversation, Result) : true <-
    .wait(message(ID, Author, Content, _, _));
    .concat("\n@", Author, ": ", Content, Post);
    .concat(Post, Conversation, UpdatedConversation);
    !collect_messages(Tail, UpdatedConversation, Result).
