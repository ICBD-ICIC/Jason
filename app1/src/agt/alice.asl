// Agent alice in project app1

/* Initial beliefs and rules */

/* Initial goals */

!start.

/* Plans */

+!start : followedBy(X) <- 
    .print(X); 
    createPost(["floods"], [raise_awareness(true), emotion("worry")]).

-followedBy(X) : true <-
    .print(X).