// Agent bob in project app1

/* Initial beliefs and rules */

/* Initial goals */

!start.

/* Plans */

+!start : true <- 
    updateFeed.

+message(I,"alice",C,O,T) : true <-
    .findall(X, interpretation(I,X), Xs);
    .print(Xs);
    repost(I);
    createPost(["floods"], [raise_awareness(true), emotion("worry")]);
    react(I, "love");
    comment(I, Xs, C, ["music"], [raise_awareness(true), emotion("happy")]);
    searchAuthor(bob).

